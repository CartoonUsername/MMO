"""Minimaler WebSocket-Server-Teil (RFC 6455) für den Browser-Testclient – nur Standardbibliothek. Siehe ADR-0036.

Unterstützt: Handshake, Text-Nachrichten (auch fragmentiert), Ping/Pong, Schließen. Client-Rahmen müssen maskiert sein; Nachrichten sind
auf `max_message` Bytes begrenzt (größer → Schließen mit 1009). Binärdaten werden abgelehnt (1003).
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import struct

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
OP_CONT, OP_TEXT, OP_BIN, OP_CLOSE, OP_PING, OP_PONG = 0x0, 0x1, 0x2, 0x8, 0x9, 0xA


class WsError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


def accept_key(client_key: str) -> str:
    return base64.b64encode(hashlib.sha1((client_key + GUID).encode("ascii")).digest()).decode("ascii")


def encode_frame(opcode: int, payload: bytes, mask_key: bytes | None = None) -> bytes:
    """Rahmen mit FIN-Bit; `mask_key` (4 Bytes) maskiert die Nutzlast (nur Clients tun das; hier für Tests)."""
    n = len(payload)
    head = bytes([0x80 | opcode])
    mbit = 0x80 if mask_key is not None else 0
    if n < 126:
        head += bytes([mbit | n])
    elif n < 65536:
        head += bytes([mbit | 126]) + struct.pack(">H", n)
    else:
        head += bytes([mbit | 127]) + struct.pack(">Q", n)
    if mask_key is not None:
        payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
        head += mask_key
    return head + payload


async def read_frame(reader: asyncio.StreamReader, max_payload: int) -> tuple[bool, int, bytes]:
    """Liest einen Client-Rahmen (maskiert Pflicht). Rückgabe: (fin, opcode, Nutzlast)."""
    b0, b1 = await reader.readexactly(2)
    fin, rsv, opcode = bool(b0 & 0x80), b0 & 0x70, b0 & 0x0F
    if rsv:
        raise WsError(1002, "reservierte Bits")
    if not b1 & 0x80:
        raise WsError(1002, "Client-Rahmen müssen maskiert sein")
    n = b1 & 0x7F
    if n == 126:
        (n,) = struct.unpack(">H", await reader.readexactly(2))
    elif n == 127:
        (n,) = struct.unpack(">Q", await reader.readexactly(8))
    if opcode >= 0x8 and (n > 125 or not fin):
        raise WsError(1002, "ungültiger Steuerrahmen")
    if n > max_payload:
        raise WsError(1009, "Nachricht zu groß")
    key = await reader.readexactly(4)
    data = await reader.readexactly(n)
    return fin, opcode, bytes(b ^ key[i % 4] for i, b in enumerate(data))


async def read_message(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, max_message: int) -> str | None:
    """Nächste Text-Nachricht; None bei Schließen. Beantwortet Ping selbst. Fehler → WsError."""
    parts: list[bytes] = []
    total = 0
    started = False
    while True:
        fin, op, data = await read_frame(reader, max_message)
        if op == OP_CLOSE:
            writer.write(encode_frame(OP_CLOSE, data[:2]))
            return None
        if op == OP_PING:
            writer.write(encode_frame(OP_PONG, data))
            await writer.drain()
            continue
        if op == OP_PONG:
            continue
        if op == OP_BIN:
            raise WsError(1003, "nur Text")
        if op == OP_TEXT:
            if started:
                raise WsError(1002, "neue Nachricht mitten in einer fragmentierten")
            started = True
        elif op == OP_CONT:
            if not started:
                raise WsError(1002, "Fortsetzung ohne Anfang")
        else:
            raise WsError(1002, "unbekannter Opcode")
        total += len(data)
        if total > max_message:
            raise WsError(1009, "Nachricht zu groß")
        parts.append(data)
        if fin:
            try:
                return b"".join(parts).decode("utf-8")
            except UnicodeDecodeError as e:
                raise WsError(1007, "kein UTF-8") from e


def close_frame(code: int, reason: str = "") -> bytes:
    return encode_frame(OP_CLOSE, struct.pack(">H", code) + reason.encode("utf-8")[:100])
