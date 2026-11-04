"""AP 15: Unity-Client bleibt deckungsgleich mit dem Server (ADR-0054)."""
import os
import shutil
import subprocess
import unittest
from pathlib import Path

from mmo_server import unitygen

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "client" / "unity" / "Assets" / "Scripts" / "Protocol.g.cs"


class UnityClient(unittest.TestCase):
    def test_generated_command_catalog_matches_the_server(self):
        self.assertEqual(CATALOG.read_text(encoding="utf-8"), unitygen.render(), "python -m mmo_server.unitygen write client/unity/Assets/Scripts/Protocol.g.cs")

    def test_panels_only_use_known_commands(self):
        import re
        from mmo_server.protocol import COMMANDS
        src = (ROOT / "client" / "unity" / "Assets" / "Scripts" / "Panels.cs").read_text(encoding="utf-8")
        used = set(re.findall(r'"((?:query|craft|discovery|market|maker|party|trade|company|production|character|essence|combat|equip|echo|settlement|plot|project|research|guild)[a-z_.]*)"', src))
        self.assertTrue(used)
        self.assertEqual({u for u in used if u not in COMMANDS}, set())

    @unittest.skipUnless(os.environ.get("MMO_TEST_UNITY") == "1" and shutil.which("dotnet"), "MMO_TEST_UNITY=1 und dotnet nötig (scripts/check_unity_core.sh)")
    def test_core_against_live_test_server(self):
        r = subprocess.run(["bash", str(ROOT / "scripts" / "check_unity_core.sh"), "17899"], capture_output=True, text=True, timeout=600)
        self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-1000:])
        self.assertIn("ALLES OK", r.stdout)
