"""Split a page into subpages that each fit into one frame (spec: "Unterseiten").

Rules:
  * a page that fits stays one page, without `sub`
  * otherwise blocks are packed greedily; a text block that is too long
    for one frame is cut at sentence or word boundaries
  * every subpage repeats the envelope (title, typ, cat, exp ...), so each
    one can be shown on its own; `txt` and `dat` stay on subpage 1
"""

from __future__ import annotations

import re
from typing import Any

import cbor2

from .codec import MAX_PAGE_BYTES, BrocastError, Codec

SUB_PLACEHOLDER = [255, 255]          # worst case size of `sub` while packing
FIRST_ONLY = ("txt", "dat", "src")
SENTENCE_END = re.compile(r"[.!?:;]\s")
# "Rel. Feuchte", "Max. Böe", "z. B.", "ca. 5": a dot after a known abbreviation
# or a single letter is no sentence end
ABBREVIATION = re.compile(
    r"(?:^|[\s(])(?:[A-Za-zÄÖÜäöü]|rel|max|min|ca|bzw|inkl|exkl|evtl|ggf|usw|vgl|nr|"
    r"str|tel|dr|mag|ing|abs|geb|jh|mio|mrd|std|sek|temp|stk|zzgl|abt|anm|bspw|"
    r"[a-zäöü]\.[a-zäöü])\.$", re.IGNORECASE)
MIN_TEXT_ROOM = 40                    # bytes; less is not worth a text fragment


class TooLargeError(BrocastError):
    """Content does not fit into the allowed number of subpages."""


def _size(codec: Codec, page: dict[str, Any]) -> int:
    return len(cbor2.dumps(codec.to_wire(page), canonical=True))


def _cut(text: str, max_bytes: int, sentence_only: bool = False) -> tuple[str, str]:
    """Longest head of text with at most max_bytes UTF-8, cut at a nice boundary.

    Order of preference: line break (keeps tables and lists intact and the
    indentation of the next line), sentence end, space, anywhere.
    sentence_only: only cut at a line break or sentence end; returns ("", text)
    if none fits.
    """
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return text, ""
    head = raw[:max_bytes].decode("utf-8", errors="ignore")
    nl = head.rfind("\n")
    if nl > 0 and (sentence_only or nl >= len(head) * 0.25):
        return head[:nl].rstrip(), text[nl + 1:]
    cut = 0
    for m in SENTENCE_END.finditer(head):
        if not ABBREVIATION.search(head[:m.start() + 1]):
            cut = m.end()
    if sentence_only:
        return (head[:cut].rstrip(), text[cut:].lstrip()) if cut else ("", text)
    if cut < len(head) * 0.25:                # no sentence end worth using
        space = head.rfind(" ")
        cut = space + 1 if space > len(head) * 0.3 else len(head)
    return head[:cut].rstrip(), text[cut:].lstrip()


def split(codec: Codec, page: dict[str, Any], max_bytes: int = MAX_PAGE_BYTES,
          max_subpages: int = 40,
          parts: list[list[dict[str, Any]]] | None = None) -> list[bytes]:
    """parts: thematic sections from the provider; each one starts a new
    subpage (and may need several). Without parts, blocks are packed freely."""
    page = {k: v for k, v in page.items() if k != "sub"}
    if parts is not None:
        parts = [list(p) for p in parts if p]
        if len(parts) <= 1:
            page = {**page, "blk": parts[0]} if parts else {k: v for k, v in page.items()
                                                            if k != "blk"}
            parts = None
    if parts is None:
        if _size(codec, page) <= max_bytes:
            return [codec.encode(page)]
        parts = [list(page.get("blk") or [])]

    first_base = {k: v for k, v in page.items() if k != "blk"}
    rest_base = {k: v for k, v in first_base.items() if k not in FIRST_ONLY}
    if _size(codec, {**first_base, "sub": SUB_PLACEHOLDER}) > max_bytes:
        raise TooLargeError("Umschlag mit txt/dat passt nicht in einen Frame")

    groups: list[list[dict[str, Any]]] = []

    def fits(group: list[dict[str, Any]], index: int) -> bool:
        base = first_base if index == 0 else rest_base
        return _size(codec, {**base, "sub": SUB_PLACEHOLDER, "blk": group}) <= max_bytes

    queue: list[dict[str, Any]] = []
    for part in parts:
        if len(groups) > max_subpages:
            break
        groups.append([])
        queue = list(part)
        _pack(codec, queue, groups, first_base, rest_base, fits, max_bytes, max_subpages)

    groups = [g for g in groups if g] or [[]]
    if queue or len(groups) > max_subpages:
        raise TooLargeError(f"mehr als {max_subpages} Unterseiten nötig")
    total = len(groups)
    out: list[bytes] = []
    for n, group in enumerate(groups, start=1):
        base = first_base if n == 1 else rest_base
        out.append(codec.encode({**base, "sub": [n, total], "blk": group}))
    return out


def _pack(codec, queue, groups, first_base, rest_base, fits, max_bytes, max_subpages) -> None:
    """Pack the blocks in queue into groups (the last group is the current one)."""
    while queue:
        block = queue.pop(0)
        current = groups[-1]
        if fits(current + [block], len(groups) - 1):
            current.append(block)
            continue
        # does not fit: fill the rest of this subpage with part of the text
        text = block.get("x")
        room = -1
        if isinstance(text, str) and text:
            base = first_base if len(groups) == 1 else rest_base
            probe = {**base, "sub": SUB_PLACEHOLDER, "blk": current + [{**block, "x": ""}]}
            room = max_bytes - _size(codec, probe) - 2     # 2: longer string header
        head, tail = "", text
        if room >= MIN_TEXT_ROOM:
            # in a page that already has content, only fill up with whole
            # sentences; an empty page may cut inside a (very long) sentence
            head, tail = _cut(text, room, sentence_only=bool(current))
        if head:
            current.append({**block, "x": head})
            if tail:
                queue.insert(0, {**block, "x": tail})
        elif current:                          # start a new subpage and retry
            queue.insert(0, block)
        else:
            raise TooLargeError(f"Block {block.get('k')!r} passt nicht in einen Frame")
        if queue:
            groups.append([])
        if len(groups) > max_subpages:
            break
