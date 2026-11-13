"""The scores of the games on this box (CR126): one table for all games, the
leaderboards, and what the sysop may delete.

Every game writes its finished games with record(); abandoned ones not. The
quote of a game:
    prefix   right tips / tips given
    contest  games won / games played
    chess    points / games played (a win 1, a draw 1/2)

Leaderboards for everybody, from the first game on, sorted by quote:
    //GAMES TOP          all games, the best 3 of each        (LB1)
    //GAMES TOP <game>   one game, the best 10 + one's own row (LB2)
answer only to the asker:
    //GAMES G <game> <games played> <players>
    //GAMES R <game> <rank> <call> <games> <quote %> [<hits>/<tries>]
    //GAMES ME <game> <rank> <call> <games> <quote %> [<hits>/<tries>]   own row outside the list
    //GAMES END
Terminal: /TOP [game] in a chat board.

Sysop console: GAMES (overview), GAMES CLEAR <game|ALL> [call] (shows what goes),
... CONFIRM (does it).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from prcore import auth

if TYPE_CHECKING:
    from .session import Session

GAMES = {"prefix": "Prefix raten", "contest": "CQ Contest", "chess": "Schach"}
QUOTE = {"prefix": "right tips", "contest": "games won", "chess": "points (win 1, draw 1/2)"}
TOP_ALL, TOP_ONE = 3, 10


def record(store, game: str, rows: list[dict]) -> None:
    """One finished game. rows: {"call", "wins", "draws", "hits", "tries", "asked"};
    the calls go in without SSID (two SSIDs of one call count as one player)."""
    merged: dict[str, dict] = {}
    for r in rows:
        base = auth.base(r["call"].upper())
        m = merged.setdefault(base, {"call": base})
        for k in ("wins", "draws", "hits", "tries", "asked"):
            m[k] = m.get(k, 0) + int(r.get(k, 0))
        if m.get("wins", 0) > 1:
            m["wins"] = 1
    if merged:
        store.game_record(game, list(merged.values()))


def quote(game: str, r: dict) -> int:
    if game == "prefix":
        return round(100 * r["hits"] / r["tries"]) if r["tries"] else 0
    if not r["games"]:
        return 0
    if game == "chess":
        return round(100 * (r["wins"] + r["draws"] / 2) / r["games"])
    return round(100 * r["wins"] / r["games"])


def ranked(store, game: str) -> list[dict]:
    rows = store.game_rows(game)
    for r in rows:
        r["quote"] = quote(game, r)
    rows.sort(key=lambda r: (-r["quote"], -r["games"], r["call"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def _row(game: str, r: dict) -> str:
    extra = f" {r['hits']}/{r['tries']}" if game == "prefix" else ""
    return f"{game} {r['rank']} {r['call']} {r['games']} {r['quote']}{extra}"


def board(store, game: str | None, me: str) -> list[str]:
    """The answer lines (without //GAMES) for LB1 (game None) or LB2."""
    me = auth.base(me.upper())
    out = []
    for g in ([game] if game else list(GAMES)):
        rows = ranked(store, g)
        out.append(f"G {g} {store.game_total(g)} {len(rows)}")
        n = TOP_ONE if game else TOP_ALL
        for r in rows[:n]:
            out.append("R " + _row(g, r))
        if game:
            mine = [r for r in rows[n:] if r["call"] == me]
            if mine:
                out.append("ME " + _row(g, mine[0]))
    out.append("END")
    return out


def top_command(s: "Session", rest: str) -> None:
    """//GAMES TOP [game] from a client."""
    p = rest.split()
    if not p or p[0].upper() != "TOP":
        s.out("//GAMES ERR bad")
        return
    game = p[1].lower() if len(p) > 1 else None
    if game is not None and game not in GAMES:
        s.out("//GAMES ERR game")
        return
    for line in board(s.service.store, game, s.call):
        s.out("//GAMES " + line)


def top_text(s: "Session", arg: str) -> None:
    """/TOP [game] for a terminal user."""
    game = arg.strip().lower() or None
    if game is not None and game not in GAMES:
        s.out("Games: " + ", ".join(GAMES) + " - /TOP or /TOP <game>")
        return
    store, lines = s.service.store, []
    for g in ([game] if game else list(GAMES)):
        rows = ranked(store, g)
        lines.append(f"{GAMES[g]}: {store.game_total(g)} games, {len(rows)} players "
                     f"(quote = {QUOTE[g]})")
        if not rows:
            lines.append("  no games yet")
        for r in rows[:TOP_ONE if game else TOP_ALL]:
            extra = f"  {r['hits']}/{r['tries']}" if g == "prefix" else ""
            lines.append(f"  {r['rank']:>2}. {r['call']:<9} {r['games']:>4} games {r['quote']:>4} %{extra}")
    s.out(*lines)


# --- sysop console -------------------------------------------------------------------

def console(store, arg: str) -> list[str]:
    """GAMES / GAMES CLEAR <game|ALL> [call] [CONFIRM]."""
    w = arg.split()
    if not w:
        out = []
        for g, name in GAMES.items():
            rows = store.game_rows(g)
            out.append(f"{g:<8} {name:<13} {store.game_total(g):>5} games {len(rows):>4} players")
        return out + ["GAMES CLEAR <game|ALL> [call]  deletes scores (shows first, then ... CONFIRM)"]
    if w[0].upper() != "CLEAR" or len(w) < 2:
        return ["Usage: GAMES | GAMES CLEAR <" + "|".join(GAMES) + "|ALL> [call] [CONFIRM]"]
    confirm = w[-1].upper() == "CONFIRM"
    if confirm:
        w = w[:-1]
    which = w[1].lower()
    if which != "all" and which not in GAMES:
        return ["Unknown game: " + w[1] + " (" + ", ".join(GAMES) + ", ALL)"]
    game = None if which == "all" else which
    call = auth.base(w[2].upper()) if len(w) > 2 else None
    what = (GAMES[game] if game else "all games") + (f", player {call}" if call else ", all players")
    if not confirm:
        n = store.game_counts(game, call)
        return [f"GAMES CLEAR: deletes {n} score row(s) - {what}"
                + ("" if call else " and the game counters") + ".",
                "To do it: " + " ".join(["GAMES CLEAR", w[1]] + ([w[2]] if call else []) + ["CONFIRM"])]
    n = store.game_clear(game, call)
    return [f"Scores deleted: {n} row(s) - {what}."]
