"""Stress part A: load, navigation, empty and malformed payloads."""
import sys, time
from stress_common import check, report, start, STATE, BOXES

app, wt, server, tmp = start()

def settle(n=30):
    for _ in range(n):
        app.update(); time.sleep(0.015)

print("\n[1] cold start against a live server")
settle(120)
check("leaderboard loaded", len(app.traders) == 250, "got %d" % len(app.traders))
check("cards rendered", len(app.board.cards.items) > 0)

print("\n[2] timeframe and hostile search input")
for key in ("day", "week", "month", "allTime"):
    app.board.set_window(key); settle(5)
check("all timeframes render", len(app.board.cards.items) > 0)
for junk in ("0xZZZZ", "'; DROP TABLE", "ü€🙂", " " * 40, "%s" % ("a" * 300)):
    app.board.query.set(junk); settle(4)
app.board.query.set(""); settle(5)
check("survives junk search", len(app.board.cards.items) > 0)

print("\n[3] window resize")
for geo in ("960x640", "1600x1000", "1100x700"):
    app.geometry(geo); settle(10)
check("resize survives", len(app.board.cards.items) > 0)

print("\n[4] rapid trader switching (stale-response guard)")
for trader in app.traders[:6]:
    app.open_trader(trader); settle(2)
settle(90)
check("detail shows the LAST trader clicked",
      app.detail._hero_lines[1] == app.traders[5]["address"])
check("positions rendered", len(app.detail.pos_tree.get_children()) == 2)

print("\n[5] trader with nothing open")
STATE["positions"] = "empty"; STATE["fills"] = "empty"
app.refresh_detail(); settle(90)
check("empty state renders", len(app.detail.pos_tree.get_children()) == 1)
BOXES.clear()
app.open_copy_dialog(); settle(15)
check("copy refused", not any(isinstance(w, wt.CopyDialog) for w in app.winfo_children()))
check("user told why", bool(BOXES) and "Nothing to copy" in BOXES[-1][1], BOXES)

print("\n[6] malformed server payloads")
STATE["positions"] = "broken"; STATE["fills"] = "broken"
app.refresh_detail(); settle(90)
check("app survives garbage", bool(app.winfo_exists()))
check("not stuck loading", app.detail.btn_refresh.enabled)

app.destroy(); server.shutdown(); server.server_close()
sys.exit(report())
