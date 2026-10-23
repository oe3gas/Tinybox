"""Build the DXCC list (enums.dxcc) of the brocast dictionary.

The number of every entry is the ADIF DXCC entity code (ARRL), so logs,
evaluations and brocast pages share one numbering. Sources (all public):

    cty.xml    Club Log country file: every entity (also deleted ones) with
               ADIF code, Club Log prefix, continent, CQ zone
    cty.plist  AD1C country file (country-files.com): the primary prefix and
               the entity name as dxfeed sees them in cty.dat, ITU zone
    dxcc.json  k0swe/dxcc-json (Apache 2.0, from the ARRL list): names of
               entities that are missing in cty.plist, deleted flag

Entry:   432: { name: "7P", en: "Lesotho", cont: AF, cq: 38, itu: 57 }
    name  AD1C primary prefix in upper case (what dxfeed finds in cty.dat)
    cl    Club Log prefix, only where it differs (Most Wanted list: 1A0, IS0 ...)
    del   true for deleted entities (name "del<code>", never sent by dxfeed)

Usage:  python tools/build_dxcc.py cty.xml cty.plist dxcc.json > dxcc.yaml
then paste the output under "enums:" in brocast-core.yaml (new dictionary
version only: entries are never renumbered or reused).
"""

from __future__ import annotations

import json
import plistlib
import sys
import xml.etree.ElementTree as ET

# Entities missing in the cty.plist used for version 4 (23.10.2026): primary
# prefix and name as AD1C writes them in cty.dat (dxfeed also matches by name,
# and "python -m dxfeed status" lists cty.dat entities without a DXCC number).
AD1C_MISSING = {
    24: ("3Y/B", "Bouvet"), 36: ("FO/C", "Clipperton Island"),
    111: ("VK0H", "Heard Island"), 117: ("4U1I", "ITU HQ"),
    153: ("VK0M", "Macquarie Island"), 177: ("JD/M", "Minami Torishima"),
    180: ("SV/A", "Mount Athos"), 191: ("E5/N", "N. Cook Islands"),
    199: ("3Y/P", "Peter 1 Island"), 238: ("VP8/O", "South Orkney Islands"),
    289: ("4U1U", "United Nations HQ"), 460: ("3D2/R", "Rotuma Island"),
    489: ("3D2/C", "Conway Reef"), 506: ("BS7", "Scarborough Reef"),
    508: ("FO/A", "Austral Islands"), 509: ("FO/M", "Marquesas Islands"),
    512: ("FK/C", "Chesterfield Islands"), 513: ("VP6/D", "Ducie Island"),
    515: ("KH8/S", "Swains Island"),
}


def q(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def build(cty_xml: str, cty_plist: str, dxcc_json: str) -> list[str]:
    root = ET.parse(cty_xml).getroot()
    ns = {"c": root.tag.split("}")[0].strip("{")}
    clublog = [{c.tag.split("}")[1]: c.text for c in e} for e in root.find("c:entities", ns)]
    with open(cty_plist, "rb") as fh:
        plist = plistlib.load(fh)
    ad1c: dict[int, list[tuple]] = {}
    for v in plist.values():
        if v.get("ExactCallsign"):
            continue
        row = (v["Prefix"].upper(), v["Country"], v["Continent"], v["CQZone"], v["ITUZone"])
        rows = ad1c.setdefault(v["ADIF"], [])
        if row[0] not in [r[0] for r in rows]:
            rows.append(row)
    with open(dxcc_json, encoding="utf-8") as fh:
        arrl = {x["entityCode"]: x for x in json.load(fh)["dxcc"]}

    out = ["  dxcc:             # ab Version 4: DXCC-Gebiete, Nummer = ADIF-Code (ARRL);"
           " erzeugt mit tools/build_dxcc.py"]
    for e in sorted(clublog, key=lambda e: int(e["adif"])):
        code = int(e["adif"])
        j = arrl.get(code, {})
        if e["deleted"] == "TRUE":
            name = j.get("name") or e["name"].title()
            out.append(f"    {code}: {{ name: del{code}, en: {q(name)}, del: true }}")
            continue
        cands = ad1c.get(code, [])
        if len(cands) > 1:      # a WAE entity shares the code (IT9 Sicily): keep the DXCC one
            want = (j.get("name") or e["name"]).lower()
            cands = [c for c in cands if c[1].lower() == want] or cands[:1]
        if cands:
            pfx, name, cont, cq, itu = cands[0]
        else:
            pfx, name = AD1C_MISSING.get(code, (e["prefix"].upper(), j.get("name") or e["name"].title()))
            cont = e["cont"]
            cq = int(e["cqz"]) if e.get("cqz") else (j.get("cq") or [None])[0]
            itu = (j.get("itu") or [None])[0]
        parts = [f"name: {q(pfx)}", f"en: {q(name)}", f"cont: {cont}"]
        if cq:
            parts.append(f"cq: {cq}")
        if itu:
            parts.append(f"itu: {itu}")
        if e["prefix"].upper() != pfx:
            parts.append(f"cl: {q(e['prefix'].upper())}")
        out.append(f"    {code}: {{ {', '.join(parts)} }}")
    return out


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    print("\n".join(build(*sys.argv[1:])))
