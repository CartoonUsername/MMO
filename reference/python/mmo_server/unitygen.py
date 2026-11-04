"""Erzeugt den Befehlskatalog des Unity-Clients aus `protocol.py` (AP 15, ADR-0054): der Client kann nicht von der Serverseite abweichen.

    python -m mmo_server.unitygen write ../../client/unity/Assets/Scripts/Protocol.g.cs
    python -m mmo_server.unitygen check ../../client/unity/Assets/Scripts/Protocol.g.cs
"""
from __future__ import annotations

import sys
from pathlib import Path

from .protocol import COMMANDS


def render() -> str:
    rows = []
    for n, c in COMMANDS.items():
        args = ", ".join(f'new Arg("{k}", \'{t.rstrip("?")}\', {"true" if t.endswith("?") else "false"})' for k, t in c.args.items())
        rows.append(f'            new Cmd("{n}", {"true" if c.mutating else "false"}, "{c.actor or ""}", new Arg[] {{ {args} }}),')
    body = "\n".join(rows)
    return f"""// GENERIERT von mmo_server/unitygen.py aus mmo_server/protocol.py - nicht von Hand ändern (Test prüft die Übereinstimmung).
using System.Collections.Generic;

namespace Mmo
{{
    public static class Protocol
    {{
        public sealed class Arg {{ public readonly string Name; public readonly char Type; public readonly bool Optional;
            public Arg(string name, char type, bool optional) {{ Name = name; Type = type; Optional = optional; }} }}      // Typ: s Text, i Ganzzahl, b Wahrheitswert, l Liste
        public sealed class Cmd {{ public readonly string Name; public readonly bool Mutating; public readonly string Actor; public readonly Arg[] Args;
            public Cmd(string name, bool mutating, string actor, Arg[] args) {{ Name = name; Mutating = mutating; Actor = actor; Args = args; }} }}

        public static readonly Cmd[] All = new Cmd[]
        {{
{body}
        }};

        static Dictionary<string, Cmd> byName;
        public static Cmd Find(string name)
        {{
            if (byName == null) {{ byName = new Dictionary<string, Cmd>(); foreach (var c in All) byName[c.Name] = c; }}
            return byName.TryGetValue(name, out var r) ? r : null;
        }}
    }}
}}
"""


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in ("write", "check"):
        print(__doc__)
        return 2
    path = Path(argv[2])
    if argv[1] == "write":
        path.write_text(render(), encoding="utf-8")
        print("geschrieben:", path)
        return 0
    ok = path.exists() and path.read_text(encoding="utf-8") == render()
    print("ok" if ok else "ABWEICHUNG: python -m mmo_server.unitygen write " + str(path))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
