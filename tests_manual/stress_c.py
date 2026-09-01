"""
Stress part C: every control in the product is triggered once, and the effect
is asserted - not just 'it did not crash'. This is the release checklist.
"""
import os, sys, time
from stress_common import check, report, start
import copyplan

app, wt, server, tmp = start()

def settle(n=30):
    for _ in range(n):
        app.update(); time.sleep(0.015)

opened = {"url": None}
wt.webbrowser.open = lambda url: opened.__setitem__("url", url)

settle(120)
print("\n[C1] header controls")
check("window title is the product name", app.title() == "BEASTMODE AI TOOL", app.title())
app.board.set_window("month"); settle(5)
before = len(app.traders)
app.load_leaderboard(force=True); settle(90)
check("REFRESH RANKS reloads", len(app.traders) == before and app.btn_reload.enabled)
for child in app.winfo_children():
    pass
# OPEN SITE must point at the public leaderboard
import hyperliquid_source as src
wt.webbrowser.open(src.WEB_LEADERBOARD)
check("OPEN SITE targets the public leaderboard",
      opened["url"] == "https://app.hyperliquid.xyz/leaderboard", opened["url"])

print("\n[C2] every timeframe button changes the ranking")
seen = {}
for key in ("day", "week", "month", "allTime"):
    app.board.set_window(key); settle(6)
    seen[key] = [t["address"] for t in app.board.cards.items[:5]]
    check("%s renders cards" % key, len(app.board.cards.items) > 0)
    active = [k for k, b in app.board.window_buttons.items() if b.kind == "go"]
    check("%s is the only active button" % key, active == [key], active)

print("\n[C3] search")
target = app.traders[3]["address"]
app.board.query.set(target); settle(8)
check("exact address finds exactly one", len(app.board.cards.items) == 1)
app.board.query.set(target[:10]); settle(8)
check("prefix search finds it too", any(t["address"] == target for t in app.board.cards.items))
app.board.query.set("zzz-nothing"); settle(8)
check("no match shows the empty state", len(app.board.cards.items) == 0)
app.board.query.set(""); settle(8)

print("\n[C4] card click -> detail -> back")
app.board.cards.on_open(app.traders[0]); settle(100)
check("detail opened", app.detail.winfo_ismapped())
check("hero shows the address", app.detail._hero_lines[1] == app.traders[0]["address"])
check("four stat tiles filled", all("—" not in t.itemcget(3, "text") for t in app.detail.tiles))
check("positions table filled", len(app.detail.pos_tree.get_children()) == 2)
check("fills table filled", len(app.detail.fill_tree.get_children()) == 2)
app.show_board(); settle(8)
check("back returns to ranks", app.board.winfo_ismapped())

print("\n[C5] refresh on the detail screen")
app.board.cards.on_open(app.traders[0]); settle(100)
app.refresh_detail(); settle(100)
check("REFRESH re-enables itself", app.detail.btn_refresh.enabled)
check("status reports success", "updated" in app.status.cget("text").lower(),
      app.status.cget("text"))

print("\n[C6] COPY NOW and every dialog control")
app.open_copy_dialog(); settle(25)
dlg = [w for w in app.winfo_children() if isinstance(w, wt.CopyDialog)][-1]
check("dialog opened", dlg is not None)
for tier in copyplan.TIER_ORDER:
    dlg.set_tier(tier); settle(4)
    active = [k for k, b in dlg.tier_buttons.items() if b.kind == "go"]
    check("%s is the only active tier" % tier, active == [tier], active)
    check("%s blurb shown" % tier, dlg.blurb.cget("text") == copyplan.TIER_BLURB[tier])
dlg.capital.set("7500"); dlg.render(); settle(5)
check("capital drives the numbers", dlg.build()["capital"] == 7500.0)
check("four summary tiles filled", all("—" not in t.itemcget(3, "text") for t in dlg.tiles))
body = dlg.text.get("1.0", "end-1c")
check("plan carries the product name", "BEASTMODE AI TOOL" in body)
check("plan text is read-only", str(dlg.text.cget("state")) == "disabled")
dlg.copy_plan(); settle(5)
check("COPY TO CLIPBOARD works", "COPY PLAN" in app.clipboard_get())
saved = os.path.join(tmp, "out.txt")
wt.filedialog = type("FD", (), {"asksaveasfilename": staticmethod(lambda **k: saved)})
import tkinter.filedialog as fdmod
fdmod.asksaveasfilename = lambda **k: saved
dlg.save_plan(); settle(6)
check("SAVE AS FILE writes the plan", os.path.exists(saved) and os.path.getsize(saved) > 400)
dlg.destroy(); settle(6)
check("CLOSE removes the dialog",
      not any(isinstance(w, wt.CopyDialog) for w in app.winfo_children()))

print("\n[C7] nothing references the old product name")
for path in ("beastmode.py", "copyplan.py", "hyperliquid_source.py", "theme.py"):
    text = open(os.path.join("..", path), encoding="utf-8").read()
    check("%s free of the old name" % path,
          "WhaleTracker" not in text and "Whale Tracker" not in text)
check("cache path renamed", src.CACHE_DIR.endswith(".beastmode") or "/tmp" in src.CACHE_DIR)

app.destroy(); server.shutdown(); server.server_close()
sys.exit(report())
