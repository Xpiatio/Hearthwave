"""Minimal AX.25 UI-frame decoder — just enough to reach the APRS payload.

APRS rides in the info field of an AX.25 UI frame. This decodes the address
block (destination, source, up to eight digipeaters) and re-renders the frame
as the TNC2 monitor text that `aprslib.parse` expects:

    SRC>DEST,DIGI1*,DIGI2:info

Receive-only: nothing here builds a frame.

Address encoding, for reference — each address is seven bytes. The first six
are the callsign, space-padded, each character shifted left one bit. The
seventh byte carries the SSID in bits 1-4, the "has been repeated" H bit in
bit 7 (only meaningful for digipeaters), and the end-of-address extension bit
in bit 0, which is set on the last address.
"""
from __future__ import annotations

ADDRESS_LEN = 7
MAX_ADDRESSES = 10  # destination + source + 8 digipeaters
UI_CONTROL = 0x03
UI_CONTROL_POLL = 0x13  # UI with the P/F bit set — still a UI frame
PID_NO_LAYER3 = 0xF0


class FrameError(ValueError):
    """The bytes are not a decodable AX.25 UI frame."""


def decode_address(block: bytes) -> tuple[str, bool, bool]:
    """Decode one seven-byte address.

    Returns ``(callsign, is_last, was_repeated)`` where *callsign* carries the
    ``-SSID`` suffix when the SSID is non-zero.
    """
    if len(block) != ADDRESS_LEN:
        raise FrameError("truncated address")
    chars = []
    for byte in block[:6]:
        char = chr(byte >> 1)
        if char == " ":
            continue
        if not (char.isalnum() and char.isascii()):
            raise FrameError(f"invalid callsign character {char!r}")
        chars.append(char)
    if not chars:
        raise FrameError("empty callsign")
    ssid_byte = block[6]
    ssid = (ssid_byte >> 1) & 0x0F
    callsign = "".join(chars)
    if ssid:
        callsign = f"{callsign}-{ssid}"
    return callsign, bool(ssid_byte & 0x01), bool(ssid_byte & 0x80)


def decode_ui_frame(frame: bytes) -> str:
    """Render an AX.25 UI frame as TNC2 monitor text.

    Raises :class:`FrameError` for anything that isn't a UI/no-layer-3 frame —
    a shared RF channel carries connected-mode traffic too, and a half-decoded
    frame is worse than a skipped one.
    """
    addresses: list[tuple[str, bool]] = []
    offset = 0
    while True:
        if offset + ADDRESS_LEN > len(frame):
            raise FrameError("address block ran off the end of the frame")
        callsign, is_last, repeated = decode_address(frame[offset:offset + ADDRESS_LEN])
        addresses.append((callsign, repeated))
        offset += ADDRESS_LEN
        if is_last:
            break
        if len(addresses) >= MAX_ADDRESSES:
            raise FrameError("address block has no end-of-address bit")
    if len(addresses) < 2:
        raise FrameError("frame has no source address")
    if offset + 2 > len(frame):
        raise FrameError("frame ends before its control/PID bytes")

    control, pid = frame[offset], frame[offset + 1]
    if control not in (UI_CONTROL, UI_CONTROL_POLL):
        raise FrameError(f"not a UI frame (control 0x{control:02X})")
    if pid != PID_NO_LAYER3:
        raise FrameError(f"unexpected PID 0x{pid:02X}")

    info = _decode_info(frame[offset + 2:])
    if not info:
        raise FrameError("UI frame has an empty info field")

    (dest, _), (src, _) = addresses[0], addresses[1]
    path = "".join(
        f",{call}*" if repeated else f",{call}"
        for call, repeated in addresses[2:]
    )
    return f"{src}>{dest}{path}:{info}"


def _decode_info(raw: bytes) -> str:
    """Info fields are usually ASCII, but Mic-E and comments carry raw bytes.

    UTF-8 first (some clients send it), latin-1 as the byte-preserving fallback
    so a stray high byte can't corrupt the coordinates that follow it.
    """
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")
