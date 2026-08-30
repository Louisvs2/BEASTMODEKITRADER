#!/usr/bin/env python3
"""
Tests fuer die Rechen- und Parse-Logik. Kein Netz noetig.
Start:  python3 test_copyplan.py
"""
import unittest

import copyplan
import hyperliquid_source as src


LEADERBOARD_SAMPLE = {
    "leaderboardRows": [
        {
            "ethAddress": "0xAAA0000000000000000000000000000000000001",
            "accountValue": "1250000.5",
            "displayName": None,
            "windowPerformances": [
                ["day", {"pnl": "1000.0", "roi": "0.01", "vlm": "500000"}],
                ["week", {"pnl": "20000.0", "roi": "0.05", "vlm": "2500000"}],
                ["month", {"pnl": "90000.0", "roi": "0.12", "vlm": "9000000"}],
                ["allTime", {"pnl": "400000.0", "roi": "0.6", "vlm": "40000000"}],
            ],
        },
        {
            "ethAddress": "0xBBB0000000000000000000000000000000000002",
            "accountValue": "800000",
            "displayName": "whale2",
            "windowPerformances": [
                ["month", {"pnl": "150000.0", "roi": "0.3", "vlm": "12000000"}],
            ],
        },
        {"noAddress": True},
    ]
}

CLEARINGHOUSE_SAMPLE = {
    "marginSummary": {"accountValue": "1250000.5", "totalNtlPos": "3000000.0",
                      "totalRawUsd": "1000000"},
    "withdrawable": "250000.0",
    "assetPositions": [
        {"type": "oneWay", "position": {
            "coin": "ETH", "szi": "600.0", "entryPx": "3000.0",
            "positionValue": "1800000.0", "unrealizedPnl": "60000.0",
            "returnOnEquity": "0.25", "liquidationPx": "2100.0",
            "leverage": {"type": "cross", "value": 5}}},
        {"type": "oneWay", "position": {
            "coin": "BTC", "szi": "-15.0", "entryPx": "70000.0",
            "positionValue": "1050000.0", "unrealizedPnl": "-9000.0",
            "returnOnEquity": "-0.04", "liquidationPx": "82000.0",
            "leverage": {"type": "isolated", "value": 3}}},
        {"type": "oneWay", "position": {
            "coin": "SOL", "szi": "0", "entryPx": None, "positionValue": "0.0",
            "unrealizedPnl": "0.0", "leverage": {"type": "cross", "value": 2}}},
    ],
}

FILLS_SAMPLE = [
    {"coin": "ETH", "px": "3010.5", "sz": "12.0", "side": "B", "time": 1756500000000,
     "dir": "Open Long", "closedPnl": "0.0", "hash": "0xabc"},
    {"coin": "BTC", "px": "69880.0", "sz": "1.5", "side": "A", "time": 1756400000000,
     "dir": "Close Long", "closedPnl": "4200.0", "hash": "0xdef"},
]


class ParseTests(unittest.TestCase):
    def test_leaderboard_parsing_and_sorting(self):
        traders = src.parse_leaderboard(LEADERBOARD_SAMPLE)
        self.assertEqual(len(traders), 2, "Zeilen ohne Adresse muessen wegfallen")
        self.assertEqual(traders[0]["address"], "0xBBB0000000000000000000000000000000000002",
                         "hoechster 30-Tage-PnL muss oben stehen")
        self.assertAlmostEqual(traders[1]["accountValue"], 1250000.5)
        self.assertAlmostEqual(traders[1]["perf"]["day"]["pnl"], 1000.0)
        # fehlende Fenster werden mit Nullen aufgefuellt
        self.assertEqual(traders[0]["perf"]["day"]["pnl"], 0.0)

    def test_leaderboard_rejects_garbage(self):
        with self.assertRaises(src.SourceError):
            src.parse_leaderboard({"leaderboardRows": "kaputt"})
        with self.assertRaises(src.SourceError):
            src.parse_leaderboard({"leaderboardRows": []})

    def test_positions_parsing(self):
        state = src._parse_clearinghouse(CLEARINGHOUSE_SAMPLE)
        self.assertEqual(len(state["positions"]), 2, "Nullpositionen fliegen raus")
        first = state["positions"][0]
        self.assertEqual(first["coin"], "ETH")
        self.assertEqual(first["side"], "LONG")
        self.assertAlmostEqual(first["roe"], 25.0)
        self.assertEqual(state["positions"][1]["side"], "SHORT")
        self.assertAlmostEqual(state["accountValue"], 1250000.5)
        self.assertAlmostEqual(state["totalNotional"], 3000000.0)

    def test_fills_parsing(self):
        fills = src._parse_fills(FILLS_SAMPLE)
        self.assertEqual(fills[0]["side"], "KAUF")      # neuester zuerst
        self.assertEqual(fills[1]["side"], "VERKAUF")
        self.assertAlmostEqual(fills[1]["closedPnl"], 4200.0)


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.positions = src._parse_clearinghouse(CLEARINGHOUSE_SAMPLE)["positions"]
        self.mids = {"ETH": 3100.0, "BTC": 69000.0}

    def test_plan_respects_capital(self):
        plan = copyplan.build_plan(self.positions, 1000.0, "AUSGEWOGEN", self.mids)
        self.assertEqual(len(plan["legs"]), 2)
        # Exposure 100 % -> Nominal darf das Kapital nicht ueberschreiten
        self.assertLessEqual(round(plan["totalNotional"], 6), 1000.0)
        self.assertLess(plan["totalMargin"], plan["totalNotional"])
        self.assertGreater(plan["totalRisk"], 0)

    def test_weights_follow_real_positions(self):
        plan = copyplan.build_plan(self.positions, 10000.0, "AUSGEWOGEN", self.mids)
        eth = [l for l in plan["legs"] if l["coin"] == "ETH"][0]
        btc = [l for l in plan["legs"] if l["coin"] == "BTC"][0]
        self.assertGreater(eth["notional"], btc["notional"],
                           "groessere Position des Traders -> groesserer Anteil")
        self.assertAlmostEqual(eth["weight"] + btc["weight"], 100.0, places=6)

    def test_direction_and_stops(self):
        plan = copyplan.build_plan(self.positions, 10000.0, "AUSGEWOGEN", self.mids)
        eth = [l for l in plan["legs"] if l["coin"] == "ETH"][0]
        btc = [l for l in plan["legs"] if l["coin"] == "BTC"][0]
        self.assertEqual(eth["side"], "LONG")
        self.assertLess(eth["stop"], eth["price"], "Long: Stop unter dem Preis")
        self.assertGreater(eth["take"], eth["price"])
        self.assertEqual(btc["side"], "SHORT")
        self.assertGreater(btc["stop"], btc["price"], "Short: Stop ueber dem Preis")
        self.assertLess(btc["take"], btc["price"])

    def test_size_matches_notional(self):
        plan = copyplan.build_plan(self.positions, 50000.0, "AGGRESSIV", self.mids)
        for leg in plan["legs"]:
            self.assertAlmostEqual(leg["size"] * leg["price"], leg["notional"],
                                   delta=leg["notional"] * 0.01)

    def test_leverage_capped(self):
        plan = copyplan.build_plan(self.positions, 10000.0, "VORSICHTIG", self.mids)
        for leg in plan["legs"]:
            self.assertLessEqual(leg["leverage"], copyplan.RISK_MODES["VORSICHTIG"]["maxLev"])

    def test_risk_modes_scale(self):
        base = copyplan.build_plan(self.positions, 10000.0, "VORSICHTIG", self.mids)
        aggr = copyplan.build_plan(self.positions, 10000.0, "AGGRESSIV", self.mids)
        self.assertLess(base["totalNotional"], aggr["totalNotional"])

    def test_tiny_capital_is_skipped_not_crashed(self):
        plan = copyplan.build_plan(self.positions, 5.0, "AUSGEWOGEN", self.mids)
        self.assertEqual(plan["legs"], [])
        self.assertTrue(plan["skipped"])
        self.assertIn("Kein umsetzbarer Plan", copyplan.plan_as_text(plan, "0xabc"))

    def test_zero_and_empty_inputs(self):
        self.assertEqual(copyplan.build_plan([], 1000.0)["legs"], [])
        self.assertEqual(copyplan.build_plan(self.positions, 0)["legs"], [])
        self.assertEqual(copyplan.build_plan(self.positions, -5)["legs"], [])

    def test_missing_price_falls_back_to_entry(self):
        plan = copyplan.build_plan(self.positions, 10000.0, "AUSGEWOGEN", mids={})
        eth = [l for l in plan["legs"] if l["coin"] == "ETH"][0]
        self.assertAlmostEqual(eth["price"], 3000.0, msg="ohne Marktpreis: Einstieg des Traders")

    def test_single_position_is_capped(self):
        single = [{"coin": "ETH", "side": "LONG", "notional": 1e9, "entryPx": 3000.0,
                   "leverage": 10, "roe": 5.0, "uPnl": 1.0, "size": 1.0}]
        plan = copyplan.build_plan(single, 1000.0, "AUSGEWOGEN", {"ETH": 3000.0})
        self.assertEqual(len(plan["legs"]), 1)
        self.assertAlmostEqual(plan["legs"][0]["weight"], 100.0)

    def test_text_output_is_concrete(self):
        plan = copyplan.build_plan(self.positions, 2500.0, "AUSGEWOGEN", self.mids)
        text = copyplan.plan_as_text(plan, "0xAAA1", "whale", 1250000.0)
        for needle in ("COPY-PLAN", "KONKRETE ORDERS", "Stop-Loss", "Take-Profit",
                       "Menge", "Hebel", "REGELN", "ETH", "BTC"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
