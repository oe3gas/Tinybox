"""CR100: the client web GUI - own network only, no foreign host names, no foreign origin."""

from __future__ import annotations

import asyncio
import dataclasses
import tempfile
import unittest

from tbclient import webguard as g
from tbclient.core import ClientCore
from tbclient.web import WebServer
from tests.test_tbclient import client_cfg


class Peer(unittest.TestCase):
    def setUp(self):
        self.lan = g.parse_allow("lan")

    def test_own_network(self):
        for a in ("127.0.0.1", "10.0.0.5", "10.255.1.2", "172.16.0.1", "172.31.255.254",
                  "192.168.1.20", "169.254.3.4", "::1", "fd12::5", "fe80::1%eth0",
                  "::ffff:192.168.1.20", "::ffff:10.1.2.3"):
            self.assertTrue(g.peer_allowed(a, self.lan), a)

    def test_outside(self):
        for a in ("8.8.8.8", "172.32.0.1", "172.15.255.255", "44.1.2.3", "100.64.0.1",
                  "2001:db8::1", "::ffff:8.8.8.8", "", None, "junk"):
            self.assertFalse(g.peer_allowed(a, self.lan), a)

    def test_settings(self):
        self.assertIsNone(g.parse_allow("any"))
        local = g.parse_allow("local")
        self.assertTrue(g.peer_allowed("127.0.0.1", local))
        self.assertFalse(g.peer_allowed("192.168.1.2", local))
        ham = g.parse_allow("lan, 44.0.0.0/8")
        self.assertTrue(g.peer_allowed("44.143.1.2", ham))
        self.assertTrue(g.peer_allowed("10.0.0.1", ham))
        for bad in ("", "lan, nonsense", "300.0.0.0/8"):
            with self.assertRaises(g.GuardError):
                g.parse_allow(bad)


class Host(unittest.TestCase):
    def test_accepted(self):
        for h in ("127.0.0.1:7744", "192.168.1.20:7744", "10.0.0.7", "[fe80::1]:7744",
                  "[::1]", "localhost:7744", "PC1:7744", "pc1", "shark.local:7744",
                  "pc1.fritz.box", "pc1.lan", "pc1.home.arpa", None):
            self.assertTrue(g.host_allowed(h), h)

    def test_rebinding_names_refused(self):
        for h in ("evil.example.com", "rebind.it:7744", "192.168.1.20.nip.io", "", "a b",
                  "pc1.example.org"):
            self.assertFalse(g.host_allowed(h), h)

    def test_extra_names(self):
        self.assertTrue(g.host_allowed("box.oe3gas.at:7744", g.parse_hosts("box.oe3gas.at")))

    def test_origin(self):
        self.assertTrue(g.origin_allowed(None, "pc1:7744"))
        self.assertTrue(g.origin_allowed("http://pc1:7744", "pc1:7744"))
        self.assertTrue(g.origin_allowed("http://192.168.1.20:7744", "192.168.1.20:7744"))
        self.assertFalse(g.origin_allowed("http://evil.example.com", "192.168.1.20:7744"))
        self.assertFalse(g.origin_allowed("null", "pc1:7744"))


class Server(unittest.IsolatedAsyncioTestCase):
    async def serve(self, allow):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cfg = dataclasses.replace(client_cfg(tmp.name, web_host="127.0.0.1", web_port=0),
                                  web_allow=allow)
        server = await WebServer(ClientCore(cfg)).start()
        self.addAsyncCleanup(server.wait_closed)
        self.addCleanup(server.close)
        return server.sockets[0].getsockname()[1]

    async def http(self, port, method="GET", path="/", host="127.0.0.1:7744", extra=""):
        r, w = await asyncio.open_connection("127.0.0.1", port)
        data = b"{}" if method == "POST" else b""
        head = f"{method} {path} HTTP/1.1\r\nConnection: close\r\nContent-Length: {len(data)}\r\n"
        if host is not None:
            head += f"Host: {host}\r\n"
        if method == "POST":
            head += "Content-Type: application/json\r\nX-TBClient: 1\r\n"
        w.write((head + extra + "\r\n").encode() + data)
        raw = await r.read()
        w.close()
        return int(raw.split()[1])

    async def test_lan_and_host(self):
        port = await self.serve("lan")
        self.assertEqual(await self.http(port), 200)
        self.assertEqual(await self.http(port, host="pc1:7744"), 200)
        self.assertEqual(await self.http(port, host="evil.example.com"), 403)
        self.assertEqual(await self.http(port, "GET", "/api/state?since=-1",
                                         host="rebind.example.net"), 403)

    async def test_address_not_allowed(self):
        port = await self.serve("10.0.0.0/8")          # 127.0.0.1 is not in it
        with self.assertLogs("tbclient.web", "WARNING"):
            self.assertEqual(await self.http(port), 403)

    async def test_foreign_origin_on_post(self):
        port = await self.serve("lan")
        self.assertEqual(await self.http(port, "POST", "/api/mail/abort",
                                         extra="Origin: http://evil.example.com\r\n"), 403)
        self.assertNotEqual(await self.http(port, "POST", "/api/mail/abort",
                                            extra="Origin: http://127.0.0.1:7744\r\n"), 403)


if __name__ == "__main__":
    unittest.main()
