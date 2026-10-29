"""The report of a run: from result.json to text (console and report.txt)."""

from __future__ import annotations

ORDER = ["conn", "disc", "send", "bull", "read", "final", "kill", "info", "chat",
         "chat_out", "img", "img_get"]
LABEL = {"conn": "connect+login", "disc": "disconnect (B)", "send": "send personal",
         "bull": "send bulletin", "read": "read + check", "final": "final read",
         "kill": "kill", "info": "other commands", "chat": "chat join",
         "chat_out": "chat leave", "img": "picture upload", "img_get": "picture fetch"}


def human(secs: float) -> str:
    secs = int(secs)
    if secs >= 3600 and secs % 3600 == 0:
        return f"{secs // 3600} h"
    if secs >= 60 and secs % 60 == 0:
        return f"{secs // 60} min"
    return f"{secs} s"


def _q(values: list[float]) -> tuple[str, str, str, str]:
    if not values:
        return "-", "-", "-", "-"
    v = sorted(values)
    p95 = v[min(len(v) - 1, int(0.95 * (len(v) - 1) + 0.5))]

    def ms(x: float) -> str:
        return f"{x * 1000:.0f}" if x < 10 else f"{x:.0f}s"
    return ms(v[0]), ms(sum(v) / len(v)), ms(p95), ms(v[-1])


def functions_table(recs: list[dict]) -> list[str]:
    funcs = sorted({r["func"] for r in recs},
                   key=lambda f: ORDER.index(f) if f in ORDER else 99)
    rows = [f"{'function':<17} {'n':>5} {'ok':>5} {'fail':>5} {'idle':>5}   "
            f"{'min':>6} {'avg':>6} {'p95':>6} {'max':>6}  (ms)"]
    for f in funcs:
        rs = [r for r in recs if r["func"] == f]
        ok = [r for r in rs if r["ok"]]
        busy = [r["secs"] for r in ok if not r["idle"]]
        mn, avg, p95, mx = _q(busy)
        rows.append(f"{LABEL.get(f, f):<17} {len(rs):>5} {len(ok):>5} {len(rs) - len(ok):>5} "
                    f"{sum(1 for r in ok if r['idle']):>5}   {mn:>6} {avg:>6} {p95:>6} {mx:>6}")
    return rows


def users_table(result: dict) -> list[str]:
    rows = [f"{'user':<10} {'type':<9} {'actions':>7} {'failed':>6}  last error"]
    for u in result["users"]:
        rs = [r for r in result["records"] if r["call"] == u["call"]]
        bad = [r for r in rs if not r["ok"]]
        kind = "terminal" if u["kind"] == "T" else "client"
        last = bad[-1]["func"] + ": " + bad[-1]["error"] if bad else ""
        rows.append(f"{u['call']:<10} {kind:<9} {len(rs):>7} {len(bad):>6}  {last[:70]}")
    return rows


def failures(result: dict) -> list[str]:
    """Why the run did not pass ([] = passed)."""
    v, why = result["verify"], []
    failed = [r for r in result["records"] if not r["ok"]]
    if failed:
        why.append(f"{len(failed)} action(s) failed")
    if v["private"]["corrupt"] or v["bulletins"]["corrupt"]:
        why.append("corrupt message text")
    if v["private"]["missing"]:
        why.append(f"{len(v['private']['missing'])} personal message(s) never arrived")
    if v["bulletins"]["missing"]:
        why.append(f"{len(v['bulletins']['missing'])} bulletin read(s) missing")
    if v["not_stored"]:
        why.append(f"{len(v['not_stored'])} message(s) not stored")
    if v["chat"]["missing"]:
        why.append(f"{len(v['chat']['missing'])} chat line(s) not delivered")
    if v["chat"]["echo_missing"]:
        why.append(f"{len(v['chat']['echo_missing'])} own chat line(s) without echo")
    if v["images"]["bad"]:
        why.append("picture differs")
    if result.get("air", {}).get("not_ui"):
        why.append("connected-mode frames on the dummy radio (must go over AXUDP)")
    if result["box"].get("died") is not None:
        why.append(f"the test box stopped during the run (exit code {result['box']['died']})")
    if result["box"]["errors"]:
        why.append(f"{result['box']['errors']} error line(s) in the box output")
    if result.get("aborted"):
        why.append("aborted")
    return why


def text(result: dict) -> str:
    v, o = result["verify"], result["options"]
    out = [f"tbtest {result['tbtest']} - run {result['run']}  ({result['started']}, "
           f"{human(result['secs'])}, seed {result['seed']})",
           f"box {result['box']['call']}, {len(result['users'])} users, functions "
           f"{','.join(o['funcs'])}"
           + (f", {o['rounds']} actions per user" if o.get("rounds") else ""),
           "", "Functions (times of the successful, non-idle actions):"]
    out += ["  " + r for r in functions_table(result["records"])]
    out += ["", "Users:"] + ["  " + r for r in users_table(result)]
    p, b, c, im = v["private"], v["bulletins"], v["chat"], v["images"]
    out += ["", "End to end:",
            f"  personal mail  stored {p['stored']}, arrived intact {p['ok']}, "
            f"corrupt {len(p['corrupt'])}, missing {len(p['missing'])}",
            f"  bulletins      stored {b['stored']}, reads intact {b['ok']} of "
            f"{b['expected_reads']}, corrupt {len(b['corrupt'])}, missing {len(b['missing'])}",
            f"  killed         {v['killed']} (each checked: gone from the box)"]
    d = c.get("delay_ms") or {}
    delay = (f", delay avg {d['avg']:.0f} ms, p95 {d['p95']:.0f} ms, max {d['max']:.0f} ms"
             if d else "")
    out += [f"  chat           {c['lines']} lines, delivered {c['delivered']} of "
            f"{c['expected']}, own echo missing {len(c['echo_missing'])}{delay}",
            f"  pictures       sent {im['sent']}, fetched by others {im['checked']}, "
            f"intact {im['ok']}"]
    if v["not_stored"]:
        out.append(f"  not stored     {', '.join(v['not_stored'][:8])}")
    for name, items in (("missing mail", p["missing"]), ("missing bulletin reads",
                                                          b["missing"]),
                        ("missing chat lines", c["missing"])):
        if items:
            out.append(f"  {name}: " + ", ".join(
                (f"{x[0]}->{x[1]}" if isinstance(x, (list, tuple)) else x) for x in items[:8])
                + (" ..." if len(items) > 8 else ""))
    air = result.get("air") or {}
    out += ["", f"Dummy radio:   {air.get('total', 0)} frame(s), {air.get('box_ui', 0)} UI frame(s)"
            f" of the box, {air.get('not_ui', 0)} connected-mode frame(s) (must be 0)"]
    box = result["box"]
    out.append(f"Test box:      {box['errors']} error line(s), {box['warnings']} warning(s) "
               f"- full output in {box['out']}")
    for line in box["error_lines"][:10]:
        out.append(f"  {line[:150]}")
    errors = [r for r in result["records"] if not r["ok"]]
    if errors:
        out += ["", "Failed actions (first 15):"]
        for r in errors[:15]:
            out.append(f"  {r['t']:>7.1f}s {r['call']}/{r['kind']} {r['func']}: {r['error'][:110]}")
    why = failures(result)
    if result.get("aborted"):
        out += ["", "RESULT: ABORTED - the end-to-end check is incomplete (no final read)"]
    else:
        out += ["", "RESULT: " + ("PASSED" if not why else "FAILED - " + "; ".join(why))]
    return "\n".join(out) + "\n"
