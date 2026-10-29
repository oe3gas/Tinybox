"""tbtest command line.

    python -m tbtest init [--force]          create the testbed folder (tbtest.conf, tinybox.conf)
    python -m tbtest run [options]           a test run, see below
    python -m tbtest box                     only the test box and the channel (manual tests,
                                             your own client; Ctrl+C ends it)
    python -m tbtest report [RUN]            show the report of the last (or a given) run
    python -m tbtest reset                   delete the test box's database and the client data
    python -m tbtest funcs                   list the functions

run:
    -u, --users N        1-30 users (default 6)
    --terminal N         how many of them are terminal users (default: half, rest clients)
    -f, --funcs LIST     conn,send,bull,read,kill,info,chat,img or all (default all)
    -t, --time T         duration: 90s, 10m, 1h; 0 = until Ctrl+C (default: minutes of [air.<baud>])
    -r, --rounds N       actions per user (stops earlier than --time if reached)
    --air BAUD           bit rate of the channel: a section [air.<baud>] of tbtest.conf
                         (1200, 9600; 0 = no channel); default [radio] air_baud. All values
                         that depend on it (TXDELAY, AX.25, pauses, sizes) come from there
    --think A-B          pause between two actions in seconds (default: [air.<baud>] think)
    --stay A-B           time in a chat board in seconds (default: [air.<baud>] stay)
    --seed N             same seed = same choices and qualities (the timing still differs)
    --fresh              empty test box and client data before the run
    --no-final           no final read of everything still unread

Before the command: -D DIR (testbed folder; default TBTEST_DIR or ../tinybox-testbed).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import shutil
import sys
import time
from pathlib import Path

from . import VERSION, bed as bed_mod, report
from .box import Air, TestBox, busy_ports
from .runner import FUNCS, Options, Run


def parse_time(text: str) -> float:
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([smh]?)\s*", text.lower())
    if m is None:
        raise argparse.ArgumentTypeError(f"duration '{text}': e.g. 90s, 10m, 1h")
    return float(m.group(1)) * {"": 1, "s": 1, "m": 60, "h": 3600}[m.group(2)]


def parse_range(text: str) -> tuple[float, float]:
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(?:-\s*(\d+(?:\.\d+)?))?\s*", text)
    if m is None:
        raise argparse.ArgumentTypeError(f"'{text}': e.g. 2-10")
    a = float(m.group(1))
    b = float(m.group(2)) if m.group(2) else a
    if b < a:
        raise argparse.ArgumentTypeError(f"'{text}': the second number is smaller")
    return a, b


def parse_funcs(text: str) -> list[str]:
    words = [w.strip().lower() for w in text.replace(" ", ",").split(",") if w.strip()]
    if not words or words == ["all"]:
        return list(FUNCS)
    bad = [w for w in words if w not in FUNCS]
    if bad:
        raise argparse.ArgumentTypeError(f"unknown function(s): {', '.join(bad)} - "
                                         f"known: {', '.join(FUNCS)}, all")
    return [f for f in FUNCS if f in words]


def setup_logging(path: Path | None, verbose: bool) -> None:
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    if path is not None:
        h = logging.FileHandler(path, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(h)
    else:
        root.addHandler(logging.NullHandler())


def cmd_init(args) -> int:
    folder = bed_mod.resolve_dir(args.dir)
    try:
        bed, new = bed_mod.init(folder, force=args.force)
    except bed_mod.BedError as exc:
        print(f"[tbtest] {exc}")
        return 2
    print(f"[tbtest] testbed {folder}")
    print(f"  tbtest.conf  {'written' if new else 'kept (edited by you?) - --force writes it anew'}")
    print(f"  tinybox.conf written: box {bed.box_call}, AXUDP 127.0.0.1:{bed.box_port}, "
          f"web http://127.0.0.1:{bed.web_port}/, telnet {bed.telnet_port}")
    print(f"  users        {', '.join(bed.users)} (UDP {bed.user_port}-"
          f"{bed.user_port + len(bed.users) - 1})")
    print(f"  channel      127.0.0.1:{bed.channel_port}/udp, "
          + (f"{bed.air_baud} Bd simulated" if bed.air_baud else "no simulation"))
    print(f"  dummy radio  127.0.0.1:{bed.air_port} (swallows every frame)")
    for baud, a in sorted(bed.airs.items()):
        what = (f"{baud} Bd: TXDELAY {a.txdelay_ms} ms, PACLEN {a.paclen}, window {a.maxframe},"
                f" T1 {a.t1_sec:g} s, pauses {a.think[0]:g}-{a.think[1]:g} s" if baud
                else "no channel (fast function test)")
        mark = "  (default)" if baud == bed.air_baud else ""
        print(f"  --air {baud:<5} {what}{mark}")
    print(f"  your client  tbclient.bat -c {bed.guest_conf()}  (call {bed.guest_call}, "
          f"web http://127.0.0.1:{bed.guest_web}/)")
    print("Next: tbtest run   (or tbtest run -u 20 -t 30m, tbtest run -t 0 = until Ctrl+C)")
    return 0


def load_bed(args) -> bed_mod.Bed:
    bed = bed_mod.Bed.load(bed_mod.resolve_dir(args.dir))
    bed.check_box_conf()
    return bed


def wipe(bed: bed_mod.Bed) -> list[str]:
    gone = []
    for sub in ("data", "users"):
        p = bed.dir / sub
        if p.exists():
            shutil.rmtree(p)
            gone.append(sub)
        p.mkdir(parents=True, exist_ok=True)
    return gone


def cmd_run(args) -> int:
    try:
        bed = load_bed(args)
    except bed_mod.BedError as exc:
        print(f"[tbtest] {exc}")
        return 2
    if not 1 <= args.users <= len(bed.users):
        print(f"[tbtest] -u: 1 to {len(bed.users)} (users in tbtest.conf)")
        return 2
    if args.air is not None and args.air not in bed.airs:
        print(f"[tbtest] --air {args.air}: no [air.{args.air}] in tbtest.conf - known: "
              + ", ".join(str(b) for b in sorted(bed.airs)))
        return 2
    if args.terminal is not None and not 0 <= args.terminal <= args.users:
        print(f"[tbtest] --terminal: 0 to {args.users}")
        return 2
    opt = Options(users=args.users, terminals=args.terminal, funcs=args.funcs,
                  duration=args.time, rounds=args.rounds, think=args.think,
                  chat_stay=args.stay, seed=args.seed, timeout=args.timeout,
                  final=not args.no_final, fresh=args.fresh, air=args.air)
    if args.fresh:
        busy = busy_ports(bed, args.users)
        if busy:
            print("[tbtest] ports in use (is a test box still running?): " + ", ".join(busy))
            return 2
        wipe(bed)
    folder = bed.runs / time.strftime("%Y%m%d-%H%M%S")
    folder.mkdir(parents=True, exist_ok=True)
    setup_logging(folder / "tbtest.log", args.verbose)
    run = Run(bed, opt, folder)
    try:
        result = asyncio.run(run.run())
    except KeyboardInterrupt:
        print("[tbtest] aborted")
        if (folder / "report.txt").exists():
            print((folder / "report.txt").read_text(encoding="utf-8"))
        return 130
    except RuntimeError as exc:
        print(f"[tbtest] {exc}")
        return 2
    print()
    print(report.text(result), end="")
    print(f"report: {folder / 'report.txt'}")
    return 0 if not report.failures(result) else 1


def cmd_box(args) -> int:
    """Only the test box and the dummy radio - for manual tests (telnet, web GUI,
    a real tbclient with tbclient.conf pointing at it)."""
    try:
        bed = load_bed(args)
    except bed_mod.BedError as exc:
        print(f"[tbtest] {exc}")
        return 2
    if args.air is not None and args.air not in bed.airs:
        print(f"[tbtest] --air {args.air}: no [air.{args.air}] in tbtest.conf - known: "
              + ", ".join(str(b) for b in sorted(bed.airs)))
        return 2
    folder = bed.runs / (time.strftime("%Y%m%d-%H%M%S") + "-box")
    folder.mkdir(parents=True, exist_ok=True)
    setup_logging(folder / "tbtest.log", args.verbose)

    async def main() -> None:
        busy = busy_ports(bed, 0)
        if busy:
            raise RuntimeError("ports in use: " + ", ".join(busy))
        air = Air(bed.air_port)
        await air.start()
        run = Run(bed, Options(users=0, air=args.air), folder, quiet=True)
        channel = run.make_channel()
        await channel.start()
        conf = None
        if channel.air_baud != bed.air_baud:            # box --air: a conf for this run only
            conf = folder / "tinybox.conf"
            conf.write_text(bed.box_conf_text(channel.air_baud, absolute=True),
                            encoding="utf-8")
        box = TestBox(bed, folder / "tinybox.out", conf)
        try:
            await box.start()
            print(f"[tbtest] test box {bed.box_call} running - Ctrl+C ends it")
            print(f"  web GUI  {box.web_url}")
            print(f"  telnet   127.0.0.1:{bed.telnet_port}")
            print(f"  AXUDP    127.0.0.1:{bed.box_port}, channel 127.0.0.1:{bed.channel_port} ("
                  + (f"{channel.air_baud} Bd simulated)" if channel.radio else "no simulation)"))
            print(f"  your client  tbclient.bat -c {bed.guest_conf(channel.air_baud)}")
            print(f"  output   {folder / 'tinybox.out'}")
            while box.running:
                await asyncio.sleep(1)
        finally:
            await box.stop()
            air.close()
            channel.close()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[tbtest] test box stopped")
    except RuntimeError as exc:
        print(f"[tbtest] {exc}")
        return 2
    return 0


def cmd_report(args) -> int:
    try:
        bed = bed_mod.Bed.load(bed_mod.resolve_dir(args.dir))
    except bed_mod.BedError as exc:
        print(f"[tbtest] {exc}")
        return 2
    runs = sorted(p for p in bed.runs.glob("*") if (p / "report.txt").is_file())
    if args.run:
        runs = [p for p in runs if args.run in p.name]
    if not runs:
        print("[tbtest] no report found")
        return 1
    print(f"[tbtest] {runs[-1]}")
    print((runs[-1] / "report.txt").read_text(encoding="utf-8"), end="")
    return 0


def cmd_reset(args) -> int:
    try:
        bed = bed_mod.Bed.load(bed_mod.resolve_dir(args.dir))
    except bed_mod.BedError as exc:
        print(f"[tbtest] {exc}")
        return 2
    busy = busy_ports(bed, len(bed.users))
    if busy:
        print("[tbtest] ports in use (is a test box still running?): " + ", ".join(busy))
        return 2
    gone = wipe(bed)
    print(f"[tbtest] emptied: {', '.join(gone) or 'nothing to do'} (logs and runs are kept)")
    return 0


def cmd_funcs(args) -> int:
    for name, (who, _w, text) in FUNCS.items():
        kinds = {"TC": "terminal+client", "T": "terminal", "C": "client"}[who]
        print(f"  {name:<5} {kinds:<16} {text}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tbtest", description=f"TinyBox testbed {VERSION}",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__.split("\n\n", 1)[1])
    ap.add_argument("-D", "--dir", help="testbed folder (default TBTEST_DIR or "
                                        "../tinybox-testbed next to the repo)")
    ap.add_argument("-v", "--verbose", action="store_true", help="DEBUG in tbtest.log")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="create the testbed folder")
    p.add_argument("--force", action="store_true", help="write tbtest.conf anew too")
    p = sub.add_parser("run", help="a test run")
    p.add_argument("-u", "--users", type=int, default=6)
    p.add_argument("--terminal", type=int, default=None)
    p.add_argument("-f", "--funcs", type=parse_funcs, default=list(FUNCS))
    p.add_argument("-t", "--time", type=parse_time, default=None)
    p.add_argument("--air", type=int, default=None)
    p.add_argument("-r", "--rounds", type=int, default=0)
    p.add_argument("--think", type=parse_range, default=None)
    p.add_argument("--stay", type=parse_range, default=None)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--timeout", type=float, default=None, help=argparse.SUPPRESS)
    p.add_argument("--fresh", action="store_true")
    p.add_argument("--no-final", action="store_true")
    p = sub.add_parser("box", help="only the test box and the channel, for manual tests")
    p.add_argument("--air", type=int, default=None)
    p = sub.add_parser("report", help="report of the last run")
    p.add_argument("run", nargs="?", help="part of the run folder name, e.g. 20261029-1430")
    sub.add_parser("reset", help="delete the box database and the client data")
    sub.add_parser("funcs", help="list the functions")
    args = ap.parse_args(argv)
    return {"init": cmd_init, "run": cmd_run, "box": cmd_box, "report": cmd_report,
            "reset": cmd_reset, "funcs": cmd_funcs}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
