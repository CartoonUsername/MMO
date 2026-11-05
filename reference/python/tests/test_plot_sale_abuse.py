"""AP 45: Missbrauchstests Grundstückshandel (ADR-0073) über das Protokoll."""
import unittest

from mmo_game import GameServer
from mmo_world.persistence import check_consistency
from tests.test_game import Bot


class PlotSaleAbuse(unittest.TestCase):
    def setUp(self):
        self.g = GameServer()
        self.w = self.g.world
        self.a, self.b, self.c = Bot(self.g, "anna"), Bot(self.g, "ben"), Bot(self.g, "cleo")
        for bot in (self.a, self.b, self.c):
            bot.call("game.join")
            self.w.inv.deposit(bot.name, self.w.trading.coin, 5000)
        self.assertTrue(self.a.call("plot.buy", site="hauptstadt", n=1)["ok"])

    def owner(self, n=1):
        return self.w.settlements.plots[f"hauptstadt:{n}"]["owner"]

    def test_bad_arguments_never_change_anything(self):
        before = self.w.settlements.to_json()
        for args in (dict(site="hauptstadt", n=1, buyer="ben", price=-5), dict(site="hauptstadt", n=1, buyer="ben", price=2.5),
                     dict(site="hauptstadt", n=1, buyer="ben", price=True), dict(site="hauptstadt", n=1, buyer="anna", price=10),
                     dict(site="hauptstadt", n=1, buyer="ghost", price=10), dict(site="hauptstadt", n="1", buyer="ben", price=10),
                     dict(site="nowhere", n=1, buyer="ben", price=10), dict(site="hauptstadt", n=99, buyer="ben", price=10),
                     dict(site="hauptstadt", n=1, buyer=["ben"], price=10)):
            self.assertFalse(self.a.call("plot.sell", **args)["ok"], args)
        self.assertEqual(self.w.settlements.to_json(), before)

    def test_only_the_named_buyer_can_accept_and_only_once(self):
        self.assertTrue(self.a.call("plot.sell", site="hauptstadt", n=1, buyer="ben", price=300)["ok"])
        self.assertFalse(self.c.call("plot.accept_sale", site="hauptstadt", n=1)["ok"])             # Dritte
        self.assertFalse(self.a.call("plot.accept_sale", site="hauptstadt", n=1)["ok"])             # Verkäufer selbst
        self.assertFalse(self.c.call("plot.cancel_sale", site="hauptstadt", n=1)["ok"])             # fremdes Angebot zurückziehen
        coins = self.w.inv.balance("ben", self.w.trading.coin)
        self.assertTrue(self.b.call("plot.accept_sale", site="hauptstadt", n=1)["ok"])
        self.assertFalse(self.b.call("plot.accept_sale", site="hauptstadt", n=1)["ok"])             # zweites Mal
        self.assertEqual((self.owner(), coins - self.w.inv.balance("ben", self.w.trading.coin)), ("ben", 300))
        self.assertFalse(self.a.call("plot.sell", site="hauptstadt", n=1, buyer="cleo", price=1)["ok"])   # nicht mehr Besitzer

    def test_no_coin_creation_across_a_sale(self):
        coin = self.w.trading.coin
        total = lambda: sum(self.w.inv.balance(c, coin) for c in ("anna", "ben", "cleo"))
        before = total()
        self.a.call("plot.sell", site="hauptstadt", n=1, buyer="ben", price=1000)
        self.b.call("plot.accept_sale", site="hauptstadt", n=1)
        self.assertEqual(before - total(), 50)                                                       # nur die Gebühr verschwindet
        self.assertEqual(check_consistency(self.w), [])

    def test_offer_is_invalidated_by_changes_after_listing(self):
        self.w.inv.deposit("anna", "timber@standard", 100)
        self.assertTrue(self.a.call("plot.build", site="hauptstadt", n=1, building="house")["ok"])
        self.assertTrue(self.a.call("plot.sell", site="hauptstadt", n=1, buyer="ben", price=10)["ok"])
        self.assertTrue(self.a.call("plot.stash_in", site="hauptstadt", n=1, item_key="timber@standard", qty=5)["ok"])
        self.assertFalse(self.b.call("plot.accept_sale", site="hauptstadt", n=1)["ok"])             # Lager nicht mehr leer
        self.assertEqual(self.owner(), "anna")
        self.assertEqual(self.w.settlements.sales, {})                                               # ungültiges Angebot entfernt


if __name__ == "__main__":
    unittest.main()
