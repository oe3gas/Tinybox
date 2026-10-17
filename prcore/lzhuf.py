"""LZHUF compression as used by F6FBB / LinBPQ compressed forwarding (B0 and B1).

A port of lzhuf.c (Haruyasu Yoshizaki 1988, FBB variant: 2 kB window, 60 byte
look-ahead) as found in LinBPQ's lzhuf32.c. Integer behaviour follows the
original 16-bit code: bit buffers are masked to 16 bits.

Payload layouts:
    B0:  length (4 bytes, little endian)  + Huffman data
    B1:  CRC-16 (2 bytes, LE) + B0 payload; the CRC covers the B0 payload
         (CCITT/XMODEM table, start value 0)

The output must be byte-identical to LinBPQ - tests compare against vectors
made with the C original.
"""

from __future__ import annotations

N = 2048                       # ring buffer
F = 60                         # look-ahead
THRESHOLD = 2
NIL = N
N_CHAR = 256 - THRESHOLD + F   # character codes 0..N_CHAR-1
T = N_CHAR * 2 - 1             # table size
R = T - 1                      # root
MAX_FREQ = 0x8000


class LzhufError(ValueError):
    pass


# --- CRC-16 (CCITT, XMODEM), as in LinBPQ -------------------------------------------

def _crc_table() -> list[int]:
    out = []
    for i in range(256):
        c = i << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) if c & 0x8000 else (c << 1)
        out.append(c & 0xFFFF)
    return out


CRCTAB = _crc_table()


def crc16(data: bytes, crc: int = 0) -> int:
    for b in data:
        crc = ((crc << 8) & 0xFFFF) ^ CRCTAB[b ^ (crc >> 8)]
    return crc


# --- position tables ---------------------------------------------------------------

P_LEN = bytes([3] + [4] * 3 + [5] * 8 + [6] * 12 + [7] * 24 + [8] * 16)
P_CODE = bytes([
    0x00, 0x20, 0x30, 0x40, 0x50, 0x58, 0x60, 0x68, 0x70, 0x78, 0x80, 0x88, 0x90, 0x94, 0x98, 0x9C,
    0xA0, 0xA4, 0xA8, 0xAC, 0xB0, 0xB4, 0xB8, 0xBC, 0xC0, 0xC2, 0xC4, 0xC6, 0xC8, 0xCA, 0xCC, 0xCE,
    0xD0, 0xD2, 0xD4, 0xD6, 0xD8, 0xDA, 0xDC, 0xDE, 0xE0, 0xE2, 0xE4, 0xE6, 0xE8, 0xEA, 0xEC, 0xEE,
    0xF0, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFB, 0xFC, 0xFD, 0xFE, 0xFF])


def _decode_tables() -> tuple[bytes, bytes]:
    """d_code/d_len: inverse of p_code/p_len for every possible leading byte."""
    d_code, d_len = bytearray(256), bytearray(256)
    for i in range(64):
        n = P_LEN[i]
        start = P_CODE[i]
        span = 1 << (8 - n) if n <= 8 else 1
        for b in range(start, start + span):
            d_code[b] = i
            d_len[b] = n
    return bytes(d_code), bytes(d_len)


D_CODE, D_LEN = _decode_tables()


# --- adaptive Huffman tree (shared by encoder and decoder) ------------------------

class _Huff:
    def __init__(self) -> None:
        self.freq = [0] * (T + 1)
        self.prnt = [0] * (T + N_CHAR)
        self.son = [0] * T
        for i in range(N_CHAR):
            self.freq[i] = 1
            self.son[i] = i + T
            self.prnt[i + T] = i
        i, j = 0, N_CHAR
        while j <= R:
            self.freq[j] = self.freq[i] + self.freq[i + 1]
            self.son[j] = i
            self.prnt[i] = self.prnt[i + 1] = j
            i += 2
            j += 1
        self.freq[T] = 0xFFFF
        self.prnt[R] = 0

    def reconst(self) -> None:
        freq, son, prnt = self.freq, self.son, self.prnt
        j = 0
        for i in range(T):
            if son[i] >= T:
                freq[j] = (freq[i] + 1) // 2
                son[j] = son[i]
                j += 1
        i, j = 0, N_CHAR
        while j < T:
            f = freq[j] = freq[i] + freq[i + 1]
            k = j - 1
            while f < freq[k]:
                k -= 1
            k += 1
            freq[k + 1:j + 1] = freq[k:j]
            freq[k] = f
            son[k + 1:j + 1] = son[k:j]
            son[k] = i
            i += 2
            j += 1
        for i in range(T):
            k = son[i]
            if k >= T:
                prnt[k] = i
            else:
                prnt[k] = prnt[k + 1] = i

    def update(self, c: int) -> None:
        freq, son, prnt = self.freq, self.son, self.prnt
        if freq[R] == MAX_FREQ:
            self.reconst()
        c = prnt[c + T]
        while True:
            freq[c] += 1
            k = freq[c]
            l = c + 1
            if k > freq[l]:
                l += 1
                while k > freq[l]:
                    l += 1
                l -= 1
                freq[c] = freq[l]
                freq[l] = k
                i = son[c]
                prnt[i] = l
                if i < T:
                    prnt[i + 1] = l
                j = son[l]
                son[l] = i
                prnt[j] = c
                if j < T:
                    prnt[j + 1] = c
                son[c] = j
                c = l
            c = prnt[c]
            if c == 0:
                break


# --- compression -------------------------------------------------------------------

class _Encoder:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0
        self.out = bytearray()
        self.putbuf = 0
        self.putlen = 0
        self.h = _Huff()
        self.text = bytearray(N + F - 1)
        self.lson = [0] * (N + 1)
        self.rson = [NIL] * (N + 257)
        self.dad = [NIL] * (N + 1)
        self.match_position = 0
        self.match_length = 0

    def get(self) -> int:
        if self.pos >= len(self.data):
            return -1
        c = self.data[self.pos]
        self.pos += 1
        return c

    # LZSS binary tree
    def insert_node(self, r: int) -> None:
        text, lson, rson, dad = self.text, self.lson, self.rson, self.dad
        cmp = 1
        p = N + 1 + text[r]
        rson[r] = lson[r] = NIL
        self.match_length = 0
        while True:
            if cmp >= 0:
                if rson[p] != NIL:
                    p = rson[p]
                else:
                    rson[p] = r
                    dad[r] = p
                    return
            else:
                if lson[p] != NIL:
                    p = lson[p]
                else:
                    lson[p] = r
                    dad[r] = p
                    return
            i = 1
            while i < F:
                cmp = text[r + i] - text[p + i]
                if cmp != 0:
                    break
                i += 1
            if i > THRESHOLD:
                if i > self.match_length:
                    self.match_position = ((r - p) & (N - 1)) - 1
                    self.match_length = i
                    if i >= F:
                        break
                if i == self.match_length:
                    c = ((r - p) & (N - 1)) - 1
                    if c < self.match_position:
                        self.match_position = c
        dad[r] = dad[p]
        lson[r] = lson[p]
        rson[r] = rson[p]
        dad[lson[p]] = r
        dad[rson[p]] = r
        if rson[dad[p]] == p:
            rson[dad[p]] = r
        else:
            lson[dad[p]] = r
        dad[p] = NIL

    def delete_node(self, p: int) -> None:
        lson, rson, dad = self.lson, self.rson, self.dad
        if dad[p] == NIL:
            return
        if rson[p] == NIL:
            q = lson[p]
        elif lson[p] == NIL:
            q = rson[p]
        else:
            q = lson[p]
            if rson[q] != NIL:
                while rson[q] != NIL:
                    q = rson[q]
                rson[dad[q]] = lson[q]
                dad[lson[q]] = dad[q]
                lson[q] = lson[p]
                dad[lson[p]] = q
            rson[q] = rson[p]
            dad[rson[p]] = q
        dad[q] = dad[p]
        if rson[dad[p]] == p:
            rson[dad[p]] = q
        else:
            lson[dad[p]] = q
        dad[p] = NIL

    # bit output, 16-bit buffer like the original
    def putcode(self, l: int, c: int) -> None:
        self.putbuf = (self.putbuf | (c >> self.putlen)) & 0xFFFF
        self.putlen += l
        if self.putlen >= 8:
            self.out.append(self.putbuf >> 8)
            self.putlen -= 8
            if self.putlen >= 8:
                self.out.append(self.putbuf & 0xFF)
                self.putlen -= 8
                self.putbuf = (c << (l - self.putlen)) & 0xFFFF
            else:
                self.putbuf = (self.putbuf << 8) & 0xFFFF

    def encode_char(self, c: int) -> None:
        prnt = self.h.prnt
        i = 0
        j = 0
        k = prnt[c + T]
        while True:
            i >>= 1
            if k & 1:
                i += 0x8000
            j += 1
            k = prnt[k]
            if k == R:
                break
        self.putcode(j, i)
        self.h.update(c)

    def encode_position(self, c: int) -> None:
        i = c >> 6
        self.putcode(P_LEN[i], P_CODE[i] << 8)
        self.putcode(6, ((c & 0x3F) << 10) & 0xFFFF)

    def run(self) -> bytes:
        text = self.text
        s, r = 0, N - F
        for i in range(r):
            text[i] = 0x20
        length = 0
        while length < F:
            c = self.get()
            if c < 0:
                break
            text[r + length] = c
            length += 1
        for i in range(1, F + 1):
            self.insert_node(r - i)
        self.insert_node(r)
        while True:
            if self.match_length > length:
                self.match_length = length
            if self.match_length <= THRESHOLD:
                self.match_length = 1
                self.encode_char(text[r])
            else:
                self.encode_char(255 - THRESHOLD + self.match_length)
                self.encode_position(self.match_position)
            last = self.match_length
            i = 0
            while i < last:
                c = self.get()
                if c < 0:
                    break
                self.delete_node(s)
                text[s] = c
                if s < F - 1:
                    text[s + N] = c
                s = (s + 1) & (N - 1)
                r = (r + 1) & (N - 1)
                self.insert_node(r)
                i += 1
            while i < last:
                i += 1
                self.delete_node(s)
                s = (s + 1) & (N - 1)
                r = (r + 1) & (N - 1)
                length -= 1
                if length:
                    self.insert_node(r)
            if length <= 0:
                break
        if self.putlen:
            self.out.append(self.putbuf >> 8)
        return bytes(self.out)


def compress(data: bytes) -> bytes:
    """B0 payload: 4-byte length (LE) + LZHUF data."""
    head = len(data).to_bytes(4, "little")
    if not data:
        return head
    return head + _Encoder(data).run()


def compress_b1(data: bytes) -> bytes:
    """B1 payload: CRC-16 (LE) of the B0 payload, then the B0 payload."""
    b0 = compress(data)
    return crc16(b0).to_bytes(2, "little") + b0


# --- decompression -----------------------------------------------------------------

def decompress(payload: bytes, max_size: int = 5_000_000) -> bytes:
    """B0 payload -> text. Raises LzhufError for impossible input."""
    if len(payload) < 4:
        raise LzhufError("payload shorter than its length field")
    size = int.from_bytes(payload[:4], "little")
    if size > max_size:
        raise LzhufError(f"message size {size} too large")
    if size == 0:
        return b""
    data = payload[4:]
    pos = 0
    getbuf = 0
    getlen = 0
    h = _Huff()
    son = h.son
    text = bytearray(b" " * N)
    r = N - F
    out = bytearray()

    def fill() -> None:
        nonlocal pos, getbuf, getlen
        while getlen <= 8:
            b = data[pos] if pos < len(data) else 0
            pos += 1
            getbuf = (getbuf | (b << (8 - getlen))) & 0xFFFF
            getlen += 8

    def get_bit() -> int:
        nonlocal getbuf, getlen
        fill()
        i = getbuf
        getbuf = (getbuf << 1) & 0xFFFF
        getlen -= 1
        return (i & 0x8000) >> 15

    def get_byte() -> int:
        nonlocal getbuf, getlen
        fill()
        i = getbuf
        getbuf = (getbuf << 8) & 0xFFFF
        getlen -= 8
        return (i & 0xFF00) >> 8

    while len(out) < size:
        if pos > len(data) + 4:
            raise LzhufError("compressed data ends too early")
        c = son[R]
        while c < T:
            c = son[c + get_bit()]
        c -= T
        h.update(c)
        if c < 256:
            out.append(c)
            text[r] = c
            r = (r + 1) & (N - 1)
        else:
            i = get_byte()
            cc = D_CODE[i] << 6
            j = D_LEN[i] - 2
            while j:
                i = (i << 1) + get_bit()
                j -= 1
            p = cc | (i & 0x3F)
            i = (r - p - 1) & (N - 1)
            for k in range(c - 255 + THRESHOLD):
                ch = text[(i + k) & (N - 1)]
                out.append(ch)
                text[r] = ch
                r = (r + 1) & (N - 1)
    return bytes(out[:size])


def decompress_b1(payload: bytes, max_size: int = 5_000_000) -> bytes:
    """Check the CRC of a B1 payload, then decompress it."""
    if len(payload) < 6:
        raise LzhufError("B1 payload too short")
    want = int.from_bytes(payload[:2], "little")
    got = crc16(payload[2:])
    if want != got:
        raise LzhufError(f"CRC error (sent {want:04X}, computed {got:04X})")
    return decompress(payload[2:], max_size)
