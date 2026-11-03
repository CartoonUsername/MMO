"""Erzeugt den Befehlskatalog-Abschnitt von docs/PROTOCOL.md aus `protocol.py` (Dokument und Code bleiben deckungsgleich).

    python -m mmo_server.docgen write ../../docs/PROTOCOL.md
    python -m mmo_server.docgen check ../../docs/PROTOCOL.md
"""
from __future__ import annotations

import sys
from pathlib import Path

from .protocol import COMMANDS, INTERNAL_ONLY

BEGIN, END = "<!-- KATALOG:BEGIN -->", "<!-- KATALOG:END -->"


def catalog_block() -> str:
    rows = []
    for n, c in COMMANDS.items():
        args = ", ".join(f"{k}{'?' if t.endswith('?') else ''}:{t.rstrip('?')}" for k, t in c.args.items())
        rows.append(f"| `{n}` | {args} | {c.actor or '–'} | {'schreibend' if c.mutating else 'lesend'} | {c.rate_group} |")
    table = "| Befehl | Argumente | handelnde Figur | Art | Ratengruppe |\n|---|---|---|---|---|\n" + "\n".join(rows)
    internal = "\n".join(f"- **{k}** – {v}" for k, v in INTERNAL_ONLY.items())
    return (f"{BEGIN}\n{table}\n\nArgumentkürzel: `s` Zeichenkette, `i` Ganzzahl, `b` Wahrheitswert, `l` Liste von Zeichenketten "
            f"(höchstens 16), `?` optional.\n\n### Bewusst nur serverintern (nicht erreichbar)\n\n{internal}\n{END}")


def apply(text: str) -> str:
    a, b = text.index(BEGIN), text.index(END) + len(END)
    return text[:a] + catalog_block() + text[b:]


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in ("write", "check"):
        print(__doc__)
        return 2
    path = Path(argv[2])
    text = path.read_text(encoding="utf-8")
    new = apply(text)
    if argv[1] == "check":
        print("ok" if new == text else f"ABWEICHUNG: {path}")
        return 0 if new == text else 1
    path.write_text(new, encoding="utf-8", newline="\n")
    print(f"geschrieben: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
