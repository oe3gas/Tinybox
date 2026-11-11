"""Frames of a connection in real time (CR117): to go out, on the air without ack.

AGW 'Y' says how many frames Direwolf still holds for a connection - not yet
sent plus sent but not acknowledged. With a big window (v2.2, k=32) a whole
picture goes out in one burst and stays "waiting" until the other side
acknowledges it: the number stood still and then fell to 0 at once.

The monitor hears both directions, so the count runs with the frames:
own I-frames on the air (Direwolf fork 'O', KISS) move V(S), the N(R) of the
other side's I/S frames move V(A). Between two 'Y' answers an acknowledgement
lowers the count at once; 'Y' corrects it at every poll.

    on_air   = V(S) - V(A)            sent, not yet acknowledged
    to_send  = 'Y' - on_air           still in the queue of Direwolf / the TNC
"""

from __future__ import annotations


def seq(control: bytes, mod128: bool) -> tuple[str, int | None, int | None]:
    """(kind, N(S), N(R)) of an AX.25 control field: kind I, S or U."""
    if not control:
        return "U", None, None
    c0 = control[0]
    if c0 & 0x01 == 0:                                # I
        if mod128:
            if len(control) < 2:
                return "U", None, None
            return "I", (c0 >> 1) & 0x7F, (control[1] >> 1) & 0x7F
        return "I", (c0 >> 1) & 0x07, (c0 >> 5) & 0x07
    if c0 & 0x03 == 0x01:                             # S (RR, RNR, REJ, SREJ)
        if mod128:
            if len(control) < 2:
                return "U", None, None
            return "S", None, (control[1] >> 1) & 0x7F
        return "S", None, (c0 >> 5) & 0x07
    return "U", None, None


class AirQueue:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.y: int | None = None        # last count of Direwolf ('Y'), corrected by acks
        self.va: int | None = None       # V(A): next frame the other side waits for
        self.vs: int | None = None       # V(S): next new frame of ours on the air
        self.mod = 8

    @property
    def on_air(self) -> int:
        if self.va is None or self.vs is None:
            return 0
        n = (self.vs - self.va) % self.mod
        return min(n, self.y) if self.y is not None else n

    @property
    def to_send(self) -> int | None:
        return None if self.y is None else max(0, self.y - self.on_air)

    def poll(self, y: int | None) -> None:
        self.y = y
        if y == 0 and self.va is not None:
            self.vs = self.va            # nothing on its way

    def own_i(self, ns: int, mod: int) -> bool:
        """An own I-frame went on the air. True if it was a new one (not a retry)."""
        self.mod = mod
        if self.va is None:
            self.va = ns
        if self.vs is None:
            self.vs = ns
        if (ns - self.va) % mod >= (self.vs - self.va) % mod:    # beyond V(S): new
            self.vs = (ns + 1) % mod
            return True
        return False

    def ack(self, nr: int, mod: int) -> bool:
        """The other side acknowledged up to N(R). True if the count changed."""
        self.mod = mod
        if self.va is None:
            self.va = nr
            return False
        n = (nr - self.va) % mod
        if n == 0 or (self.vs is not None and n > (self.vs - self.va) % mod):
            return False                 # nothing new, or not a sane N(R)
        self.va = nr
        if self.y is not None:
            self.y = max(0, self.y - n)
        return True
