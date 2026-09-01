"""Shared rig for the manual GUI stress runs: a local server that can serve
normal, empty and deliberately broken payloads, plus non-blocking dialogs."""
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hyperliquid_source as src
import test_integration as fx

FAILS = []


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILS.append(name)


def report():
    print("\n" + "=" * 46)
    print("FAILURES: %d %s" % (len(FAILS), FAILS if FAILS else ""))
    print("=" * 46)
    return 1 if FAILS else 0


STATE = {"positions": "normal", "fills": "normal"}

EMPTY_CH = {"marginSummary": {"accountValue": "500.0", "totalNtlPos": "0.0"},
            "withdrawable": "500.0", "assetPositions": []}

# every field the UI touches, wrong in a different way
BROKEN_CH = {"marginSummary": {"accountValue": None},
             "assetPositions": [
                 {"position": None},
                 {"nonsense": 1},
                 {"position": {"coin": "WEIRD", "szi": "1.0"}},
                 {"position": {"coin": None, "szi": "abc", "entryPx": {}}},
                 "not a dict",
             ]}
BROKEN_FILLS = [{"coin": "X"}, "junk", {"time": "not-a-number", "px": None}, None]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_a):
        pass

    def _json(self, payload):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._json(fx.LEADERBOARD)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        kind = json.loads(self.rfile.read(length) or b"{}").get("type")
        if kind == "clearinghouseState":
            self._json({"normal": fx.CLEARINGHOUSE, "empty": EMPTY_CH,
                        "broken": BROKEN_CH}[STATE["positions"]])
        elif kind == "userFills":
            self._json({"normal": fx.FILLS, "empty": [],
                        "broken": BROKEN_FILLS}[STATE["fills"]])
        elif kind == "allMids":
            self._json(fx.MIDS)
        else:
            self._json({})


BOXES = []


class FakeBox:
    """Modal boxes block forever with nobody to click OK - record instead."""
    @staticmethod
    def showinfo(title, msg, **_k):
        BOXES.append(("info", title, msg))

    @staticmethod
    def showwarning(title, msg, **_k):
        BOXES.append(("warn", title, msg))

    @staticmethod
    def showerror(title, msg, **_k):
        BOXES.append(("error", title, msg))


def start():
    """Boot the server, point the module at it, return (app, wt, server)."""
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % server.server_port
    src.INFO_URL = base + "/info"
    src.LEADERBOARD_URL = base + "/leaderboard"
    tmp = tempfile.mkdtemp()
    src.CACHE_DIR = tmp
    src.CACHE_FILE = os.path.join(tmp, "lb.json")

    import whaletracker as wt
    wt.messagebox = FakeBox
    app = wt.App()
    return app, wt, server, tmp
