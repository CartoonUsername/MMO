"""Spielschicht des Vertical Slice: Raum, Bewegung, Live-Kampf, Sammeln, Mehrspieler (ADR-0028). Siehe docs/VERTICAL_SLICE.md."""
from .game import GameServer, load_game_rules

__all__ = ["GameServer", "load_game_rules"]
