"""The test box as its own process, and the dummy radio.

Air: a KISS-TCP server on 127.0.0.1 that swallows every frame. The test box
(interface = kiss) and the client users (their radio port) connect to it
instead of kisshub or Direwolf - so nothing can reach a real transmitter. What
they send is counted: over AXUDP nothing between a user and the box may
appear here, only UI frames of the box (e.g. TBMAIL notices).

TestBox: `python -m tinybox -c <testbed>/tinybox.conf`, started from the repo,
its console output into runs/<time>/tinybox.out. Ready when its AXUDP port
listens.
"""

from __future__ import annotations

import asyncio
import os
import re
import socket
import subprocess
import sys
from collections import Counter
from pathlib import Path

from prcore import kiss
from prcore.ax25 import frame as ax

from .bed import REPO, Bed

READY_RE = re.compile(r"AXUDP listening on")
WEB_RE = re.compile(r"Web GUI login\S*\s+(http://\S+)")
ERROR_RE = re.compile(r"\bERROR\b|\bCRITICAL\b|Traceback|internal error", re.IGNORECASE)
WARN_RE = re.compile(r"\bWARNING\b")
START_TIMEOUT = 30


class Air:
    """The dummy radio (KISS-TCP). Counts frames by (source, destination, kind)."""

    def __init__(self, port: int) -> None:
        self.port = port
        self.frames: Counter = Counter()
        self.clients = 0
        self._server: asyncio.base_events.Server | None = None

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._conn, "127.0.0.1", self.port)

    async def _conn(self, r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
        dec = kiss.Decoder()
        self.clients += 1
        try:
            while chunk := await r.read(4096):
                for _port, cmd, data in dec.feed(chunk):
                    if cmd != kiss.CMD_DATA:
                        continue
                    try:
                        dest, src, _path, _rep = ax.peek(data)
                        kind = ax.Frame.decode(data).kind
                    except Exception:
                        dest, src, kind = "?", "?", "?"
                    self.frames[(src, dest, kind)] += 1
        except (ConnectionError, OSError):
            pass
        finally:
            self.clients -= 1
            w.close()

    def close(self) -> None:
        if self._server is not None:
            self._server.close()

    def summary(self, box_call: str) -> dict:
        """Frames on the dummy radio. 'user' = from or to a user: must be 0."""
        box = box_call.upper()
        user = sum(n for (s, d, k), n in self.frames.items() if k != "UI")
        return {"total": sum(self.frames.values()), "not_ui": user,
                "by": [{"src": s, "dest": d, "kind": k, "n": n}
                       for (s, d, k), n in sorted(self.frames.items())],
                "box_ui": sum(n for (s, d, k), n in self.frames.items()
                              if k == "UI" and s.upper() == box)}


def port_free(port: int, udp: bool = False) -> bool:
    kind = socket.SOCK_DGRAM if udp else socket.SOCK_STREAM
    with socket.socket(socket.AF_INET, kind) as s:
        if not udp and sys.platform != "win32":
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def busy_ports(bed: Bed, n_users: int) -> list[str]:
    """Ports of the testbed that something else uses (e.g. a box still running)."""
    out = []
    for name, port in (("air_port", bed.air_port), ("web_port", bed.web_port),
                       ("telnet_port", bed.telnet_port)):
        if not port_free(port):
            out.append(f"{name} {port}/tcp")
    if not port_free(bed.box_port, udp=True):
        out.append(f"box_port {bed.box_port}/udp")
    if not port_free(bed.channel_port, udp=True):
        out.append(f"channel_port {bed.channel_port}/udp")
    for call in bed.users[:n_users]:
        p = bed.port_of(call)
        if not port_free(p, udp=True):
            out.append(f"{call} {p}/udp")
    return out


class TestBox:
    """The TinyBox process of the testbed."""

    __test__ = False                      # not a unittest class

    def __init__(self, bed: Bed, out_path: Path, conf: Path | None = None) -> None:
        self.bed = bed
        self.conf = conf or bed.box_conf
        self.out_path = out_path
        self.proc: asyncio.subprocess.Process | None = None
        self.web_url = ""
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.n_errors = 0
        self.n_warnings = 0
        self.ready = asyncio.Event()
        self.died: int | None = None          # exit code if it stopped by itself
        self._stopping = False
        self._reader: asyncio.Task | None = None
        self._out = None

    async def start(self) -> None:
        env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8",
                   TINYBOX_LAUNCHER="")
        self._out = open(self.out_path, "w", encoding="utf-8")
        # own process group, so Ctrl+C in the console reaches only tbtest -
        # tbtest then writes its report and stops the box itself
        extra = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                 if sys.platform == "win32" else {"start_new_session": True})
        self.proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "tinybox", "-c", str(self.conf),
            cwd=str(REPO), env=env, stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, **extra)
        self._reader = asyncio.create_task(self._read())
        try:
            await asyncio.wait_for(self._wait_ready(), START_TIMEOUT)
        except asyncio.TimeoutError:
            raise RuntimeError(f"the test box did not start within {START_TIMEOUT} s - "
                               f"see {self.out_path}") from None

    async def _wait_ready(self) -> None:
        exited = asyncio.ensure_future(self.proc.wait())
        ready = asyncio.ensure_future(self.ready.wait())
        done, _ = await asyncio.wait({exited, ready}, return_when=asyncio.FIRST_COMPLETED)
        ready.cancel()
        if exited in done:
            await asyncio.sleep(0.2)                 # the last lines of output
            raise RuntimeError(f"the test box stopped at once (exit code "
                               f"{self.proc.returncode}) - see {self.out_path}")
        exited.cancel()

    async def _read(self) -> None:
        assert self.proc is not None and self.proc.stdout is not None
        while True:
            raw = await self.proc.stdout.readline()
            if not raw:
                if not self._stopping and self.ready.is_set():
                    self.died = await self.proc.wait()
                break
            line = raw.decode("utf-8", "replace").rstrip()
            self._out.write(line + "\n")
            self._out.flush()
            if READY_RE.search(line):
                self.ready.set()
            m = WEB_RE.search(line)
            if m:
                self.web_url = m.group(1)
                continue                             # the login token stays in the file only
            if ERROR_RE.search(line):
                self.n_errors += 1
                if len(self.errors) < 30:
                    self.errors.append(line)
            elif WARN_RE.search(line) and "config hint" not in line:
                self.n_warnings += 1
                if len(self.warnings) < 30:
                    self.warnings.append(line)

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.returncode is None

    async def stop(self) -> None:
        self._stopping = True
        if self.proc is None:
            return
        if self.proc.returncode is None:
            self.proc.terminate()
            try:
                await asyncio.wait_for(self.proc.wait(), 10)
            except asyncio.TimeoutError:
                self.proc.kill()
                await self.proc.wait()
        if self._reader is not None:
            try:
                await asyncio.wait_for(self._reader, 3)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._reader.cancel()
        if self._out is not None:
            self._out.close()
            self._out = None

