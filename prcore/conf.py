"""Config files of all programs: the shared base (Refactoring R7).

A section can be declared instead of read by hand: a dataclass whose fields say their
key, default, allowed range and whether RELOAD takes them over - in one place, so the
default no longer lives twice (dataclass and loader) and RELOAD knows it by itself.

    @dataclass
    class MailboxCfg:
        max_users: int = setting(3, lo=1, hi=50, live=True)
        welcome_text: str = setting("", live=True)

    mailbox = load_section(cp, "mailbox", MailboxCfg)
    live_fields(MailboxCfg)   ->  {"max_users", "welcome_text"}

Types: bool, int, float, str (from the annotation). Sections with special rules
(lists, calls, files) keep their own code next to it; load_section can run first and
the rest is checked after it.
"""

from __future__ import annotations

import configparser
import dataclasses
import typing
from typing import Any, Callable


class ConfigError(Exception):
    """A config file is missing or a value is not allowed - the message names
    [section] key. Every program raises this one (tinybox, tbclient, kisshub, dxfeed)."""


def setting(default: Any, *, key: str | None = None, lo: float | None = None,
            hi: float | None = None, live: bool = False,
            check: Callable[[Any], str | None] | None = None) -> Any:
    """A declared field: key in the file (default: the field name), range lo..hi,
    live = RELOAD takes it over, check(value) -> error text or None."""
    return dataclasses.field(default=default, metadata={
        "key": key, "lo": lo, "hi": hi, "live": live, "check": check})


def get_value(cp: configparser.ConfigParser, sec: str, key: str, default: Any,
              kind: type = str) -> Any:
    try:
        if kind is bool:
            return cp.getboolean(sec, key, fallback=default)
        if kind is int:
            return cp.getint(sec, key, fallback=default)
        if kind is float:
            return cp.getfloat(sec, key, fallback=default)
        return cp.get(sec, key, fallback=default)
    except ValueError as exc:
        raise ConfigError(f"[{sec}] {key}: {exc}") from None


def check_range(sec: str, key: str, value: float, lo: float, hi: float) -> None:
    if not lo <= value <= hi:
        raise ConfigError(f"[{sec}] {key}: {value} must be between {lo} and {hi}")


def check_port(sec: str, key: str, port: int) -> None:
    if not 1 <= port <= 65535:
        raise ConfigError(f"[{sec}] {key}: {port} is not a valid TCP port")


def _kind(hint: Any) -> type:
    for t in (bool, int, float, str):
        if hint is t:
            return t
    raise TypeError(f"no declared setting of type {hint!r}")


def load_section(cp: configparser.ConfigParser, sec: str, cls: type) -> Any:
    """An instance of the declared dataclass cls with the values of [sec]."""
    hints = typing.get_type_hints(cls)
    values = {}
    for f in dataclasses.fields(cls):
        md = f.metadata
        if "live" not in md:                      # not declared with setting()
            continue
        key = md["key"] or f.name
        value = get_value(cp, sec, key, f.default, _kind(hints[f.name]))
        if md["lo"] is not None and md["hi"] is not None:
            check_range(sec, key, value, md["lo"], md["hi"])
        if md["check"] is not None and (err := md["check"](value)):
            raise ConfigError(f"[{sec}] {key}: {err}")
        values[f.name] = value
    return cls(**values)


def live_fields(cls: type) -> set[str]:
    """The fields RELOAD takes over."""
    return {f.name for f in dataclasses.fields(cls) if f.metadata.get("live")}


def declared(cls: type) -> list[tuple[str, Any, Any, Any, bool]]:
    """(key, default, lo, hi, live) of every declared field - for docs and the installer."""
    return [(f.metadata["key"] or f.name, f.default, f.metadata["lo"], f.metadata["hi"],
             f.metadata["live"]) for f in dataclasses.fields(cls) if "live" in f.metadata]
