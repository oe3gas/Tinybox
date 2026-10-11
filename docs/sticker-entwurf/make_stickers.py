# TinyBox stickers (draft): writes the SVGs and vorschau.html. Run: python make_stickers.py
import os, html
OUT = os.path.dirname(os.path.abspath(__file__))   # SVGs land next to this script
F = "font-family=\"'Arial Black','Segoe UI Black',Impact,sans-serif\" font-weight=\"900\""
NAVY, BLUE, YEL, RED, GRN, ORA, PINK, GREY, SKY = "#1d2b3a", "#1f6fd1", "#ffc93c", "#e5484d", "#2e9b4f", "#f08c2e", "#e05a8a", "#8b95a1", "#bfe3ff"

def txt(x, y, s, size, fill=NAVY, stroke=None, sw=0, anchor="middle", extra=""):
    st = f' stroke="{stroke}" stroke-width="{sw}" paint-order="stroke" stroke-linejoin="round"' if stroke else ""
    return f'<text x="{x}" y="{y}" {F} font-size="{size}" fill="{fill}" text-anchor="{anchor}"{st} {extra}>{html.escape(s)}</text>'

def sticker(name, body, bg="#ffffff"):
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160" width="160" height="160">
<defs><filter id="sh" x="-10%" y="-10%" width="120%" height="125%"><feDropShadow dx="0" dy="3" stdDeviation="3" flood-opacity=".25"/></filter></defs>
<rect x="8" y="8" width="144" height="144" rx="30" fill="{bg}" stroke="#fff" stroke-width="6" filter="url(#sh)"/>
{body}
</svg>'''
    open(f"{OUT}/{name}.svg", "w").write(svg)

def waves(x, y, n=3, col=BLUE, r0=12, step=10, a0=-50, a1=50, w=4):
    import math
    out = []
    for i in range(n):
        r = r0 + i * step
        x1, y1 = x + r * math.cos(math.radians(a0)), y + r * math.sin(math.radians(a0))
        x2, y2 = x + r * math.cos(math.radians(a1)), y + r * math.sin(math.radians(a1))
        out.append(f'<path d="M{x1:.1f} {y1:.1f} A{r} {r} 0 0 1 {x2:.1f} {y2:.1f}" fill="none" stroke="{col}" stroke-width="{w}" stroke-linecap="round"/>')
    return "".join(out)

def face(cx, cy, r, mood="happy", fill=YEL):
    eyes = {
        "happy": f'<circle cx="{cx-r*.35}" cy="{cy-r*.15}" r="{r*.1}" fill="{NAVY}"/><circle cx="{cx+r*.35}" cy="{cy-r*.15}" r="{r*.1}" fill="{NAVY}"/>',
        "grumpy": f'<path d="M{cx-r*.55} {cy-r*.4} l{r*.35} {r*.15} M{cx+r*.55} {cy-r*.4} l-{r*.35} {r*.15}" stroke="{NAVY}" stroke-width="3" stroke-linecap="round"/><circle cx="{cx-r*.33}" cy="{cy-r*.08}" r="{r*.09}" fill="{NAVY}"/><circle cx="{cx+r*.33}" cy="{cy-r*.08}" r="{r*.09}" fill="{NAVY}"/>',
        "laugh": f'<path d="M{cx-r*.5} {cy-r*.15} q{r*.15} -{r*.25} {r*.3} 0 M{cx+r*.2} {cy-r*.15} q{r*.15} -{r*.25} {r*.3} 0" fill="none" stroke="{NAVY}" stroke-width="3" stroke-linecap="round"/>',
        "sleep": f'<path d="M{cx-r*.5} {cy-r*.1} q{r*.15} {r*.15} {r*.3} 0 M{cx+r*.2} {cy-r*.1} q{r*.15} {r*.15} {r*.3} 0" fill="none" stroke="{NAVY}" stroke-width="3" stroke-linecap="round"/>',
        "dead": f'<path d="M{cx-r*.5} {cy-r*.3} l{r*.25} {r*.25} m0 -{r*.25} l-{r*.25} {r*.25} M{cx+r*.25} {cy-r*.3} l{r*.25} {r*.25} m0 -{r*.25} l-{r*.25} {r*.25}" stroke="{NAVY}" stroke-width="3" stroke-linecap="round"/>',
        "sad": f'<circle cx="{cx-r*.35}" cy="{cy-r*.1}" r="{r*.1}" fill="{NAVY}"/><circle cx="{cx+r*.35}" cy="{cy-r*.1}" r="{r*.1}" fill="{NAVY}"/>',
    }[mood]
    mouth = {
        "happy": f'<path d="M{cx-r*.4} {cy+r*.2} q{r*.4} {r*.4} {r*.8} 0" fill="none" stroke="{NAVY}" stroke-width="3" stroke-linecap="round"/>',
        "grumpy": f'<path d="M{cx-r*.35} {cy+r*.45} q{r*.35} -{r*.3} {r*.7} 0" fill="none" stroke="{NAVY}" stroke-width="3" stroke-linecap="round"/>',
        "laugh": f'<path d="M{cx-r*.5} {cy+r*.1} h{r} q0 {r*.6} -{r*.5} {r*.6} q-{r*.5} 0 -{r*.5} -{r*.6}z" fill="{NAVY}"/><path d="M{cx-r*.3} {cy+r*.5} q{r*.3} -{r*.2} {r*.6} 0" fill="{RED}"/>',
        "sleep": f'<ellipse cx="{cx}" cy="{cy+r*.4}" rx="{r*.12}" ry="{r*.09}" fill="{NAVY}"/>',
        "dead": f'<path d="M{cx-r*.35} {cy+r*.4} h{r*.7}" stroke="{NAVY}" stroke-width="3" stroke-linecap="round"/><path d="M{cx+r*.05} {cy+r*.4} q0 {r*.3} {r*.18} {r*.3} q{r*.15} 0 {r*.12} -{r*.3}" fill="{PINK}"/>',
        "sad": f'<path d="M{cx-r*.35} {cy+r*.45} q{r*.35} -{r*.35} {r*.7} 0" fill="none" stroke="{NAVY}" stroke-width="3" stroke-linecap="round"/>',
    }[mood]
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{NAVY}" stroke-width="3"/>' + eyes + mouth

def mast(x, ytop, ybot, col=NAVY):
    return (f'<path d="M{x} {ybot} L{x} {ytop}" stroke="{col}" stroke-width="5" stroke-linecap="round"/>'
            f'<path d="M{x-12} {ybot} L{x} {ytop+25} L{x+12} {ybot}" fill="none" stroke="{col}" stroke-width="3" stroke-linejoin="round"/>'
            f'<circle cx="{x}" cy="{ytop}" r="5" fill="{RED}"/>')

def meter(cx, cy, angle, labels=("1", "9", "+"), col=NAVY, face_col="#fff8e1"):
    import math
    a = math.radians(angle)
    nx, ny = cx + 44 * math.cos(a), cy - 44 * math.sin(a)
    ticks = "".join(
        f'<path d="M{cx+50*math.cos(math.radians(t)):.1f} {cy-50*math.sin(math.radians(t)):.1f} L{cx+42*math.cos(math.radians(t)):.1f} {cy-42*math.sin(math.radians(t)):.1f}" stroke="{RED if t<55 else col}" stroke-width="3"/>'
        for t in range(160, 15, -18))
    return (f'<path d="M{cx-60} {cy+8} L{cx-60} {cy-20} A60 60 0 0 1 {cx+60} {cy-20} L{cx+60} {cy+8} Z" fill="{face_col}" stroke="{col}" stroke-width="3"/>'
            + ticks +
            f'<path d="M{cx} {cy} L{nx:.1f} {ny:.1f}" stroke="{RED}" stroke-width="4" stroke-linecap="round"/><circle cx="{cx}" cy="{cy}" r="6" fill="{col}"/>')

S = {}
# 1 CQ
S["cq"] = mast(36, 40, 128) + waves(36, 40, 3, BLUE, 14, 11, -60, 30) + \
    f'<path d="M62 70 h80 a8 8 0 0 1 8 8 v34 a8 8 0 0 1 -8 8 h-60 l-14 12 v-12 h-6 a8 8 0 0 1 -8 -8 v-34 a8 8 0 0 1 8 -8z" fill="{YEL}" stroke="{NAVY}" stroke-width="3"/>' + \
    txt(102, 92, "CQ CQ", 20) + txt(102, 114, "CQ", 20)
# 2 73
S["73"] = waves(80, 78, 3, "#ffffff", 46, 10, -150, -30, 4) + txt(80, 112, "73!", 64, YEL, NAVY, 8)
# 3 88
S["88"] = f'<path d="M80 136 C30 104 22 72 40 54 C56 38 74 46 80 60 C86 46 104 38 120 54 C138 72 130 104 80 136Z" fill="{PINK}" stroke="{NAVY}" stroke-width="3"/>' + txt(80, 104, "88", 46, "#fff", NAVY, 6)
# 4 QSL
S["qsl"] = f'<g transform="rotate(-8 80 80)"><rect x="22" y="40" width="116" height="76" rx="6" fill="#fff" stroke="{NAVY}" stroke-width="3"/>' \
    f'<rect x="106" y="48" width="24" height="28" fill="none" stroke="{RED}" stroke-width="2" stroke-dasharray="3 2"/>' \
    f'<path d="M32 92 h50 M32 102 h40" stroke="{GREY}" stroke-width="3"/>' + txt(62, 78, "QSL", 28, BLUE) + '</g>' + \
    f'<circle cx="118" cy="114" r="22" fill="{GRN}" stroke="#fff" stroke-width="4"/><path d="M107 114 l8 8 l14 -16" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>'
# 5 5/9+20
S["59"] = meter(80, 92, 30) + txt(80, 138, "5/9+20", 28, RED, "#fff", 5) + \
    f'<path d="M126 34 l4 10 l10 2 l-8 6 l2 10 l-8 -5 l-8 5 l2 -10 l-8 -6 l10 -2z" fill="{YEL}" stroke="{NAVY}" stroke-width="2"/>'
# 6 QRM
S["qrm"] = f'<path d="M18 42 l8 -8 l8 8 l8 -8 l8 8 M110 42 l8 -8 l8 8 l8 -8 l8 8 M16 70 l6 -6 l6 6 l6 -6 M120 70 l6 -6 l6 6 l6 -6" fill="none" stroke="{RED}" stroke-width="3" stroke-linecap="round"/>' + \
    face(80, 74, 32, "grumpy", ORA) + \
    f'<path d="M46 72 a34 34 0 0 1 68 0" fill="none" stroke="{NAVY}" stroke-width="6"/><rect x="38" y="64" width="12" height="22" rx="4" fill="{NAVY}"/><rect x="110" y="64" width="12" height="22" rx="4" fill="{NAVY}"/>' + \
    txt(80, 140, "QRM!", 30, RED, "#fff", 5)
# 7 QRT
S["qrt"] = f'<path d="M108 30 a26 26 0 1 0 22 40 a20 20 0 1 1 -22 -40z" fill="{YEL}"/>' + \
    '<circle cx="34" cy="34" r="2" fill="#fff"/><circle cx="58" cy="22" r="1.6" fill="#fff"/><circle cx="140" cy="96" r="1.6" fill="#fff"/>' + \
    face(64, 80, 26, "sleep", "#ffe0b5") + txt(100, 66, "z", 16, "#fff") + txt(112, 52, "Z", 20, "#fff") + \
    txt(80, 138, "QRT", 36, "#fff", NAVY, 6)
# 8 QRZ
S["qrz"] = f'<circle cx="66" cy="66" r="34" fill="{SKY}" stroke="{NAVY}" stroke-width="6"/><path d="M90 92 l30 30" stroke="{NAVY}" stroke-width="12" stroke-linecap="round"/>' + \
    txt(66, 78, "?", 40, BLUE) + txt(80, 144, "QRZ?", 28, NAVY, "#fff", 5)
# 9 HI HI
S["hihi"] = face(80, 66, 34, "laugh") + \
    f'<path d="M40 54 q-6 10 -2 16 M120 54 q6 10 2 16" fill="none" stroke="{BLUE}" stroke-width="3" stroke-linecap="round"/>' + \
    txt(80, 128, "HI HI", 30, BLUE, "#fff", 5) + \
    "".join(f'<circle cx="{x}" cy="143" r="2.6" fill="{NAVY}"/>' for x in (44, 51, 58, 65, 75, 82, 95, 102, 109, 116, 126, 133))
# 10 Pileup
cols = [ORA, PINK, GRN, BLUE, YEL, SKY, RED]
heads = ""
for i, (x, y) in enumerate([(30, 104), (52, 98), (74, 104), (96, 98), (118, 104), (40, 80), (63, 76), (86, 80), (108, 76), (130, 82)]):
    heads += f'<circle cx="{x}" cy="{y}" r="11" fill="{cols[i % len(cols)]}" stroke="{NAVY}" stroke-width="2"/>'
bubbles = "".join(f'<rect x="{x}" y="{y}" width="{w}" height="16" rx="6" fill="#fff" stroke="{NAVY}" stroke-width="2"/>' + txt(x + w / 2, y + 12, t, 10)
                  for x, y, w, t in [(18, 34, 40, "ME!"), (62, 24, 40, "QRZ"), (104, 36, 42, "DL1.."), (40, 52, 34, "OE?")])
S["pileup"] = bubbles + heads + f'<rect x="16" y="112" width="128" height="30" fill="{NAVY}" rx="6"/>' + txt(80, 135, "PILEUP", 24, YEL)
# 11 Magic smoke
S["smoke"] = f'<path d="M58 70 q-14 -8 -6 -22 q-6 -18 14 -20 q8 -14 24 -6 q18 -6 22 10 q16 4 8 20 q4 14 -12 18 q-10 10 -24 4 q-14 8 -26 -4z" fill="#c9ced4" stroke="{GREY}" stroke-width="2"/>' + \
    f'<rect x="34" y="82" width="92" height="40" rx="5" fill="{GREY}" stroke="{NAVY}" stroke-width="3"/><circle cx="54" cy="102" r="9" fill="{NAVY}"/><rect x="72" y="94" width="40" height="14" rx="2" fill="{RED}"/>' + \
    txt(92, 105, "PA", 11, "#fff") + txt(80, 145, "MAGIC SMOKE", 16, RED, "#fff", 4) + txt(84, 56, "puff!", 14, NAVY)
# 12 SWR 1:1
S["swr11"] = meter(80, 90, 160, face_col="#e8f7ec") + txt(80, 136, "SWR 1:1", 26, GRN, "#fff", 5) + \
    "".join(f'<path d="M{x} {y-8} l2 6 l6 2 l-6 2 l-2 6 l-2 -6 l-6 -2 l6 -2z" fill="{YEL}" stroke="{NAVY}" stroke-width="1.5"/>' for x, y in ((28, 32), (132, 30), (140, 56)))
# 13 SWR inf
S["swrinf"] = meter(80, 90, 18, face_col="#ffe9e9") + txt(80, 140, "SWR ∞", 30, RED, "#fff", 5) + \
    f'<path d="M132 30 q8 12 0 18 q-8 -6 0 -18z" fill="{SKY}" stroke="{BLUE}" stroke-width="2"/><path d="M24 40 l6 6 M24 46 l6 -6" stroke="{RED}" stroke-width="3"/>'
# 14 Dummy load
S["dummy"] = f'<rect x="44" y="40" width="72" height="72" rx="10" fill="{GREY}" stroke="{NAVY}" stroke-width="3"/>' + \
    "".join(f'<path d="M{x} 44 v64" stroke="{NAVY}" stroke-width="2" opacity=".35"/>' for x in range(54, 112, 10)) + \
    f'<rect x="72" y="26" width="16" height="16" rx="3" fill="{YEL}" stroke="{NAVY}" stroke-width="3"/>' + \
    face(80, 78, 20, "sleep", "#fff") + txt(80, 132, "DUMMY LOAD", 17, NAVY, "#fff", 4) + txt(80, 148, "50 Ω", 13, BLUE)
# 15 Band offen
S["open"] = f'<circle cx="80" cy="74" r="38" fill="{SKY}" stroke="{NAVY}" stroke-width="3"/>' + \
    f'<path d="M50 60 q12 -10 22 -2 q6 10 -4 16 q-12 4 -12 14 q-10 -6 -6 -28z M88 46 q14 0 20 12 q-10 4 -8 14 q-10 8 -16 -2 q4 -14 4 -24z M86 98 q12 -4 16 6 q-6 8 -16 4z" fill="{GRN}"/>' + \
    f'<path d="M24 114 Q80 20 136 114" fill="none" stroke="{ORA}" stroke-width="4" stroke-dasharray="7 5"/>' + \
    txt(80, 140, "BAND OFFEN!", 17, GRN, "#fff", 5)
# 16 Band tot
S["dead"] = f'<rect x="22" y="30" width="116" height="78" rx="8" fill="{NAVY}"/>' + \
    "".join(f'<path d="M{22+x} 30 v78" stroke="#2f4156" stroke-width="1"/>' for x in range(23, 116, 23)) + \
    f'<path d="M30 72 h22 l4 -10 l4 20 l4 -10 h72" fill="none" stroke="#5be38a" stroke-width="3"/>' + \
    face(112, 54, 0.001, "dead") + \
    f'<path d="M98 44 l10 10 m0 -10 l-10 10 M118 44 l10 10 m0 -10 l-10 10" stroke="{RED}" stroke-width="4" stroke-linecap="round"/>' + \
    txt(80, 138, "BAND TOT", 24, NAVY, "#fff", 5)
# 17 Lid (pot lid pun)
S["lid"] = f'<ellipse cx="80" cy="88" rx="56" ry="20" fill="#d7dbe0" stroke="{NAVY}" stroke-width="3"/><path d="M28 86 q52 -52 104 0" fill="#e8ebef" stroke="{NAVY}" stroke-width="3"/>' + \
    f'<rect x="66" y="42" width="28" height="12" rx="6" fill="{NAVY}"/><path d="M50 72 q8 -12 22 -16" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round"/>' + \
    txt(80, 140, "LID", 34, RED, "#fff", 5) + f'<path d="M120 32 l10 -8 M126 44 l12 -2" stroke="{RED}" stroke-width="3" stroke-linecap="round"/>'
# 18 Kaffee im Shack
S["coffee"] = f'<path d="M50 30 q-8 10 0 18 q8 8 0 18 M70 26 q-8 10 0 18 q8 8 0 18" fill="none" stroke="{GREY}" stroke-width="3" stroke-linecap="round"/>' + \
    f'<path d="M108 74 h8 a14 14 0 0 1 0 28 h-8" fill="none" stroke="{NAVY}" stroke-width="6"/><path d="M36 72 h74 v34 a20 20 0 0 1 -20 20 h-34 a20 20 0 0 1 -20 -20z" fill="{RED}" stroke="{NAVY}" stroke-width="3"/>' + \
    mast(118, 26, 60, NAVY) + waves(118, 26, 2, BLUE, 10, 8, -60, 20, 3) + \
    txt(73, 106, "QSO", 18, "#fff") + txt(80, 148, "KAFFEE", 18, NAVY, "#fff", 4)
# 19 Dipol im Baum
S["tree"] = f'<rect x="72" y="94" width="16" height="42" fill="#8a5a2b" stroke="{NAVY}" stroke-width="2"/>' + \
    f'<circle cx="80" cy="62" r="40" fill="{GRN}" stroke="{NAVY}" stroke-width="3"/><circle cx="56" cy="76" r="18" fill="#3fb562"/><circle cx="104" cy="74" r="18" fill="#3fb562"/>' + \
    f'<path d="M14 92 L46 78 q-6 -14 8 -12 q10 4 2 12 q-8 6 6 8 q18 0 30 -6 q8 -8 16 0 q6 8 -4 10 q-8 0 0 -8 L146 64" fill="none" stroke="{ORA}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>' + \
    f'<circle cx="68" cy="44" r="3.5" fill="{NAVY}"/><circle cx="92" cy="44" r="3.5" fill="{NAVY}"/><path d="M70 62 q10 -9 20 0" fill="none" stroke="{NAVY}" stroke-width="3" stroke-linecap="round"/>' + \
    f'<path d="M100 40 q4 8 0 11 q-4 -3 0 -11z" fill="{SKY}" stroke="{BLUE}" stroke-width="1.5"/>' + \
    txt(80, 150, "HÄNGT…", 18, NAVY, "#fff", 4)
# 20 Antennenbau
S["build"] = mast(58, 30, 112) + f'<path d="M40 38 h36 M44 50 h28" stroke="{NAVY}" stroke-width="4" stroke-linecap="round"/>' + \
    f'<path d="M92 78 a20 20 0 0 1 40 0 z" fill="{YEL}" stroke="{NAVY}" stroke-width="3"/><rect x="88" y="76" width="48" height="7" rx="3" fill="{YEL}" stroke="{NAVY}" stroke-width="3"/>' + \
    f'<path d="M104 100 l26 22" stroke="{GREY}" stroke-width="8" stroke-linecap="round"/><circle cx="102" cy="98" r="9" fill="none" stroke="{GREY}" stroke-width="6"/>' + \
    txt(80, 144, "ANTENNENBAU", 16, ORA, "#fff", 4)


# ---- Entwurf 2: Anpassungen + neue
S["cq"] = f'<path d="M30 32 h100 a14 14 0 0 1 14 14 v52 a14 14 0 0 1 -14 14 h-58 l-26 22 v-22 h-16 a14 14 0 0 1 -14 -14 v-52 a14 14 0 0 1 14 -14z" fill="{YEL}" stroke="{NAVY}" stroke-width="4" stroke-linejoin="round"/>' + \
    txt(80, 68, "CQ CQ", 30) + txt(80, 100, "CQ", 30)

S["smoke"] = (
    '<defs><radialGradient id="glow" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#ffd166"/><stop offset=".6" stop-color="#ff7a3c" stop-opacity=".7"/><stop offset="1" stop-color="#ff4d2e" stop-opacity="0"/></radialGradient>'
    '<linearGradient id="sm" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#5d646d"/><stop offset="1" stop-color="#c3c8ce"/></linearGradient></defs>'
    # smoke column: overlapping puffs, darker at the bottom
    + "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="url(#sm)" opacity="{o}"/>' for x, y, r, o in
              [(86, 70, 12, .95), (78, 58, 14, .9), (92, 50, 15, .85), (80, 38, 17, .8), (100, 32, 15, .75), (66, 30, 13, .7), (88, 22, 14, .6), (112, 22, 11, .5)])
    + f'<ellipse cx="86" cy="80" rx="22" ry="10" fill="url(#glow)"/>'
    # transceiver
    + f'<rect x="26" y="78" width="108" height="44" rx="6" fill="#3a4654" stroke="{NAVY}" stroke-width="3"/>'
    + f'<rect x="34" y="86" width="38" height="16" rx="2" fill="#9fe1cb" stroke="{NAVY}" stroke-width="2"/>' + txt(53, 98, "ERR", 11, NAVY)
    + f'<circle cx="104" cy="100" r="12" fill="#222c36" stroke="#8b95a1" stroke-width="2"/><path d="M104 100 l6 -7" stroke="#fff" stroke-width="2"/>'
    + f'<circle cx="40" cy="113" r="3.5" fill="{RED}"/><circle cx="52" cy="113" r="3.5" fill="#8b95a1"/><circle cx="64" cy="113" r="3.5" fill="#8b95a1"/>'
    + "".join(f'<path d="M{x} 79 v-4" stroke="{NAVY}" stroke-width="2"/>' for x in range(80, 100, 5))
    # crack and sparks
    + f'<path d="M86 79 l-4 8 l6 4 l-5 9" fill="none" stroke="{ORA}" stroke-width="2.5" stroke-linejoin="round"/>'
    + f'<path d="M118 66 l6 -10 l-2 8 l7 -2 l-8 11 l2 -7z" fill="{YEL}" stroke="{NAVY}" stroke-width="1.2"/>'
    + f'<path d="M48 64 l-6 -9 l7 5 l-1 -7 l5 10 l-6 -3z" fill="{YEL}" stroke="{NAVY}" stroke-width="1.2"/>'
    + txt(80, 145, "MAGIC SMOKE", 16, RED, "#fff", 4))

S["resistor"] = (
    f'<path d="M14 72 H42 M118 72 H146" stroke="{GREY}" stroke-width="5" stroke-linecap="round"/>'
    f'<path d="M42 54 q0 -10 10 -10 h12 q6 0 8 4 h16 q2 -4 8 -4 h12 q10 0 10 10 v36 q0 10 -10 10 h-12 q-6 0 -8 -4 h-16 q-2 4 -8 4 h-12 q-10 0 -10 -10z" fill="#e8c99a" stroke="{NAVY}" stroke-width="3"/>'
    + "".join(f'<rect x="{x}" y="{y}" width="7" height="{h}" fill="{c}"/>' for x, y, h, c in
              [(52, 45, 54, "#f2c230"), (64, 47, 50, "#8e44ad"), (95, 47, 50, RED), (108, 45, 54, "#c9a227")])
    + f'<circle cx="74" cy="66" r="3.5" fill="{NAVY}"/><circle cx="88" cy="66" r="3.5" fill="{NAVY}"/><path d="M73 78 q8 7 16 0" fill="none" stroke="{NAVY}" stroke-width="3" stroke-linecap="round"/>'
    + txt(80, 132, "OHM SWEET", 18, NAVY, "#fff", 4) + txt(80, 150, "OHM", 18, ORA, "#fff", 4))

S["transistor"] = (
    "".join(f'<path d="M{x} 96 V128" stroke="{GREY}" stroke-width="5" stroke-linecap="round"/>' for x in (64, 80, 96))
    + f'<path d="M50 96 V54 a30 30 0 0 1 60 0 V96 Z" fill="#2b2f36" stroke="{NAVY}" stroke-width="3"/>'
    + f'<rect x="50" y="88" width="60" height="8" fill="#3d434c"/>'
    + txt(80, 95, "NPN", 9, "#9aa4ad")
    + f'<circle cx="70" cy="56" r="7" fill="#fff"/><circle cx="90" cy="56" r="7" fill="#fff"/><circle cx="72" cy="57" r="3.5" fill="{NAVY}"/><circle cx="92" cy="57" r="3.5" fill="{NAVY}"/>'
    + f'<path d="M68 70 q12 12 24 0" fill="none" stroke="#fff" stroke-width="3.5" stroke-linecap="round"/>'
    # flexing arms
    + f'<path d="M50 70 q-18 -2 -20 -18" fill="none" stroke="#2b2f36" stroke-width="6" stroke-linecap="round"/><circle cx="30" cy="48" r="7" fill="#2b2f36"/>'
    + f'<path d="M110 70 q18 -2 20 -18" fill="none" stroke="#2b2f36" stroke-width="6" stroke-linecap="round"/><circle cx="130" cy="48" r="7" fill="#2b2f36"/>'
    + txt(80, 150, "GAIN!", 22, BLUE, "#fff", 5))

S["tube"] = (
    '<defs><radialGradient id="tg" cx=".5" cy=".55" r=".5"><stop offset="0" stop-color="#ffb347" stop-opacity=".9"/><stop offset=".55" stop-color="#ff7a3c" stop-opacity=".35"/><stop offset="1" stop-color="#ff7a3c" stop-opacity="0"/></radialGradient></defs>'
    + f'<circle cx="80" cy="66" r="52" fill="url(#tg)"/>'
    + f'<path d="M58 104 V52 a22 22 0 0 1 44 0 V104 Z" fill="#dff1ff" fill-opacity=".55" stroke="{NAVY}" stroke-width="3"/>'
    + f'<path d="M80 30 l0 -6" stroke="{NAVY}" stroke-width="3" stroke-linecap="round"/>'
    + f'<rect x="66" y="48" width="28" height="44" rx="3" fill="#8b95a1" fill-opacity=".55" stroke="#5d646d" stroke-width="2"/>'
    + f'<path d="M74 88 V60 q6 -8 12 0 V88" fill="none" stroke="#ff8c1a" stroke-width="4" stroke-linecap="round"/>'
    + f'<path d="M74 88 V60 q6 -8 12 0 V88" fill="none" stroke="#fff3b0" stroke-width="1.5" stroke-linecap="round"/>'
    + f'<path d="M64 52 q2 -14 12 -18" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity=".8"/>'
    + f'<rect x="54" y="104" width="52" height="14" rx="3" fill="#2b2f36" stroke="{NAVY}" stroke-width="2"/>'
    + "".join(f'<path d="M{x} 118 v8" stroke="{GREY}" stroke-width="3"/>' for x in (64, 74, 86, 96))
    + txt(80, 148, "WARMING UP", 17, ORA, "#fff", 4))

S["gonedx"] = (
    f'<path d="M80 18 L48 50 M80 18 L112 50" stroke="{NAVY}" stroke-width="3"/><circle cx="80" cy="18" r="5" fill="{GREY}" stroke="{NAVY}" stroke-width="2"/>'
    + f'<g transform="rotate(-4 80 86)"><rect x="22" y="48" width="116" height="78" rx="8" fill="#f6e3b4" stroke="#8a5a2b" stroke-width="4"/>'
    + f'<path d="M30 58 h100 M30 116 h100" stroke="#d9be86" stroke-width="2"/>'
    + txt(80, 82, "GONE", 26, "#8a5a2b") + txt(80, 110, "DXING", 26, RED) + '</g>'
    + f'<circle cx="128" cy="124" r="16" fill="{SKY}" stroke="{NAVY}" stroke-width="2.5"/>'
    + f'<path d="M118 118 q6 -6 10 0 q-2 6 -8 6z M130 112 q8 2 8 8 q-6 2 -8 -2z" fill="{GRN}"/>'
    + f'<path d="M114 132 Q128 98 142 132" fill="none" stroke="{ORA}" stroke-width="2.5" stroke-dasharray="4 3"/>')

S["onant"] = (
    f'<path d="M50 20 V128" stroke="{NAVY}" stroke-width="5" stroke-linecap="round"/>'
    + f'<path d="M16 34 H128" stroke="{NAVY}" stroke-width="4" stroke-linecap="round"/>'
    + "".join(f'<path d="M{x} {34-h} V{34+h}" stroke="{NAVY}" stroke-width="3" stroke-linecap="round"/>' for x, h in ((22, 14), (48, 12), (80, 11), (108, 10), (126, 9)))
    + f'<path d="M50 80 h-10 M50 100 h-10" stroke="{NAVY}" stroke-width="2"/>'
    # technician hugging the mast, waving
    + f'<path d="M62 70 Q70 92 64 112" stroke="{BLUE}" stroke-width="14" stroke-linecap="round" fill="none"/>'
    + f'<path d="M58 80 L50 84" stroke="{BLUE}" stroke-width="6" stroke-linecap="round"/>'
    + f'<path d="M68 78 Q86 70 92 54" stroke="{BLUE}" stroke-width="6" stroke-linecap="round" fill="none"/><circle cx="93" cy="51" r="5" fill="#ffd9b0" stroke="{NAVY}" stroke-width="1.5"/>'
    + f'<path d="M64 110 L54 124 M66 110 L74 126" stroke="{NAVY}" stroke-width="6" stroke-linecap="round"/>'
    + f'<circle cx="66" cy="58" r="11" fill="#ffd9b0" stroke="{NAVY}" stroke-width="2.5"/>'
    + f'<path d="M54 56 a12 12 0 0 1 24 0 z" fill="{YEL}" stroke="{NAVY}" stroke-width="2.5"/><rect x="51" y="54" width="30" height="4" rx="2" fill="{YEL}" stroke="{NAVY}" stroke-width="2"/>'
    + f'<circle cx="69" cy="62" r="1.8" fill="{NAVY}"/><path d="M64 66 q4 3 8 0" fill="none" stroke="{NAVY}" stroke-width="1.8" stroke-linecap="round"/>'
    + f'<path d="M98 44 q6 -2 8 -8 M100 52 q8 0 10 -4" fill="none" stroke="{GREY}" stroke-width="2" stroke-linecap="round"/>'
    + txt(80, 147, "ON MY ANTENNA", 15, ORA, "#fff", 4))

ORDER = ["cq", "73", "88", "qsl", "qrm", "qrt", "dummy", "open", "dead", "smoke",
         "resistor", "transistor", "tube", "gonedx", "onant"]
S = {k: S[k] for k in ORDER}
BG = {"73": BLUE, "qrt": "#2b3d63", "pileup": "#fff4dc", "dead": "#f1f3f5"}
for k, body in S.items():
    sticker(k, body, BG.get(k, "#ffffff"))
order = list(S)
cells = "".join(f'<figure><img src="{k}.svg"><figcaption>{k}</figcaption></figure>' for k in order)
open(os.path.join(OUT, "vorschau.html"), "w").write(f'''<!doctype html><meta charset=utf-8><style>
body{{margin:0;padding:20px;background:#eef1f4;font:13px system-ui}} .g{{display:grid;grid-template-columns:repeat(5,170px);gap:14px}}
figure{{margin:0;text-align:center}} img{{width:160px;height:160px}} figcaption{{color:#556;font-family:monospace}}</style>
<div class=g>{cells}</div>''')
print(len(S))
