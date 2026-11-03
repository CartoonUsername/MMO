import dataclasses
import unittest

from mmo_cee import CharacterService, IntegrityError
from mmo_cee.history import EventLog


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.svc = CharacterService()
        self.svc.create("c1", "player")
        self.svc.record("c1", "identity.xp_gained", {"amount": 50})

    def test_chain_valid(self):
        self.svc.log.verify("c1")
        evs = self.svc.log.events("c1")
        self.assertEqual([e.seq for e in evs], [0, 1])
        self.assertEqual(evs[1].prev_hash, evs[0].hash)
        self.assertEqual(evs[0].rules_version, self.svc.rules.version)

    def test_tamper_detected(self):
        evs = self.svc.log._events["c1"]
        evs[1] = dataclasses.replace(evs[1], payload={"amount": 999999})
        with self.assertRaises(IntegrityError):
            self.svc.log.verify("c1")
        with self.assertRaises(IntegrityError):
            self.svc.rebuild("c1")

    def test_removed_event_detected(self):
        del self.svc.log._events["c1"][0]
        with self.assertRaises(IntegrityError):
            self.svc.log.verify("c1")

    def test_replay_equals_live_state(self):
        self.svc.record("c1", "profession.work", {"profession": "mining", "xp": 400})
        live = self.svc.state("c1").parts
        import copy
        live = copy.deepcopy(live)
        self.assertEqual(self.svc.rebuild("c1").parts, live)

    def test_json_roundtrip(self):
        data = self.svc.log.to_json("c1")
        log2 = EventLog.from_json("c1", data)
        svc2 = CharacterService(log=log2)
        self.assertEqual(svc2.state("c1").parts["identity"]["xp"], 50)

    def test_payload_decoupled_from_caller(self):
        payload = {"amount": 10}
        ev = self.svc.record("c1", "identity.xp_gained", payload)
        payload["amount"] = 10**9
        self.assertEqual(ev.payload["amount"], 10)
        self.svc.log.verify("c1")


if __name__ == "__main__":
    unittest.main()
