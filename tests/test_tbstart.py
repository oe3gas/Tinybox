"""CR138: control console (tbstart) - program list, supervisor, board."""

from __future__ import annotations

import socket
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from unittest import mock

from tbstart import board, programs
from tbstart import supervisor as sv

# a dummy program: listens on a port (argv[1], 0 = none), prints, exits cleanly on
# Ctrl+C/SIGINT, or with the code argv[2] after argv[3] seconds
DUMMY = textwrap.dedent("""
    import socket, sys, time
    port, code, after = int(sys.argv[1]), int(sys.argv[2]), float(sys.argv[3])
    if port:
        s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", port)); s.listen()
    print("[dummy] 10:00:00 hello", flush=True)
    try:
        t0 = time.time()
        while after < 0 or time.time() - t0 < after:
            time.sleep(0.05)
        print("[dummy] 10:00:01 [ERROR] crash", flush=True)
        print("Traceback (most recent call last):", file=sys.stderr, flush=True)
        print("  File x, line 1", file=sys.stderr, flush=True)
        sys.exit(code)
    except KeyboardInterrupt:
        print("[dummy] 10:00:02 clean stop", flush=True)
""")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait(cond, timeout: float = 10.0, sup: sv.Supervisor | None = None) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if sup is not None:
            sup.tick()
        if cond():
            return True
        time.sleep(0.05)
    return False


class ProgramListTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for d in ("tinybox", "tbclient", "kisshub", "brocast/brocast"):
            (self.root / d).mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_list_from_tbstart_conf_and_program_confs(self):
        (self.root / "tbstart.conf").write_text(
            "# comment\n[start]\ndirewolf = no\nkisshub = yes\nkisshub_profile = pk232\n"
            "tinybox = yes\nbrocast = no\n", encoding="utf-8")
        (self.root / "tbclient.conf").write_text(
            "[station]\nmycall = OE3GAS-12   # me\n[web]\nport = 7755\n", encoding="utf-8")
        (self.root / "brocast" / "brocastd.conf").write_text(
            "[brocastd]\nmode = station ; senden\n", encoding="utf-8")
        progs = {p.key: p for p in programs.programs(
            self.root, programs.start_settings(self.root), python="py")}
        self.assertNotIn("direwolf", progs)           # no exe, not active: not shown
        self.assertNotIn("dxfeed", progs)             # not installed (release package)
        self.assertEqual((progs["kisshub"].active, progs["kisshub"].role,
                          progs["kisshub"].port, progs["kisshub"].modem),
                         (True, "pk232", 8101, True))
        self.assertEqual(progs["tinybox"].missing, "tinybox.conf fehlt")
        self.assertEqual(progs["tinybox"].env, {"TINYBOX_LAUNCHER": "1"})
        cli = progs["tbclient"]
        self.assertEqual((cli.active, cli.port, cli.role, cli.url, cli.missing),
                         (True, 7755, "OE3GAS-12", "http://127.0.0.1:7755/", ""))
        self.assertEqual(cli.cmd, ["py", "-m", "tbclient", "-c", "tbclient.conf"])
        bro = progs["brocast"]                        # one entry, station: no web port
        self.assertEqual((bro.role, bro.port, bro.active, bro.cwd.name),
                         ("Station", None, False, "brocast"))

    def test_direwolf_port_from_its_conf(self):
        dw = self.root / "dw"
        dw.mkdir()
        (dw / "direwolf-tinybox.exe").write_bytes(b"")
        (dw / "direwolf.conf").write_text("MYCALL X\nAGWPORT 8010\n", encoding="utf-8")
        s = dict(programs.start_settings(self.root), direwolf=True, direwolf_dir=str(dw))
        p = programs.programs(self.root, s)[0]
        self.assertEqual((p.key, p.port, p.modem, p.missing, p.cwd), ("direwolf", 8010, True, "", dw))

    def test_missing_direwolf_says_where_it_looked(self):
        s = dict(programs.start_settings(self.root), direwolf=True,
                 direwolf_dir=str(self.root / "direwolf"))
        dw = programs.programs(self.root, s)[0]
        self.assertEqual(dw.missing, "direwolf-tinybox.exe fehlt - k: Pfad einstellen")
        self.assertIn(str(self.root / "direwolf" / "direwolf-tinybox.exe"), dw.detail)
        sup = sv.Supervisor([dw])
        sup.start_all(first=True)
        self.assertEqual(sup.runs[0].state, sv.MISSING)
        self.assertTrue(any("gibt es nicht" in m[3] for m in sup.messages))

    def test_profile_only_for_this_run(self):
        s = programs.start_settings(self.root)        # no tbstart.conf: client only
        self.assertEqual((s["tbclient"], s["tinybox"], s["exists"]), (True, False, False))
        s4 = programs.apply_profile(s, "4")
        self.assertTrue(s4["tinybox"] and s4["brocast"])
        self.assertFalse(programs.apply_profile(s, "3")["tinybox"])
        self.assertEqual(programs.apply_profile(s, "x"), s)

    def test_set_active_keeps_the_rest(self):
        path = self.root / "tbstart.conf"
        path.write_text("# Einstellungen\n[start]\ndirewolf = yes   # modem\ntinybox = no\n",
                        encoding="utf-8")
        programs.set_active(self.root, "tinybox", True)
        programs.set_active(self.root, "dxfeed", True)
        text = path.read_text(encoding="utf-8")
        self.assertIn("# Einstellungen", text)
        self.assertIn("direwolf = yes   # modem", text)
        s = programs.start_settings(self.root)
        self.assertEqual((s["tinybox"], s["dxfeed"], s["direwolf"]), (True, True, True))


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "dummy.py").write_text(DUMMY, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def prog(self, key="tbclient", port=0, code=1, after=-1.0, modem=False, active=True):
        return programs.Program(key, key, key[:5], [sys.executable, "dummy.py", str(port),
                                                     str(code), str(after)],
                                self.dir, active, port or None, "Web", modem=modem)

    def test_start_running_clean_stop(self):
        port = free_port()
        sup = sv.Supervisor([self.prog(port=port)])
        run = sup.runs[0]
        sup.start_all(first=True)
        self.assertTrue(wait(lambda: run.state == sv.RUNNING, sup=sup))
        self.assertTrue(run.port_ok)
        sup.stop(run, wait=True)
        self.assertEqual(run.state, sv.STOPPED)
        self.assertTrue(wait(lambda: any("clean stop" in m[3] for m in sup.messages)),
                        "the program got SIGINT/Ctrl+Break, not a kill")

    def test_crash_restarts_then_gives_up(self):
        sup = sv.Supervisor([self.prog(after=0.1, code=1)])
        run = sup.runs[0]
        with mock.patch.object(sv, "RESTART_DELAY", 0.1), mock.patch.object(sv, "MAX_ATTEMPTS", 2):
            sup.start_all()
            self.assertTrue(wait(lambda: run.state == sv.FAILED, 15, sup=sup))
        self.assertIn("aufgegeben", run.note)
        self.assertEqual(len(run.errors), 3)                  # one block per run
        self.assertCountEqual(run.errors[-1][1],
                         ["[dummy] 10:00:01 [ERROR] crash", "Traceback (most recent call last):",
                          "  File x, line 1"])

    def test_tinybox_restart_code_starts_again_at_once(self):
        sup = sv.Supervisor([self.prog(key="tinybox", after=0.1, code=3)])
        run = sup.runs[0]
        sup.start_all()
        self.assertTrue(wait(lambda: any("TinyBox RESTART" in m[3] for m in sup.messages),
                             sup=sup))
        self.assertTrue(wait(lambda: run.alive(), sup=sup))
        self.assertEqual(run.attempts, 0)
        sup.stop(run, wait=True)

    def test_exit_0_and_config_error_are_not_restarted(self):
        sup = sv.Supervisor([self.prog(after=0.1, code=0), self.prog(key="x2", after=0.1, code=2)])
        sup.start_all()
        self.assertTrue(wait(lambda: sup.runs[0].state == sv.ENDED
                             and sup.runs[1].state == sv.FAILED, sup=sup))
        self.assertIn("Konfigurationsfehler", sup.runs[1].note)

    def test_others_wait_for_the_modem_port(self):
        port = free_port()
        sup = sv.Supervisor([self.prog(key="direwolf", port=port, modem=True),
                             self.prog(key="tinybox")])
        modem, box = sup.runs
        sup.start_all(first=True)
        self.assertEqual(box.state, sv.WAITING)
        self.assertTrue(wait(lambda: box.alive(), sup=sup))
        self.assertTrue(modem.port_ok)
        sup.stop_all()
        self.assertEqual((modem.state, box.state), (sv.STOPPED, sv.STOPPED))

    def test_stop_all_reports_every_program(self):
        """q / Ctrl+C: one line per program - ended (how, exit code) or not running."""
        port = free_port()
        sup = sv.Supervisor([self.prog(key="direwolf", port=port, modem=True),
                             self.prog(key="tinybox"), self.prog(key="brocast")])
        modem, box, bro = sup.runs
        sup.start(modem)
        sup.start(box)
        self.assertTrue(wait(lambda: modem.state == sv.RUNNING and box.state == sv.RUNNING,
                             sup=sup))
        lines: list[str] = []
        sup.stop_all(lines.append)
        text = "\n".join(lines)
        self.assertIn("brocast: lief nicht", text)
        self.assertIn("tinybox: wird beendet (PID", text)
        self.assertIn("tinybox: sauber beendet", text)
        self.assertIn("direwolf: sauber beendet", text)
        ends = [i for i, x in enumerate(lines) if "beendet (Exit" in x]
        self.assertLess(ends[0], ends[1])
        self.assertIn("tinybox", lines[ends[0]], "modem last")
        self.assertEqual((modem.state, box.state), (sv.STOPPED, sv.STOPPED))

    def test_port_in_use_is_external_and_missing_conf_is_shown(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            s.listen()
            p = self.prog(port=s.getsockname()[1])
            m = self.prog(key="tinybox")
            m.missing = "tinybox.conf fehlt"
            sup = sv.Supervisor([p, m])
            sup.start_all(first=True)
        self.assertEqual((sup.runs[0].state, sup.runs[0].proc), (sv.EXTERNAL, None))
        self.assertEqual((sup.runs[1].state, sup.runs[1].note), (sv.MISSING, "tinybox.conf fehlt"))

    def test_stdin_is_a_pipe_not_nul(self):
        """On Windows NUL is a console: TinyBox would run its sysop console on it."""
        sup = sv.Supervisor([self.prog()])
        with mock.patch.object(sv.subprocess, "Popen", side_effect=OSError("x")) as popen:
            sup.start(sup.runs[0])
        self.assertIs(popen.call_args.kwargs["stdin"], sv.subprocess.PIPE)

    def test_deactivate_stops(self):
        sup = sv.Supervisor([self.prog()])
        run = sup.runs[0]
        sup.start_all()
        self.assertTrue(wait(run.alive, sup=sup))
        sup.set_active(run, False)
        self.assertTrue(wait(lambda: run.state == sv.OFF, sup=sup))


class BoardTests(unittest.TestCase):
    def sup(self):
        progs = [programs.Program(k, n, k[:5], ["x"], Path("."), a, port, "Web", role)
                 for k, n, a, port, role in (("direwolf", "Direwolf", True, 8000, "Modem"),
                                             ("tinybox", "TinyBox", True, 8080, "OE3XHU"),
                                             ("brocast", "brocastd", False, None, "Listener"))]
        sup = sv.Supervisor(progs)
        r = sup.runs[1]
        for i, t in enumerate(("[tinyb] 11:00:00 one", "[tinyb] 11:00:01 [ERROR] first",
                               "  detail", "[tinyb] 11:00:02 two",
                               "[tinyb] 11:00:03 [ERROR] second")):
            sup.line(r, "out", t)
        sup.line(sup.runs[0], "err", "direwolf says something")
        return sup

    def test_every_line_has_the_window_width(self):
        sup = self.sup()
        ui = board.UI(selected=1)
        for w, h in ((80, 24), (120, 40), (200, 60)):
            lines = board.render(sup, ui, w, h, "PC1", "logs/x.log", "Neuer Stand")
            self.assertEqual({board.vlen(x) for x in lines}, {w}, (w, h))
            self.assertLessEqual(len(lines), h)
        text = "\n".join(board.ANSI.sub("", x) for x in board.render(sup, ui, 120, 40, "PC1"))
        self.assertIn("Filter: 2 TinyBox", text)
        self.assertIn("Letzter Fehler – 2 TinyBox (2 von 2)", text)
        self.assertIn("↑/↓ Fehler blättern", text)
        self.assertNotIn("direwolf says", text)               # filtered on TinyBox

    def test_up_down_page_through_the_error_blocks(self):
        sup, ui = self.sup(), board.UI(selected=1)
        self.assertEqual(board.error_block(sup, ui)[2], ["[tinyb] 11:00:03 [ERROR] second"])
        board.move_error(sup, ui, -1)
        self.assertEqual(board.error_block(sup, ui)[2],
                         ["[tinyb] 11:00:01 [ERROR] first", "  detail"])
        board.move_error(sup, ui, -1)                          # stays at the oldest
        self.assertEqual(board.error_block(sup, ui)[1], 0)
        board.move_error(sup, ui, +1)
        self.assertEqual(board.error_block(sup, ui)[1], 1)

    def test_without_selection_latest_error_and_lines_get_a_tag(self):
        sup, ui = self.sup(), board.UI()
        text = "\n".join(board.ANSI.sub("", x) for x in board.render(sup, ui, 120, 40, "PC1"))
        self.assertIn("[direw!] direwolf says something", text)
        self.assertIn("Letzter Fehler – 2 TinyBox", text)
        ui.only_errors = True
        text = "\n".join(board.ANSI.sub("", x) for x in board.render(sup, ui, 120, 40, "PC1"))
        self.assertNotIn("11:00:00 one", text)


class DirewolfProblemTests(unittest.TestCase):
    """CR139: Direwolf starts without the sound card / PTT port - say so."""

    START = ('"Microham" doesn\'t match any of the input devices.',
             '"Microham" doesn\'t match any of the output devices.',
             "Available audio input devices for receive (*=selected):",
             " *  3: Mikrofon (USB Audio CODEC )   (channel 0)",
             "ERROR can't open device COM20 for channel 0 PTT control.",
             "Channel 0: 1200 baud, AFSK 1200 & 2200 Hz, A+, 48000 sample rate, Tx AX.25.")

    def make(self):
        prog = programs.Program("direwolf", "Direwolf", "dwolf", ["x"], Path("."), True,
                                8000, "AGW", "Modem", modem=True)
        return sv.Supervisor([prog])

    def test_the_lines_direwolf_prints(self):
        self.assertEqual(sv.direwolf_problem(self.START[0]),
                         'Audio-Eingang "Microham" nicht gefunden - Windows-Standardgerät')
        self.assertEqual(sv.direwolf_problem(self.START[4]),
                         "PTT-Port COM20 lässt sich nicht öffnen - kein Senden")
        self.assertEqual(sv.direwolf_problem("Invalid output (transmit) audio device number 7."),
                         "Audio-Ausgang Nr. 7 gibt es nicht")
        self.assertIsNone(sv.direwolf_problem(self.START[5]))

    def test_warnings_error_block_and_board(self):
        sup = self.make()
        r = sup.runs[0]
        for t in self.START + self.START:                     # twice: only once each
            sup.line(r, "out", t)
        self.assertEqual(len(r.warnings), 3)
        warn = [m[3] for m in sup.messages if "[WARN]" in m[3]]
        self.assertEqual(len(warn), 3)
        self.assertIn("Direwolf: PTT-Port COM20", warn[-1])
        self.assertTrue(r.errors)                              # zone 3 shows the lines
        r.state = sv.RUNNING
        with mock.patch.object(sv.Run, "alive", return_value=True):
            row = board.row(r, False, time.monotonic())
            text = "\n".join(board.ANSI.sub("", x)
                             for x in board.render(sup, board.UI(only_errors=True), 160, 40, "PC1"))
        self.assertIn(board.YELLOW + "läuft ⚠", row)
        self.assertIn("PTT-Port COM20", board.ANSI.sub("", row))
        self.assertIn("[WARN] Direwolf: Audio-Ausgang", text)

    def test_only_direwolf_and_cleared_on_start(self):
        prog = programs.Program("tbclient", "TBClient", "tbcli", ["x"], Path("."), True)
        sup = sv.Supervisor([prog])
        sup.line(sup.runs[0], "out", self.START[4])
        self.assertEqual(sup.runs[0].warnings, [])
        sup = self.make()
        r = sup.runs[0]
        sup.line(r, "out", self.START[4])
        r.prog.cmd = [sys.executable, "-c", "pass"]
        sup.start(r)
        self.assertEqual(r.warnings, [])
        sup.stop(r, wait=True)


if __name__ == "__main__":
    unittest.main()
