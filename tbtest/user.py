"""What terminal and client users have in common."""

from __future__ import annotations

from .ledger import Ledger


class ActionError(Exception):
    """An action failed - the text goes into the report."""


class User:
    kind = "?"                       # T terminal, C client

    def __init__(self, call: str, box: str, ledger: Ledger, timeout: float) -> None:
        self.call = call
        self.box = box
        self.ledger = ledger
        self.timeout = timeout
        self.board: str | None = None
        self.status = "idle"         # shown in the live line
        self.last_error = ""

    @property
    def label(self) -> str:
        return f"{self.call}/{self.kind}"

    async def start(self) -> None: ...
    async def close(self) -> None: ...
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...

    @property
    def connected(self) -> bool:
        return False
