"""Is a received file a program? (CR96, audit TB-05)

A file from another station is only data - but a program or script that lands
on the PC can do harm once someone double-clicks it. The client therefore does
not take such files: by the offered name (before a byte is fetched) and by the
content (the first bytes; for a ZIP the names inside). Anything else may come.
"""

from __future__ import annotations

import io
import zipfile

BLOCKED_EXT = frozenset("""
    exe com scr pif bat cmd ps1 psm1 psd1 vbs vbe js jse mjs wsf wsh wsc hta msi msp mst
    dll cpl ocx sys drv lnk url scf inf reg jar class sh bash zsh csh command app pkg dmg
    deb rpm apk appx msix ipa elf bin run py pyw pyc pl rb php docm dotm xlsm xltm xlam
    pptm potm ppam sldm iso img vhd vhdx chm gadget application appref-ms
""".split())

MAGIC = (
    (b"MZ", "Windows program"),
    (b"\x7fELF", "Linux program"),
    (b"\xfe\xed\xfa\xce", "macOS program"), (b"\xfe\xed\xfa\xcf", "macOS program"),
    (b"\xce\xfa\xed\xfe", "macOS program"), (b"\xcf\xfa\xed\xfe", "macOS program"),
    (b"\xca\xfe\xba\xbe", "macOS/Java program"),
    (b"#!", "script"),
    (b"L\x00\x00\x00\x01\x14\x02\x00", "Windows shortcut"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", None),       # old Office/MSI: checked by name
)


def _ext(name: str) -> str:
    name = name.strip().rstrip(". ").lower()
    return name.rsplit(".", 1)[-1] if "." in name else ""


def name_verdict(name: str) -> str | None:
    """Why a file of this name is not taken, or None."""
    if _ext(name) in BLOCKED_EXT:
        return f"program or script file (.{_ext(name)}) - not taken"
    return None


def content_verdict(data: bytes) -> str | None:
    """Why these bytes are not taken, or None."""
    for magic, what in MAGIC:
        if what and data.startswith(magic):
            return f"{what} - not taken"
    if data[:4] == b"PK\x03\x04":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for n in z.namelist():
                    if name_verdict(n.rsplit("/", 1)[-1]):
                        return f"ZIP with a program inside ({n}) - not taken"
        except (zipfile.BadZipFile, OSError, ValueError, RuntimeError):
            return "damaged ZIP - not taken"
    return None


def verdict(name: str, data: bytes | None = None) -> str | None:
    return name_verdict(name) or (content_verdict(data) if data is not None else None)
