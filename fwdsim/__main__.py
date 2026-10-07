"""fwdsim command line.

    python -m fwdsim cases                          list the test cases
    python -m fwdsim run --stub                     all cases against a fwdsim stand-in
    python -m fwdsim run T04 T05 [--agw]            cases against the real TinyBox
    python -m fwdsim serve [--agw]                  OE3GAS waits for TinyBox to call
    python -m fwdsim call [--agw]                   OE3GAS calls TinyBox now
    python -m fwdsim send DL0XTC P OE1ABC @ OE3XTC.#NOE.AUT.EU "Subject" [-t text]
    python -m fwdsim list [CALL] | show CALL NR | reset

Options before the command: -c fwdsim.conf, -v (debug log).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from . import VERSION
from . import config as config_mod
from .harness import Harness
from .runner import run_cases
from .scenarios import CASES
from .session import Faults
from .store import Store


def _store(cfg) -> Store:
    return Store(cfg.db_path)


def cmd_cases(args, cfg) -> int:
    for c in CASES.values():
        kind = "manual" if c.func is None else "auto"
        print(f"{c.id}  ab {c.since}  {kind:6}  {c.title}")
    return 0


async def _run(args, cfg) -> int:
    ids = [i.upper() for i in args.cases] or list(CASES)
    unknown = [i for i in ids if i not in CASES]
    if unknown:
        print(f"unknown case(s): {', '.join(unknown)}")
        return 2
    if args.tinybox_db:
        cfg.tinybox.db = args.tinybox_db
    store = Store(":memory:") if args.stub else _store(cfg)
    h = Harness(cfg, store, stub=args.stub, use_agw=args.agw)
    await h.start()
    try:
        _, failed, _ = await run_cases(h, ids)
    finally:
        await h.stop()
        store.close()
    return 1 if failed else 0


async def _serve(args, cfg) -> int:
    store = _store(cfg)
    h = Harness(cfg, store, stub=False, use_agw=args.agw)
    await h.start()
    print(f"{cfg.hop.call} waiting on TCP {cfg.tcp_listen_host}:{h.listen_port}"
          f"{' and AGW as ' + cfg.hop_ax25_call if args.agw else ''} - Ctrl+C to stop")
    try:
        while True:
            r = await h.incoming.get()
            print(f"session with {r.peer}: mode {r.mode}, sent {r.sent}, "
                  f"received {r.received}{', ERROR ' + r.error if r.error else ''}")
    finally:
        await h.stop()
        store.close()


async def _call(args, cfg) -> int:
    store = _store(cfg)
    h = Harness(cfg, store, stub=False, use_agw=args.agw)
    await h.start()
    try:
        r = await h.hop_calls_target(Faults(sid=args.sid) if args.sid else None)
    finally:
        await h.stop()
        store.close()
    print(f"mode {r.mode}, peer SID {r.peer_sid}, sent {r.sent}, received {r.received}"
          f"{', ERROR ' + r.error if r.error else ''}")
    return 1 if r.error else 0


def cmd_send(args, cfg) -> int:
    from .net import SimNet
    store = _store(cfg)
    net = SimNet(cfg, store)
    try:
        bbs = net.bbs(args.bbs)
    except KeyError as exc:
        print(exc)
        return 2
    m = bbs.create(args.type, args.to, args.at, args.subject, args.text.replace("\\n", "\n"))
    asyncio.run(net.settle())
    print(f"{bbs.call}: msg {m.id} {m.type} {m.to_call} @ {m.at_addr} BID {m.bid} queued")
    store.close()
    return 0


def cmd_list(args, cfg) -> int:
    from .net import SimNet
    store = _store(cfg)
    net = SimNet(cfg, store)
    boxes = [net.bbs(args.bbs)] if args.bbs else [net.hop, net.remote]
    for bbs in boxes:
        print(f"--- {bbs.call} ({bbs.haddr})")
        for m in bbs.messages():
            q = store.queue_states(bbs.call, m.id)
            print(f"{m.id:4} {m.type}{m.status} {m.to_call:8} @ {m.at_addr:24} "
                  f"{m.from_call:8} {m.bid:14} {m.subject[:30]}  {q or ''}")
    store.close()
    return 0


def cmd_show(args, cfg) -> int:
    from .net import SimNet
    store = _store(cfg)
    m = SimNet(cfg, store).bbs(args.bbs).store.get(args.bbs.upper(), args.nr)
    if m is None:
        print("no such message")
        return 1
    print(f"{m.type}{m.status} to {m.to_call} @ {m.at_addr} from {m.from_call} BID {m.bid}")
    print(f"Subject: {m.subject}")
    if m.note:
        print(f"Note: {m.note}")
    print(m.wire_text())
    store.close()
    return 0


def cmd_reset(args, cfg) -> int:
    store = _store(cfg)
    store.reset()
    store.close()
    print("fwdsim mailboxes cleared")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="fwdsim", description=f"fwdsim {VERSION}")
    p.add_argument("-c", "--config", default="fwdsim.conf")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("cases")
    r = sub.add_parser("run")
    r.add_argument("cases", nargs="*")
    r.add_argument("--stub", action="store_true", help="test against a fwdsim stand-in")
    r.add_argument("--agw", action="store_true", help="use Direwolf/AGW instead of TCP")
    r.add_argument("--tinybox-db", help="tinybox.db for read-only checks")
    s = sub.add_parser("serve")
    s.add_argument("--agw", action="store_true")
    c = sub.add_parser("call")
    c.add_argument("--agw", action="store_true")
    c.add_argument("--sid", help="send this SID instead of our own")
    se = sub.add_parser("send")
    se.add_argument("bbs")
    se.add_argument("type", choices=["P", "B", "p", "b"])
    se.add_argument("to")
    se.add_argument("at_sign", metavar="@", choices=["@"])
    se.add_argument("at")
    se.add_argument("subject")
    se.add_argument("-t", "--text", default="Test message from fwdsim.")
    li = sub.add_parser("list")
    li.add_argument("bbs", nargs="?")
    sh = sub.add_parser("show")
    sh.add_argument("bbs")
    sh.add_argument("nr", type=int)
    sub.add_parser("reset")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING,
                        format="%(asctime)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    cfg = config_mod.load(args.config)
    try:
        if args.cmd == "cases":
            return cmd_cases(args, cfg)
        if args.cmd == "run":
            return asyncio.run(_run(args, cfg))
        if args.cmd == "serve":
            return asyncio.run(_serve(args, cfg))
        if args.cmd == "call":
            return asyncio.run(_call(args, cfg))
        if args.cmd == "send":
            return cmd_send(args, cfg)
        if args.cmd == "list":
            return cmd_list(args, cfg)
        if args.cmd == "show":
            return cmd_show(args, cfg)
        if args.cmd == "reset":
            return cmd_reset(args, cfg)
    except KeyboardInterrupt:
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
