"""Login with the user's key, signed commands, certificates of the home BBS, trust
and LoTW (CR93, CR94, CR99, CR113).
Part of ClientCore (Refactoring R2): a mixin, so the methods keep working on the core's
state; tbclient/core.py puts the parts together."""

from __future__ import annotations

import logging
import time

from prcore import auth, tbproto
from prcore.calls import base_call

log = logging.getLogger(__name__)


class LoginMixin:
    def admin(self, command: str, refresh: str = "") -> bool:
        """CR94 (Variante B): one sysop console command at the TinyBox, signed. Only
        if the box granted ADM (the sysop, logged in with his released key).
        refresh: 'mail' or 'bulletins' changed (KILL, MOVE, COPY) - sync that
        when the answer is in."""
        command = " ".join(command.split())[:200]
        if "ADM" not in self.caps or not command or self.state != "online":
            return False
        if refresh in ("mail", "bulletins"):
            self._adm_refresh = refresh
        self.adm_log.append({"k": "cmd", "x": command, "t": int(time.time())})
        self.asking["adm"] = time.time()
        self.send_line(self.signed("//ADM " + command))
        self.changed()
        return True

    def signed(self, line: str, payload: list[str] | tuple[str, ...] = ()) -> str:
        """CR93 stage 2: a critical command (//SEND, //KILL, //SYNC k=, //PROF) with
        its number and signature - bound to this login, so an injected or recorded
        frame is refused. payload = the lines that follow (subject and text)."""
        if self._login is None:
            return line                       # no login with a key (older TinyBox)
        self._cmd_ctr += 1
        box, nonce = self._login
        sig = self.identity.sign_command(box, self.cfg.mycall, nonce, self._cmd_ctr, line,
                                         payload)
        return tbproto.with_signature(line, self._cmd_ctr, sig)

    # --- CR93 stage 3: the certificate of the home BBS ----------------------------------

    def _certs(self) -> dict[str, str]:
        certs = self.settings.get("certs")
        return certs if isinstance(certs, dict) else {}

    def _cert_due(self) -> bool:
        """At the home BBS: no certificate of it yet, or one that runs out soon."""
        box = self.auth.get("box") or self.target
        if self._login is None or base_call(box) != base_call(self.home):
            return False
        try:
            until = auth.parse_cert(self._certs().get(box.upper(), ""))["until"]
        except auth.AuthError:
            return True
        soon = time.strftime("%Y%m%d", time.gmtime(time.time() + auth.CERT_RENEW_DAYS * 86400))
        return until < soon

    def _store_cert(self, text: str) -> None:
        try:
            c = auth.parse_cert(text)
        except auth.AuthError:
            return                                   # '-': this box issues none
        box = (self.auth.get("box") or self.target).upper()
        if c["call"] != base_call(self.cfg.mycall) or c["pub"] != self.identity.pub \
                or c["issuer"] != box:
            log.warning("certificate from %s not for this key - ignored", box)
            return
        self.settings["certs"] = {**self._certs(), box: text}
        self.save_settings()
        self.console.append(f"*** certificate of {box} until {c['until'][:4]}-{c['until'][4:6]}-"
                            f"{c['until'][6:]}: other TinyBoxen that trust {box} let you log in")

    def _trust_due(self) -> bool:
        box = self.auth.get("box") or self.target
        if self._login is None or base_call(box) != base_call(self.home):
            return False
        tr = self.settings.get("trust")
        return not isinstance(tr, dict) or time.time() - tr.get("at", 0) > 86400

    def _store_trust(self, rest: str) -> None:
        """//TRUST box=key ...: from the home BBS (the first one is the home BBS itself)."""
        box = (self.auth.get("box") or self.target).upper()
        if self._login is None or base_call(box) != base_call(self.home):
            return
        keys = {}
        for part in rest.split()[:21]:
            name, eq, pub = part.partition("=")
            try:
                if eq and 3 <= len(name) <= 9:
                    auth.b64d(pub, 32)
                    keys[name.upper()] = pub
            except auth.AuthError:
                continue
        if box in keys:
            self.settings["trust"] = {"at": int(time.time()), "home": box, "keys": keys}
            self.save_settings()

    def trusted_issuer(self, issuer: str) -> bytes | None:
        """CR99: the key of a TinyBox whose certificates this client believes - its
        home BBS and the boxes that one trusts (fetched with //TRUST?)."""
        tr = self.settings.get("trust")
        pub = tr.get("keys", {}).get(issuer.upper()) if isinstance(tr, dict) else None
        try:
            return auth.b64d(pub, 32) if pub else None
        except auth.AuthError:
            return None

    # --- CR113: LoTW as anchor of trust -------------------------------------------------

    @property
    def _lotw_path(self):
        return self.cfg.data_dir / "lotw.json"

    def lotw_proof(self) -> dict | None:
        """The kept LoTW proof for the current key (None = none, or for another key)."""
        import json
        try:
            proof = json.loads(self._lotw_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(proof, dict) or proof.get("pub") != self.identity.pub:
            return None
        return proof

    def lotw_status(self) -> dict:
        from prcore import lotw
        out = {"available": lotw.available(), "call": base_call(self.cfg.mycall),
               "box": {k: v for k, v in self.lotw_box.items() if k != "asked"}}
        proof = self.lotw_proof()
        if proof:
            try:
                info = lotw.verify(proof, roots=None)
                out.update(state="ok", until=info["until"], dxcc=info["dxcc"], fp=info["fp"],
                           issuer=info["issuer"], date=proof.get("date", ""))
            except lotw.LotwError as exc:
                out.update(state="invalid", error=str(exc), until=proof.get("until", ""))
        else:
            out["state"] = "none"
        return out

    def lotw_sign(self, p12: bytes, password: str) -> dict:
        """Confirm the own key with the LoTW certificate: sign once, keep the proof.
        The .p12 and the password are only used here and not kept."""
        import json
        from prcore import lotw
        proof = lotw.sign_binding(p12, password, base_call(self.cfg.mycall), self.identity.pub)
        tmp = self._lotw_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(proof, indent=1), encoding="utf-8")
        tmp.replace(self._lotw_path)
        log.info("LoTW: key %s confirmed with the LoTW certificate of %s (until %s)",
                 self.identity.fp, proof["call"], proof["until"])
        if "LOTW" in self.caps and self.state == "online":
            self.lotw_box = {}
            self._lotw_ask()                         # the TinyBox learns it now
        self.changed()
        return self.lotw_status()

    # CR113 stage 2: the TinyBox learns it - once per key, then only //LOTW? at a login
    def _lotw_ask(self) -> None:
        if self.lotw_proof() is not None and self.lotw_box.get("asked") != self.target:
            self.lotw_box = {"asked": self.target, "state": "asking"}
            self.send_line("//LOTW?")

    def _lotw_answer(self, rest: str) -> None:
        proof = self.lotw_proof()
        word = rest.split(" ", 1)[0]
        box = self.auth.get("box") or self.target
        if rest.startswith("until=") and proof and rest[6:] >= proof.get("until", ""):
            self.lotw_box.update(state="ok", until=rest[6:], box=box)
        elif (rest == "-" or rest.startswith("until=")) and proof:
            self._lotw_send(proof)
        elif word == "more" and proof and not self.lotw_box.get("full"):
            self.lotw_box["full"] = True             # the box lacks an ARRL certificate
            self._lotw_send(proof, full=True)
        elif word == "off":
            self.lotw_box.update(state="off", box=box)
        elif word == "ok":
            until = rest.split("until=", 1)[1].split()[0] if "until=" in rest else ""
            self.lotw_box.update(state="ok", until=until, box=box)
            self.console.append(f"*** {box} knows now: your key is confirmed with LoTW (until {until})")
            if self.auth.get("state") == "ok":
                self.asking["cert"] = time.time()
                self.send_line("//CERT?")            # the certificate with the LoTW level
        elif word == "err":
            why = rest[4:].strip()
            self.lotw_box.update(state="err", error=why, box=box)
            self.console.append(f"*** {box} did not take your LoTW confirmation: {why}")
        self.changed()

    def _lotw_send(self, proof: dict, full: bool = False) -> None:
        """Normally only the callsign certificate (the box has the ARRL ones)."""
        from prcore import lotw
        text = lotw.wire_encode(proof, full)
        parts = [text[i:i + 200] for i in range(0, len(text), 200)]
        self.lotw_box["state"] = "sending"
        log.info("LoTW: sending the confirmation to %s (%d bytes, %d lines)", self.target,
                 len(text), len(parts))
        for i, chunk in enumerate(parts, 1):
            self.send_line(f"//LOTWP {i}/{len(parts)} {chunk}")

    def lotw_forget(self) -> None:
        try:
            self._lotw_path.unlink()
        except FileNotFoundError:
            pass
        self.changed()

    def own_cert(self) -> str:
        """The certificate of the home BBS for this key (for other TBClients, CR99)."""
        return self._cert_for("")

    def _cert_for(self, box: str) -> str:
        """At another TinyBox: the newest valid certificate of another box (home)."""
        today = time.strftime("%Y%m%d", time.gmtime())
        best = ("", "")
        for issuer, text in self._certs().items():
            if issuer == box.upper():
                continue
            try:
                c = auth.parse_cert(text)
            except auth.AuthError:
                continue
            if c["until"] >= today and c["pub"] == self.identity.pub and c["until"] > best[0]:
                best = (c["until"], text)
        return best[1]

    def _note_home_auth(self, state: str, reason: str = "") -> None:
        """CR104: the last login answer of the home BBS, kept for the settings page."""
        if base_call(self.auth.get("box") or self.target) != base_call(self.home):
            return
        new = {"state": state, "reason": reason, "at": int(time.time())}
        old = self.settings.get("auth_home") or {}
        if (old.get("state"), old.get("reason")) == (state, reason) and new["at"] - old.get("at", 0) < 3600:
            return                                  # same answer: no write per login
        self.settings["auth_home"] = new
        self.save_settings()

    # --- the lines of the TinyBox about the login (tbclient/core.py _CONTROL) -----------

    def _c_auth_ask(self, cmd: str, rest: str, line: str) -> None:
        """//AUTH? - CR93: log in with the user's key"""
        a = dict(x.split("=", 1) for x in rest.split() if "=" in x)
        nonce, box = a.get("n", ""), a.get("box", "") or self.target
        if not nonce or len(nonce) > 64:
            return
        self.auth.update(state="asking", box=box, reason="")
        self._login = (box, nonce)            # stage 2: signed commands of this login
        self._cmd_ctr = 0
        cert = self._cert_for(box)
        self.send_line(f"//AUTH sig={self.identity.sign_login(box, self.cfg.mycall, nonce)} "
                   f"pub={self.identity.pub} dev={self.identity.device}"
                   + (f" cert={cert}" if cert else ""))

    def _c_adm(self, cmd: str, rest: str, line: str) -> None:
        """//ADM>/ADMEND - CR94: answer of an admin command"""
        k = "out" if cmd == "ADM>" else "end"
        self.adm_log.append({"k": k, "x": rest, "t": int(time.time())})
        if k == "end":
            self.asking.pop("adm", None)
        if k == "end" and self._adm_refresh:
            scope, self._adm_refresh = self._adm_refresh, ""
            self.sync.start(scope)
        self.changed()

    def _c_trust(self, cmd: str, rest: str, line: str) -> None:
        """//TRUST - CR99: keys the home BBS trusts"""
        self.asking.pop("trust", None)
        self._store_trust(rest)

    def _c_cert(self, cmd: str, rest: str, line: str) -> None:
        """//CERT - stage 3: from the home BBS"""
        self.asking.pop("cert", None)
        self._store_cert(rest.strip())

    def _c_authwait(self, cmd: str, rest: str, line: str) -> None:
        self.auth.update(state="wait", reason="")
        self._note_home_auth("wait")
        box = base_call(self.auth["box"] or self.target)
        waited = self.settings.setdefault("auth_waited", [])     # CR133: "confirmed" later
        if box not in waited:
            waited.append(box)
            self.save_settings()
        self.console.append(f"*** {self.auth['box'] or self.target}: the sysop still has to confirm "
                            f"this client (protects your callsign) - give him the code {self.identity.fp}")
        self._lotw_ask()                     # CR113: LoTW may release it
        self.changed()

    def _c_lotw(self, cmd: str, rest: str, line: str) -> None:
        """//LOTW - CR113 stage 2"""
        self._lotw_answer(rest.strip())

    def _c_err(self, cmd: str, rest: str, line: str) -> None:
        if rest.startswith("auth"):
            why = rest[4:].strip() or "refused"
            self.auth.update(state="refused", reason=why)
            self._note_home_auth("refused", why)
            self.console.append(f"*** login with your key refused: {why}")
            self.changed()
            return
        self.console.append(line)
