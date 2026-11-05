"""AP 20: Client-Fenster für Elementzauber, Echo-Wirkung, Gildenforschung und Raid (ADR-0059). Statische Prüfung des Browser-Clients."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from mmo_game.game import load_game_rules
from mmo_sim.rules import load_sim_rules

INDEX = Path(__file__).resolve().parents[1] / "mmo_game" / "web" / "index.html"
PANELS = Path(__file__).resolve().parents[3] / "client" / "unity" / "Assets" / "Scripts" / "Panels.cs"
HTML = INDEX.read_text(encoding="utf-8")


class WebClient(unittest.TestCase):
    def test_script_is_valid_javascript(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node nicht installiert")
        js = "\n".join(re.findall(r"<script[^>]*>(.*?)</script>", HTML, re.S))
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(js)
        r = subprocess.run([node, "--check", f.name], capture_output=True, text=True)
        Path(f.name).unlink()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_every_kit_command_has_a_label(self):
        """Alle Zauberbefehle der Standardregeln haben Name/Symbol in der Skill-Leiste."""
        sim = load_sim_rules(load_game_rules()["sim_rules"])
        casts = [n for n, s in sim["skills"].items() if isinstance(s, dict) and "element" in s]
        for c in casts:
            self.assertRegex(HTML, rf"\b{c}:\[", c)

    def test_new_windows_are_wired(self):
        for needle in ("game.elements", "Wirkung im Kampf", "Gildenforschung", "guild.research", "raid_cleared", "guild_chest", "Gildenraid betreten"):
            self.assertIn(needle, HTML, needle)

    def test_hotkeys_do_not_collide_with_controls(self):
        keys = re.search(r"const SLOT_KEYS=\[(.*?)\]", HTML).group(1).replace('"', "").split(",")
        self.assertEqual(len(keys), len(set(keys)))
        self.assertFalse(set(keys) & {"w", "a", "s", "d", "e", " "})

    def test_unity_guild_panel_offers_research(self):
        self.assertIn("guild.research", PANELS.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()


class ComboLabels(unittest.TestCase):
    """AP 27: Kombinationszauber haben lesbare Namen in der Skill-Leiste und im Elementfenster."""
    def test_combo_labels_wired(self):
        for needle in ("function skillOf(", 'cmd.startsWith("combo_")', "skillOf(c.cmd)", "em.result.combos"):
            self.assertIn(needle, HTML, needle)
        self.assertNotIn('SKILL[c.cmd]||[c.cmd,"•"]', HTML)

    def test_label_logic_in_node(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node nicht installiert")
        m = re.search(r"function skillOf\(.*?\}\n", HTML, re.S)
        self.assertIsNotNone(m)
        js = ('const SKILL={light:["Hieb","x"]};const ELEM_NAME={earth:"Erde",water:"Wasser",fire:"Feuer"};' + m.group(0)
              + 'console.log(JSON.stringify([skillOf("light"),skillOf("combo_earth_water"),skillOf("combo_earth_fire_water"),skillOf("zz")]))')
        r = subprocess.run([node, "-e", js], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), '[["Hieb","x"],["Erde+Wasser","✦"],["Erde+Feuer+Wasser","✹"],["zz","•"]]')
