"""CR55: APRS in plain language - test vectors are real packets heard on
144.800 MHz on 16.10.2026."""

import calendar
import re
import unittest

from tinybox import aprs

NOW = calendar.timegm((2026, 10, 16, 12, 1, 0))      # 14:01 local


def dec(dest, src, path, used, info, **kw):
    kw.setdefault("now", NOW)
    return aprs.decode(dest, src, path, [bool(x) for x in used], info, **kw)


def chips(r):
    return [c["t"] for c in r["chips"]]


def joined(r):
    return "".join(s["t"] for s in r["segs"])


class MicETests(unittest.TestCase):
    def test_yaesu_on_the_motorway(self):
        info = b'`+Y_s,U>/`"6J}145.500MHz DE PETER 73       messages welcome_% '
        r = dec("TX0W84", "OM4MO-9", ["OE3XWJ-10", "WIDE1", "WIDE2-1"], [1, 1, 0], info)
        self.assertEqual(r["title"], "Mic-E position report")
        self.assertEqual(r["dest"]["mode"], "payload")
        self.assertEqual(r["dest"]["device"], "Yaesu FTM-400DR")
        self.assertAlmostEqual(r["lat"], 48 + 7.84 / 60, places=4)
        self.assertAlmostEqual(r["lon"], 15 + 1.67 / 60, places=4)
        c = chips(r)
        for want in ("131 km/h → 257°", "233 m", "M1 En Route", "car", "Yaesu FTM-400DR"):
            self.assertIn(want, c)
        self.assertEqual(joined(r), info.decode())
        cells = r["mice"]["cells"]
        self.assertEqual([x["d"] for x in cells], ["4", "8", "0", "7", "8", "4"])
        self.assertEqual(cells[3]["bit"], "North")

    def test_longitude_offset_and_kenwood(self):
        r = dec("T9SRT8", "DA1MIY-9", ["DB0SLB-10", "WIDE1", "OE3XWJ-10", "WIDE2"], [1, 1, 1, 1],
                b'`}57l .j/]"6J}= ')
        self.assertAlmostEqual(r["lon"], 7 + 25.27 / 60, places=4)
        self.assertEqual(r["dest"]["device"], "Kenwood TM-D710")
        self.assertIn("M2 In Service", chips(r))
        self.assertIn("233 m", chips(r))

    def test_altitude_on_a_mountain(self):
        r = dec("TXTV16", "OE5RFO-9", ["OE3XWJ-10", "WIDE1", "WIDE2-1"], [1, 1, 0], b'`)Npl?Yj/`"Bw}_% ')
        self.assertIn("1370 m", chips(r))
        self.assertIn("M0 Off Duty", chips(r))

    def test_cut_off_packet(self):
        r = dec("TY4T13", "OK1UFM-9", ["OK0BR-1", "OE3XWJ-10", "WIDE2"], [1, 1, 1], b"`)4;")
        self.assertIn("cut off", r["title"])
        self.assertAlmostEqual(r["lat"], 49 + 44.13 / 60, places=4)


class PositionTests(unittest.TestCase):
    def test_uncompressed_with_course_and_altitude(self):
        info = b"!4808.09N/01508.51Ev297/000/A=000912Arnold car 578"
        r = dec("APDR10", "OE1IAH-8", ["OE3XWJ-10", "WIDE1", "WIDE2-1"], [1, 1, 0], info)
        self.assertEqual(r["dest"]["mode"], "device")
        self.assertIn("APRSdroid", r["dest"]["device"])
        self.assertIn("278 m", chips(r))
        self.assertIn("standing (course 297°)", chips(r))
        self.assertEqual(joined(r), info.decode())

    def test_overlay_and_phg(self):
        r = dec("APDW16", "OK0MIL-1", ["OE3XWJ-10", "WIDE2"], [1, 1],
                b"!5033.29N101355.86E#PHG2530iGate + Fill-in Digi")
        self.assertIn("overlay 1", " ".join(chips(r)))
        self.assertIn("PHG 4 W 3 dBi omni", chips(r))
        self.assertIn("DireWolf", r["dest"]["device"])

    def test_hf_gateway_is_explained(self):
        r = dec("APMI01-2", "OE3MZC-2", [], [], b"@161319z4812.06N/01555.87E& Igate in Neulengbach")
        self.assertIn("HF gateway", chips(r))                       # not "hF gateway"
        sym = [x for x in r["segs"] if x["label"] == "Symbol code"][0]
        self.assertIn("iGate", sym["mean"])
        self.assertEqual(sym["sym"], "/&")

    def test_compressed(self):
        r = dec("APOT2A", "OE3XKN-10", ["OE3XWJ-10", "WIDE1", "WIDE3-3"], [1, 1, 0], b"!/6,fxRISM} st 13.5V 25C")
        self.assertAlmostEqual(r["lat"], 48.2007, places=3)
        self.assertAlmostEqual(r["lon"], 15.6328, places=3)
        self.assertTrue(r["warnings"])                       # WIDE3-3 for a fixed station
        self.assertIn("⚠ unassigned", " ".join(chips(r)))   # /} is not a symbol

    def test_timestamp_of_a_clock_that_is_behind(self):
        r = dec("APMI06", "OE3SZA-15", ["OE3XWJ-10", "WIDE2-1"], [1, 0],
                b"@161034z4802.06N/01457.09E#Digipeater Hochkogel by OE3SZA")
        self.assertIn("clock off", " ".join(chips(r)))

    def test_weather_with_a_malformed_field(self):
        info = b"!4810.66N/01210.56E_000/000g000t065h0b09550a488m 15.04V_WX-HAAG OBB"
        r = dec("APRSWX", "DC1MBB-8", ["DB0HOB-10", "OE3XWJ-10", "WIDE2"], [1, 1, 1], info)
        self.assertEqual(r["title"], "Weather report")
        c = chips(r)
        for want in ("wind calm", "18.3 °C", "955.0 hPa", "humidity ⚠ invalid"):
            self.assertIn(want, c)
        self.assertEqual(joined(r), info.decode())

    def test_distance_from_the_locator(self):
        home = aprs.locator_to_latlon("JN88EP")
        r = dec("APDR10", "OE1IAH-8", [], [], b"!4808.09N/01508.51Ev297/000", home=home)
        self.assertTrue(any(re.fullmatch(r"\d+ km, \d+° from you", c) for c in chips(r)))


class OtherTypesTests(unittest.TestCase):
    def test_telemetry_is_scaled_with_the_definitions(self):
        mem = aprs.TelemetryMemory()
        for line in (b":OE3CRA-2 :PARM.Vin,Rx1h,Dg1h,Eff1h,A5,O1,O2,O3,O4,I1,I2,I3,I4",
                     b":OE3CRA-2 :UNIT.Volt,Pkt,Pkt,Pcnt,None,On,On,On,On,Hi,Hi,Hi,Hi",
                     b":OE3CRA-2 :EQNS.0,0.079,0,0,10,0,0,10,0,0,1,0,0,0,0",
                     b":OE3CRA-2 :BITS.11111111,Telemetry test"):
            r = dec("APMI04", "OE3CRA-2", [], [], line, memory=mem)
            self.assertEqual(r["title"], "Telemetry definition")
            self.assertEqual(joined(r), line.decode())
        info = b"T#002,176,016,000,033,000,00000000"
        r = dec("APMI04", "OE3CRA-2", [], [], info, memory=mem)
        c = chips(r)
        for want in ("Vin 13.9 Volt", "Rx1h 160 Pkt", "Dg1h 0 Pkt", "Eff1h 33 Pcnt", "bits: nothing active"):
            self.assertIn(want, c)
        self.assertEqual(joined(r), info.decode())

    def test_telemetry_without_definitions_stays_raw(self):
        r = dec("APOT2A", "OE3XKN-10", [], [], b"T#182,152,172,249,000,000,00000010",
                memory=aprs.TelemetryMemory())
        self.assertIn("A1 152", chips(r))

    def test_third_party_status(self):
        info = b"}OE3BIA-11>APRSWX,TCPIP,OE3BIA-12*:> WiSE Weather Station"
        r = dec("APMI06", "OE3BIA-12", ["OE3XWJ-10", "WIDE2"], [1, 1], info)
        self.assertEqual(r["title"], "Third-party packet: status report")
        self.assertIn("from OE3BIA-11 via iGate OE3BIA-12", chips(r))
        self.assertEqual(joined(r), info.decode())

    def test_message_with_number(self):
        r = dec("APDR16", "OE3GAS-7", [], [], b":OE3TEC   :Servus{12")
        self.assertEqual(r["title"], "Message")
        self.assertIn("to OE3TEC", chips(r))
        self.assertIn("no. 12, wants an ack", chips(r))

    def test_not_aprs(self):
        self.assertIsNone(dec("TBCHAT-1", "OE3GAS-1", [], [], b"#118 hello"))
        self.assertIsNone(dec("ID", "OE3GAS-1", [], [], b"OE3GAS-1/R BBS"))


class PathTests(unittest.TestCase):
    def test_heard_from_the_last_digipeater(self):
        self.assertEqual(aprs.heard_from("DA1MIY-9", ["DB0SLB-10", "WIDE1", "OE3XWJ-10", "WIDE2"], [True] * 4)[0],
                         "OE3XWJ-10")
        self.assertEqual(aprs.heard_from("OE3CRA-2", ["WIDE2-1"], [False])[0], "OE3CRA-2")
        self.assertEqual(aprs.heard_from("OE3CRA-2", ["WIDE2"], [True])[0], "")     # untraced digi
        r = dec("APMI04", "OE3CRA-2", ["OE3XWJ-10", "WIDE2-1"], [1, 0],
                b":OE3CRA-2 :UNIT.Volt,Pkt,Pkt,Pcnt,None,On,On,On,On,Hi,Hi,Hi,Hi")
        self.assertEqual(r["heard"]["call"], "OE3XWJ-10")
        self.assertEqual([c["call"] for c in r["chain"]], ["OE3CRA-2", "OE3XWJ-10"])
        self.assertTrue(r["segs"][-1]["mean"].startswith("A1 Volt · A2 Pkt"))
        r = dec("APMI06", "OM0ODX", ["OE6XTR", "OE3XWJ-10", "WIDE2"], [1, 1, 1], b">status")
        self.assertEqual([(c["call"], c["k"]) for c in r["chain"]],
                         [("OM0ODX", "src"), ("OE6XTR", ""), ("OE3XWJ-10", "heard")])
        r = dec("APMI06", "OM0ODX", ["WIDE2-1"], [0], b">status")
        self.assertEqual([(c["call"], c["k"]) for c in r["chain"]], [("OM0ODX", "heard")])


    def test_hops_used_and_left(self):
        rows, summary, warn = aprs.explain_path(["OE3XWJ-10", "WIDE1", "WIDE2-1"], [True, True, False])
        self.assertEqual(rows[0]["call"], "OE3XWJ-10*")
        self.assertIn("1 more hop", rows[2]["note"])
        self.assertIn("1 hop(s) still allowed", summary)
        self.assertEqual(warn, [])

    def test_no_path(self):
        rows, summary, _ = aprs.explain_path([], [])
        self.assertIn("No path", summary)


class DeviceTests(unittest.TestCase):
    def test_device_list(self):
        self.assertEqual(aprs.device_of("APMI06"), "Microsat WX3in1 Plus 2.0")
        self.assertIn("DireWolf", aprs.device_of("APDW17"))
        self.assertEqual(aprs.device_of("BEACON"), "")


def _addr(call: str, last: bool = False, hbit: bool = False) -> bytes:
    base, _, ssid = call.partition("-")
    b = bytes(ord(c) << 1 for c in base.ljust(6))
    return b + bytes([0x60 | (int(ssid or 0) << 1) | (0x80 if hbit else 0) | (1 if last else 0)])


class MonitorTests(unittest.TestCase):
    """The decoder in the monitors of the client and the TinyBox."""

    INFO = b'`+Y_s,U>/`"6J}145.500MHz_% '

    def test_client_monitor_entry(self):
        from tbclient import radio
        raw = (_addr("TX0W84") + _addr("OM4MO-9") + _addr("OE3XWJ-10", hbit=True) +
               _addr("WIDE1", hbit=True) + _addr("WIDE2-1", last=True) + b"\x03\xf0" + self.INFO)
        f = radio.decode(raw)
        self.assertEqual(f.repeated, [True, True, False])
        e = radio.monitor_entry(f, aprs_memory=aprs.TelemetryMemory())
        self.assertEqual(e["via"], ["OE3XWJ-10*", "WIDE1*", "WIDE2-1"])
        self.assertEqual(e["aprs"]["title"], "Mic-E position report")
        self.assertEqual("".join(s["t"] for s in e["aprs"]["segs"]), e["text"])

    def test_client_leaves_tinybox_frames_alone(self):
        from tbclient import radio
        raw = _addr("TBCHAT-1") + _addr("OE3GAS-1", last=True) + b"\x03\xf0" + b"!4808.09N/01508.51Ev"
        self.assertNotIn("aprs", radio.monitor_entry(radio.decode(raw)))

    def test_tinybox_frame_monitor(self):
        from tinybox import framemon
        from tinybox.ax25 import frame as ax
        e = framemon.entry(ax.ui_frame("TX0W84", "OM4MO-9", self.INFO).encode(), tx=False, mycall="OE3GAS-1")
        self.assertEqual(e["aprs"]["dest"]["mode"], "payload")
        e = framemon.entry(ax.ui_frame("ID", "OE3GAS-1", b"TinyBox").encode(), tx=True, mycall="OE3GAS-1")
        self.assertNotIn("aprs", e)


if __name__ == "__main__":
    unittest.main()
