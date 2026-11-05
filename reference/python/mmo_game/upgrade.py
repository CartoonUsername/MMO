"""Hebt einen gespeicherten Spielstand auf eine höhere CEE-Regelversion (ADR-0071).

    python -m mmo_game.upgrade --data /var/lib/mmo --to rules_v10.json

Nur bei gestopptem Dienst ausführen (vorher Sicherung: scripts/backup_mmo.sh). Der Spielstand wird als NEUE Generation
geschrieben; die bisherigen Generationen bleiben unverändert und erlauben den Rückweg. Positionen, Gegner und Sammelpunkte
(game_state.json) werden auf die neue Generation übertragen; die alte Fassung bleibt als game_state.gen-<n>.json liegen.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from mmo_world.persistence import Store, upgrade_world


def upgrade_store(path: str | Path, target_cee_file: str) -> dict:
    store = Store(path)
    gen, world = store.load_latest_valid()
    before = world.svc.rules.version
    new = upgrade_world(world, target_cee_file)
    gen_new = store.commit(new)
    f = Path(path) / "game_state.json"
    moved = False
    if f.exists():
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            data = None
        if data is not None and data.get("generation") == gen:
            shutil.copyfile(f, Path(path) / f"game_state.gen-{gen}.json")
            data["generation"] = gen_new
            tmp = f.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            tmp.replace(f)
            moved = True
    return {"from_rules": before, "to_rules": new.svc.rules.version, "generation_old": gen, "generation_new": gen_new, "game_state_kept": moved}


def main(argv: list[str]) -> int:
    def arg(name: str) -> str | None:
        return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else None
    data, to = arg("--data"), arg("--to")
    if not data or not to:
        print(__doc__)
        return 2
    try:
        print(json.dumps(upgrade_store(data, to), ensure_ascii=False))
    except Exception as e:  # bewusst breit: jede Ablehnung ist ein Abbruch ohne Änderung der alten Generationen
        print(f"ABBRUCH: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
