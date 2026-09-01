#!/usr/bin/env python3
"""
Integration tests: a local HTTP server plays Hyperliquid, so the real network
path - urllib, gzip, streaming download, JSON parsing, the disk cache and the
error handling - gets exercised end to end.

Run:  python3 test_integration.py
No internet needed; everything happens on 127.0.0.1.
"""

import gzip
import json
import os
import shutil
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

import hyperliquid_source as src

# ---------------------------------------------------------------- fixtures
# Shapes copied from Hyperliquid's documented responses, values invented.
LEADERBOARD = {"leaderboardRows": [
    {"ethAddress": "0x%040d" % i,
     "accountValue": str(1_000_000 + i * 1000),
     "displayName": ("trader%d" % i) if i % 3 == 0 else None,
     "windowPerformances": [
         ["day", {"pnl": str(i * 10), "roi": str(i / 1000.0), "vlm": str(i * 500)}],
         ["week", {"pnl": str(i * 70), "roi": str(i / 500.0), "vlm": str(i * 3000)}],
         ["month", {"pnl": str(i * 300), "roi": str(i / 200.0), "vlm": str(i * 12000)}],
         ["allTime", {"pnl": str(i * 900), "roi": str(i / 80.0), "vlm": str(i * 40000)}],
     ]}
    for i in range(1, 401)]}

CLEARINGHOUSE = {
    "marginSummary": {"accountValue": "1250000.5", "totalNtlPos": "3000000.0",
                      "totalRawUsd": "1000000.0"},
    "crossMarginSummary": {"accountValue": "1250000.5"},
    "withdrawable": "250000.0",
    "assetPositions": [
        {"type": "oneWay", "position": {
            "coin": "ETH", "szi": "600.0", "entryPx": "3000.0",
            "positionValue": "1800000.0", "unrealizedPnl": "60000.0",
            "returnOnEquity": "0.25", "liquidationPx": "2100.0",
            "marginUsed": "360000.0", "maxLeverage": 25,
            "cumFunding": {"allTime": "1200.0"},
            "leverage": {"type": "cross", "value": 5}}},
        {"type": "oneWay", "position": {
            "coin": "kPEPE", "szi": "-15000.0", "entryPx": "0.0182",
            "positionValue": "252.0", "unrealizedPnl": "-9.0",
            "returnOnEquity": "-0.04", "liquidationPx": None,
            "leverage": {"type": "isolated", "value": 3}}},
    ]}

FILLS = [{"coin": "ETH", "px": "3010.5", "sz": "12.0", "side": "B",
          "time": 1756500000000, "startPosition": "588.0", "dir": "Open Long",
          "closedPnl": "0.0", "hash": "0xabc", "oid": 1, "crossed": True,
          "fee": "3.6", "tid": 9},
         {"coin": "kPEPE", "px": "0.0181", "sz": "5000", "side": "A",
          "time": 1756400000000, "startPosition": "-10000", "dir": "Open Short",
          "closedPnl": "0.0", "hash": "0xdef", "oid": 2, "crossed": False,
          "fee": "0.1", "tid": 10}]

MIDS = {"ETH": "3100.0", "BTC": "69000.0", "kPEPE": "0.0179", "@1": "1.0"}


class Handler(BaseHTTPRequestHandler):
    """Serves the fixtures; `mode` lets a test force failures."""
    mode = "ok"

    def log_message(self, *_a):
        pass

    def _send(self, payload, status=200, gzip_it=False):
        body = json.dumps(payload).encode()
        headers = [("Content-Type", "application/json")]
        if gzip_it:
            body = gzip.compress(body)
            headers.append(("Content-Encoding", "gzip"))
        self.send_response(status)
        for key, value in headers:
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if Handler.mode == "http500":
            self.send_error(500, "boom")
            return
        if Handler.mode == "garbage":
            body = b"<html>not json</html>"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        # the real leaderboard arrives gzipped
        self._send(LEADERBOARD, gzip_it=True)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        request = json.loads(self.rfile.read(length) or b"{}")
        kind = request.get("type")
        if Handler.mode == "http500":
            self.send_error(500, "boom")
        elif kind == "clearinghouseState":
            self._send(CLEARINGHOUSE)
        elif kind == "userFills":
            self._send(FILLS, gzip_it=True)
        elif kind == "allMids":
            self._send(MIDS)
        else:
            self._send({})


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:%d" % cls.port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        Handler.mode = "ok"
        self.tmp = tempfile.mkdtemp()
        self._saved = (src.INFO_URL, src.LEADERBOARD_URL, src.CACHE_DIR, src.CACHE_FILE)
        src.INFO_URL = self.base + "/info"
        src.LEADERBOARD_URL = self.base + "/leaderboard"
        src.CACHE_DIR = self.tmp
        src.CACHE_FILE = os.path.join(self.tmp, "leaderboard.json")

    def tearDown(self):
        src.INFO_URL, src.LEADERBOARD_URL, src.CACHE_DIR, src.CACHE_FILE = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)


class LeaderboardTests(Base):
    def test_downloads_parses_and_sorts(self):
        traders, age = src.fetch_leaderboard(limit=50)
        self.assertEqual(len(traders), 50)
        self.assertEqual(age, 0)
        pnls = [t["perf"]["month"]["pnl"] for t in traders]
        self.assertEqual(pnls, sorted(pnls, reverse=True), "must be ranked by 30d pnl")
        self.assertEqual(traders[0]["address"], "0x%040d" % 400)

    def test_progress_is_reported(self):
        lines = []
        src.fetch_leaderboard(progress=lines.append, limit=10)
        self.assertTrue(any("leaderboard" in l.lower() for l in lines), lines)

    def test_cache_is_written_and_reused(self):
        src.fetch_leaderboard(limit=20)
        self.assertTrue(os.path.exists(src.CACHE_FILE))
        Handler.mode = "http500"          # server now broken
        traders, age = src.fetch_leaderboard(limit=20)
        self.assertEqual(len(traders), 20, "must be served from cache")
        self.assertIsNotNone(src.cached_leaderboard_age())

    def test_force_bypasses_cache(self):
        src.fetch_leaderboard(limit=5)
        Handler.mode = "http500"
        with self.assertRaises(src.SourceError):
            src.fetch_leaderboard(limit=5, force=True)

    def test_http_error_is_readable(self):
        Handler.mode = "http500"
        with self.assertRaises(src.SourceError) as ctx:
            src.fetch_leaderboard(force=True)
        self.assertIn("500", str(ctx.exception))

    def test_non_json_is_rejected(self):
        Handler.mode = "garbage"
        with self.assertRaises(src.SourceError):
            src.fetch_leaderboard(force=True)


class RankingTests(Base):
    """Every timeframe must rank the real leaders, not a monthly slice."""

    @staticmethod
    def _row(addr, day=0, week=0, month=0, all_time=0):
        return {"ethAddress": addr, "accountValue": "1000", "displayName": None,
                "windowPerformances": [
                    ["day", {"pnl": str(day), "roi": "0", "vlm": "0"}],
                    ["week", {"pnl": str(week), "roi": "0", "vlm": "0"}],
                    ["month", {"pnl": str(month), "roi": "0", "vlm": "0"}],
                    ["allTime", {"pnl": str(all_time), "roi": "0", "vlm": "0"}]]}

    def test_window_leaders_survive_the_cut(self):
        """
        Regression: the code ranked by 30-day PnL, cut to the top N, then let
        the UI re-sort that slice. A trader leading the day but outside the
        monthly top N could never be shown, so the 24H view was simply wrong.
        """
        rows = [self._row("0x%040d" % i, month=1_000_000 - i) for i in range(500)]
        rows.append(self._row("0xDAY", day=9_999_999, month=-50_000))
        rows.append(self._row("0xWEEK", week=8_888_888, month=-60_000))
        rows.append(self._row("0xALLTIME", all_time=7_777_777, month=-70_000))

        top = src.top_traders(rows, limit=250)
        kept = {t["address"] for t in top}
        for outlier in ("0xDAY", "0xWEEK", "0xALLTIME"):
            self.assertIn(outlier, kept, "%s was cut although it leads a window" % outlier)

        for window, winner in (("day", "0xDAY"), ("week", "0xWEEK"),
                               ("allTime", "0xALLTIME")):
            best = max(top, key=lambda t: t["perf"][window]["pnl"])
            self.assertEqual(best["address"], winner, window)

    def test_streaming_matches_a_plain_parse(self):
        payload = {"leaderboardRows": [self._row("0x%040d" % i, month=i)
                                       for i in range(50)]}
        streamed = src.top_traders(
            src.iter_leaderboard_rows(json.dumps(payload)), limit=10)
        direct = src.parse_leaderboard(payload, limit=10)
        self.assertEqual([t["address"] for t in streamed],
                         [t["address"] for t in direct])

    def test_streaming_survives_an_unexpected_shape(self):
        # a bare list instead of the documented object
        rows = [self._row("0xA", month=5), self._row("0xB", month=9)]
        got = src.top_traders(src.iter_leaderboard_rows(json.dumps(rows)), limit=5)
        self.assertEqual(got[0]["address"], "0xB")


class TraderTests(Base):
    def test_positions_round_trip(self):
        state = src.fetch_positions("0xabc")
        self.assertAlmostEqual(state["accountValue"], 1250000.5)
        self.assertAlmostEqual(state["withdrawable"], 250000.0)
        self.assertEqual(len(state["positions"]), 2)
        eth, pepe = state["positions"]
        self.assertEqual((eth["coin"], eth["side"]), ("ETH", "LONG"))
        self.assertEqual((pepe["coin"], pepe["side"]), ("kPEPE", "SHORT"))
        self.assertEqual(pepe["liqPx"], 0.0, "a null liquidation price must not crash")
        self.assertGreater(eth["notional"], pepe["notional"], "sorted by size")

    def test_fills_round_trip(self):
        fills = src.fetch_fills("0xabc")
        self.assertEqual([f["side"] for f in fills], ["BUY", "SELL"])
        self.assertEqual(fills[0]["coin"], "ETH")

    def test_mids_round_trip(self):
        mids = src.fetch_mids()
        self.assertAlmostEqual(mids["ETH"], 3100.0)
        self.assertIn("kPEPE", mids)

    def test_server_error_raises(self):
        Handler.mode = "http500"
        for call in (lambda: src.fetch_positions("0xabc"),
                     lambda: src.fetch_fills("0xabc"),
                     src.fetch_mids):
            with self.assertRaises(src.SourceError):
                call()

    def test_unreachable_host_is_readable(self):
        src.INFO_URL = "http://127.0.0.1:1/info"   # nothing listens there
        with self.assertRaises(src.SourceError) as ctx:
            src.fetch_mids()
        self.assertIn("connection", str(ctx.exception).lower())


class EndToEndTests(Base):
    def test_live_data_produces_a_usable_plan(self):
        """The whole chain: fetch -> parse -> plan -> text."""
        import copyplan
        state = src.fetch_positions("0xabc")
        mids = src.fetch_mids()
        plan = copyplan.build_plan(state["positions"], 2000.0, "BALANCED", mids)

        self.assertTrue(plan["legs"], "real positions must yield real legs")
        self.assertLessEqual(round(plan["totalNotional"], 6), 2000.0)
        for leg in plan["legs"]:
            self.assertGreater(leg["size"], 0)
            self.assertGreater(leg["price"], 0)
            self.assertAlmostEqual(leg["size"] * leg["price"], leg["notional"],
                                   delta=leg["notional"] * 0.02)
            if leg["side"] == "LONG":
                self.assertLess(leg["stop"], leg["price"])
            else:
                self.assertGreater(leg["stop"], leg["price"])

        text = copyplan.plan_as_text(plan, "0xabc", "", state["accountValue"])
        self.assertIn("ORDERS", text)
        self.assertIn("ETH", text)
        # the mark price from the server, not the stale entry price
        self.assertIn("3,100.00", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
