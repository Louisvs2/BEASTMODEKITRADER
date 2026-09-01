#!/usr/bin/env python3
"""
WHALE TRACKER  -  desktop app for macOS, Windows and Linux.

Shows Hyperliquid's public trader leaderboard, each trader's LIVE open
positions and their most recent executed trades, and turns those real
positions into a concrete copy plan sized for your own capital.

Run:  python3 whaletracker.py
Standard library only - nothing to install.
"""

import datetime
import queue
import sys
import threading
import webbrowser

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ImportError:
    sys.stderr.write(
        "\nERROR: this Python was built without tkinter.\n"
        "  macOS  : brew install python-tk, or install Python from python.org\n"
        "  Windows: reinstall Python from python.org, keep 'tcl/tk and IDLE' ticked\n"
        "  Linux  : sudo apt install python3-tk\n\n"
    )
    raise SystemExit(1)

import theme as T
import widgets as W
import hyperliquid_source as src
import copyplan


LEV_LABEL = {"cross": "CROSS", "isolated": "ISO"}


def when(ms):
    if not ms:
        return "-"
    try:
        return datetime.datetime.fromtimestamp(ms / 1000.0).strftime("%d %b  %H:%M:%S")
    except (ValueError, OSError, OverflowError):
        return "-"


class App(tk.Tk):
    def __init__(self):
        tk.Tk.__init__(self)
        self.title("Whale Tracker")
        self.geometry("1240x820")
        self.minsize(960, 640)
        self.configure(bg=T.VOID)

        self.jobs = queue.Queue()
        self.traders = []
        self.window_key = "month"
        self.current = None
        self.current_detail = None
        self._warned_certificates = False

        self._style_tables()
        self._build_header()

        self.stage = tk.Frame(self, bg=T.VOID)
        self.stage.pack(fill="both", expand=True)
        self.board = BoardScreen(self.stage, self)
        self.detail = DetailScreen(self.stage, self)
        self.show_board()

        self._build_statusbar()
        self.after(60, self._pump)
        self.after(150, self.load_leaderboard)

    # ---------------------------------------------------------------- chrome
    def _style_tables(self):
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure("Neon.Treeview",
                     background=T.SURFACE, fieldbackground=T.SURFACE,
                     foreground=T.TEXT, rowheight=30, borderwidth=0,
                     font=T.nums(11))
        st.configure("Neon.Treeview.Heading",
                     background=T.DEEP, foreground=T.FAINT, relief="flat",
                     borderwidth=0, font=T.display(9))
        st.map("Neon.Treeview.Heading", background=[("active", T.SURFACE_2)])
        st.map("Neon.Treeview",
               background=[("selected", T.SURFACE_2)],
               foreground=[("selected", T.CYAN)])
        st.layout("Neon.Treeview", [("Neon.Treeview.treearea", {"sticky": "nswe"})])

    def _build_header(self):
        bar = tk.Frame(self, bg=T.DEEP, height=72)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        left = tk.Frame(bar, bg=T.DEEP)
        left.pack(side="left", padx=20)
        logo = tk.Canvas(left, width=310, height=52, bg=T.DEEP,
                         highlightthickness=0, bd=0)
        logo.pack(pady=10)
        first = logo.create_text(0, 18, text="WHALE", anchor="w",
                                 fill=T.TEXT, font=T.display(23))
        logo.create_text(logo.bbox(first)[2] + 8, 18, text="TRACKER", anchor="w",
                         fill=T.CYAN, font=T.display(23))
        logo.create_text(2, 40, text="LIVE COPY-TRADING INTEL  ·  HYPERLIQUID",
                         anchor="w", fill=T.FAINT, font=T.display(9))

        right = tk.Frame(bar, bg=T.DEEP)
        right.pack(side="right", padx=20)
        self.btn_reload = W.NeonButton(right, "REFRESH RANKS",
                                       command=lambda: self.load_leaderboard(force=True),
                                       kind="primary", bg=T.DEEP)
        self.btn_reload.pack(side="right", pady=17)
        W.NeonButton(right, "OPEN SITE",
                     command=lambda: webbrowser.open(src.WEB_LEADERBOARD),
                     kind="ghost", bg=T.DEEP).pack(side="right", padx=10, pady=17)

        tk.Frame(self, bg=T.STROKE, height=1).pack(fill="x")

    def _build_statusbar(self):
        tk.Frame(self, bg=T.STROKE, height=1).pack(fill="x", side="bottom")
        bar = tk.Frame(self, bg=T.DEEP, height=30)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        self.status = tk.Label(bar, text="ready", bg=T.DEEP, fg=T.MUTED,
                               font=T.body(10), anchor="w")
        self.status.pack(side="left", padx=18)
        tk.Label(bar, text="executes no orders  ·  not financial advice",
                 bg=T.DEEP, fg=T.FAINT, font=T.body(10)).pack(side="right", padx=18)

    def say(self, text, color=T.MUTED):
        self.status.config(text=text, fg=color)

    # ------------------------------------------------------------ threading
    def run_bg(self, fn, on_done, on_error=None):
        """fn() runs off the UI thread; on_done(result) runs back on it."""
        def worker():
            try:
                result = fn()
            except src.SourceError as exc:
                self.jobs.put(("err", (on_error, str(exc))))
            except Exception as exc:  # never let a thread kill the window
                self.jobs.put(("err", (on_error, "Unexpected error: %s" % exc)))
            else:
                self.jobs.put(("ok", (on_done, result)))
        threading.Thread(target=worker, daemon=True).start()

    def _pump(self):
        try:
            while True:
                kind, (callback, payload) = self.jobs.get_nowait()
                if kind == "ok":
                    if callback:
                        callback(payload)
                elif kind == "msg":
                    self.say(payload)
                else:
                    self.say(payload, T.RED)
                    if callback:
                        callback(payload)
        except queue.Empty:
            pass
        self.after(60, self._pump)

    def progress(self, text):
        self.jobs.put(("msg", (None, text)))

    # -------------------------------------------------------------- screens
    def show_board(self):
        self.detail.pack_forget()
        self.board.pack(fill="both", expand=True)

    def show_detail(self):
        self.board.pack_forget()
        self.detail.pack(fill="both", expand=True)

    # --------------------------------------------------------------- loading
    def load_leaderboard(self, force=False):
        self.btn_reload.set_enabled(False)
        self.btn_reload.set_text("LOADING…")
        self.say("Loading leaderboard …")

        def work():
            return src.fetch_leaderboard(progress=self.progress, force=force)

        def done(result):
            traders, age = result
            self.traders = traders
            self.board.set_traders(traders)
            self.btn_reload.set_enabled(True)
            self.btn_reload.set_text("REFRESH RANKS")
            origin = "cached, %d min old" % (age // 60) if age else "fresh"
            self.say("%d traders ranked  (%s)" % (len(traders), origin), T.LIME)

        def failed(msg):
            self.btn_reload.set_enabled(True)
            self.btn_reload.set_text("REFRESH RANKS")
            cached = src.load_cached_leaderboard()
            if cached:
                self.traders = cached
                self.board.set_traders(cached)
                self.say("Network failed - showing the last saved leaderboard.", T.GOLD)
            if "certificate" in msg.lower() and not self._warned_certificates:
                self._warned_certificates = True
                messagebox.showwarning(
                    "Certificates missing",
                    "This Mac's Python has no trusted root certificates, so it "
                    "cannot verify any HTTPS connection and no data can be "
                    "loaded.\n\n"
                    "Fix it once: double-click fix_certificates.command in the "
                    "Whale Tracker folder, then start the app again.")

        self.run_bg(work, done, failed)

    def open_trader(self, trader):
        self.current = trader
        self.current_detail = None
        self.detail.begin(trader)
        self.show_detail()
        self.refresh_detail()

    def refresh_detail(self):
        trader = self.current
        if not trader:
            return
        address = trader["address"]
        self.say("Fetching live positions for %s …" % T.short_addr(address))
        self.detail.set_busy(True)

        def work():
            state = src.fetch_positions(address)
            fills = src.fetch_fills(address)
            try:
                mids = src.fetch_mids()
            except src.SourceError:
                mids = {}
            return {"state": state, "fills": fills, "mids": mids}

        def done(data):
            if self.current is not trader:
                return  # the user moved on already
            self.current_detail = data
            self.detail.fill(trader, data)
            self.detail.set_busy(False)
            self.say("Live data updated  ·  %s"
                     % datetime.datetime.now().strftime("%H:%M:%S"), T.LIME)

        def failed(_msg):
            self.detail.set_busy(False)

        self.run_bg(work, done, failed)

    def open_copy_dialog(self):
        if not self.current or not self.current_detail:
            messagebox.showinfo("Still loading",
                                "Live positions have not arrived yet.")
            return
        if not self.current_detail["state"]["positions"]:
            messagebox.showinfo(
                "Nothing to copy",
                "This trader holds no open position right now, so there is "
                "nothing to mirror.")
            return
        CopyDialog(self, self.current, self.current_detail)


# ======================================================================
class BoardScreen(tk.Frame):
    """Home screen: the ranked traders as cards."""

    def __init__(self, parent, app):
        tk.Frame.__init__(self, parent, bg=T.VOID)
        self.app = app
        self.traders = []

        hud = tk.Frame(self, bg=T.VOID)
        hud.pack(fill="x", padx=18, pady=(16, 8))
        self.tiles = []
        for caption in ("TRADERS TRACKED", "COMBINED EQUITY", "TOP PNL", "TIMEFRAME"):
            tile = W.StatTile(hud, caption, "—", bg=T.VOID)
            tile.pack(side="left", padx=(0, 12))
            self.tiles.append(tile)

        controls = tk.Frame(self, bg=T.VOID)
        controls.pack(fill="x", padx=18, pady=(4, 10))

        search = tk.Frame(controls, bg=T.SURFACE, highlightbackground=T.STROKE,
                          highlightthickness=1)
        search.pack(side="left", fill="x", expand=True, padx=(0, 14))
        tk.Label(search, text="⌕", bg=T.SURFACE, fg=T.CYAN,
                 font=T.display(13)).pack(side="left", padx=(12, 6))
        self.query = tk.StringVar()
        self.query.trace_add("write", lambda *_: self.render())
        entry = tk.Entry(search, textvariable=self.query, bg=T.SURFACE, fg=T.TEXT,
                         insertbackground=T.CYAN, relief="flat", font=T.body(12))
        entry.pack(side="left", fill="x", expand=True, pady=9)
        tk.Label(search, text="search wallet", bg=T.SURFACE, fg=T.FAINT,
                 font=T.body(10)).pack(side="right", padx=12)

        self.window_buttons = {}
        for key in src.WINDOWS:
            btn = W.NeonButton(controls, src.WINDOW_LABEL[key],
                               command=lambda k=key: self.set_window(k),
                               kind="ghost", width=92, bg=T.VOID)
            btn.pack(side="left", padx=3)
            self.window_buttons[key] = btn

        self.cards = W.TraderCards(self, on_open=app.open_trader)
        self.cards.pack(fill="both", expand=True, padx=0, pady=(0, 8))

        self.set_window("month", render=False)

    def set_window(self, key, render=True):
        self.app.window_key = key
        for name, btn in self.window_buttons.items():
            btn.set_active(name == key)
        if render:
            self.render()

    def set_traders(self, traders):
        self.traders = traders
        self.render()

    def render(self):
        key = self.app.window_key
        needle = self.query.get().strip().lower()
        rows = [t for t in self.traders
                if not needle
                or needle in t["address"].lower()
                or needle in (t.get("name") or "").lower()]
        rows.sort(key=lambda t: t["perf"].get(key, {}).get("pnl", 0.0), reverse=True)
        rows = rows[:60]

        self.cards.set_items(rows, key)

        equity = sum(t["accountValue"] for t in self.traders)
        best = rows[0]["perf"].get(key, {}).get("pnl", 0.0) if rows else 0.0
        self.tiles[0].render("TRADERS TRACKED", str(len(self.traders)), T.TEXT)
        self.tiles[1].render("COMBINED EQUITY", "$" + T.compact(equity), T.CYAN)
        self.tiles[2].render("TOP PNL", "$" + T.compact(best), T.pnl_color(best))
        self.tiles[3].render("TIMEFRAME", src.WINDOW_LABEL[key], T.VIOLET)


# ======================================================================
class DetailScreen(tk.Frame):
    """One trader: live positions and recent fills."""

    POS_COLS = [
        ("coin", "ASSET", 90, "w"),
        ("side", "SIDE", 80, "w"),
        ("size", "SIZE", 120, "e"),
        ("entry", "ENTRY $", 120, "e"),
        ("notional", "POSITION $", 130, "e"),
        ("lev", "LEV", 120, "e"),
        ("upnl", "UNREAL. PNL $", 130, "e"),
        ("roe", "ROE %", 90, "e"),
        ("liq", "LIQ $", 120, "e"),
    ]
    FILL_COLS = [
        ("time", "TIME", 160, "w"),
        ("coin", "ASSET", 80, "w"),
        ("side", "ACTION", 90, "w"),
        ("dir", "TYPE", 140, "w"),
        ("sz", "SIZE", 120, "e"),
        ("px", "PRICE $", 120, "e"),
        ("pnl", "REALISED $", 120, "e"),
    ]

    def __init__(self, parent, app):
        tk.Frame.__init__(self, parent, bg=T.VOID)
        self.app = app

        nav = tk.Frame(self, bg=T.VOID)
        nav.pack(fill="x", padx=18, pady=(14, 6))
        W.NeonButton(nav, "‹  BACK TO RANKS", command=app.show_board,
                     kind="ghost", width=170, bg=T.VOID).pack(side="left")
        self.btn_refresh = W.NeonButton(nav, "REFRESH", command=app.refresh_detail,
                                        kind="primary", width=120, bg=T.VOID)
        self.btn_refresh.pack(side="right")

        hero = tk.Frame(self, bg=T.VOID)
        hero.pack(fill="x", padx=18, pady=(4, 10))
        self.hero = tk.Canvas(hero, height=92, bg=T.VOID, highlightthickness=0, bd=0)
        self.hero.pack(fill="x")
        self.hero.bind("<Configure>", lambda _e: self._draw_hero())
        self._hero_lines = ("", "")

        tiles = tk.Frame(self, bg=T.VOID)
        tiles.pack(fill="x", padx=18, pady=(0, 12))
        self.tiles = []
        for caption in ("EQUITY", "OPEN POSITIONS", "NOTIONAL", "UNREALISED PNL"):
            tile = W.StatTile(tiles, caption, "—", bg=T.VOID, width=210)
            tile.pack(side="left", padx=(0, 12))
            self.tiles.append(tile)

        # the action bar is packed against the bottom FIRST, so the tables
        # below can never push it out of the window
        foot = tk.Frame(self, bg=T.VOID)
        foot.pack(side="bottom", fill="x", padx=18, pady=14)
        W.NeonButton(foot, "⚡  COPY NOW", command=app.open_copy_dialog,
                     kind="go", height=52, font=T.display(17),
                     width=280, radius=16, bg=T.VOID).pack()

        body = tk.Frame(self, bg=T.VOID)
        body.pack(fill="both", expand=True, padx=18)

        self.lbl_positions = self._heading(body, "OPEN POSITIONS")
        self.pos_tree = self._table(body, self.POS_COLS, 5)
        self._heading(body, "RECENT FILLS  ·  what they just bought and sold")
        self.fill_tree = self._table(body, self.FILL_COLS, 7)

    def _heading(self, parent, text):
        label = tk.Label(parent, text=text, bg=T.VOID, fg=T.FAINT,
                         font=T.display(10), anchor="w")
        label.pack(fill="x", pady=(10, 6))
        return label

    def _table(self, parent, cols, height):
        holder = tk.Frame(parent, bg=T.SURFACE, highlightbackground=T.STROKE,
                          highlightthickness=1)
        holder.pack(fill="both", expand=True)
        tree = ttk.Treeview(holder, columns=[c[0] for c in cols], show="headings",
                            height=height, selectmode="browse", style="Neon.Treeview")
        for key, label, width, anchor in cols:
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor=anchor, stretch=False)
        tree.tag_configure("up", foreground=T.UP)
        tree.tag_configure("down", foreground=T.DOWN)
        tree.tag_configure("plain", foreground=T.MUTED)
        bar = tk.Scrollbar(holder, orient="vertical", command=tree.yview,
                           troughcolor=T.DEEP, bg=T.STROKE, bd=0,
                           highlightthickness=0, width=10)
        tree.configure(yscrollcommand=bar.set)
        tree.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        return tree

    def _draw_hero(self):
        c = self.hero
        c.delete("all")
        width = c.winfo_width()
        if width < 50:
            return
        W.rounded(c, 1, 1, width - 2, 90, 16, fill=T.SURFACE,
                  outline=T.STROKE, width=1)
        c.create_rectangle(2, 16, 6, 74, fill=T.CYAN, outline="")
        title, subtitle = self._hero_lines
        c.create_text(24, 32, text=title, anchor="w", fill=T.TEXT, font=T.display(17))
        c.create_text(24, 60, text=subtitle, anchor="w", fill=T.MUTED, font=T.nums(11))

    def begin(self, trader):
        label = trader.get("name") or T.short_addr(trader["address"], 12, 8)
        self._hero_lines = (label, trader["address"])
        self._draw_hero()
        for tile, caption in zip(self.tiles, ("EQUITY", "OPEN POSITIONS",
                                              "NOTIONAL", "UNREALISED PNL")):
            tile.render(caption, "…", T.FAINT)
        self.pos_tree.delete(*self.pos_tree.get_children())
        self.fill_tree.delete(*self.fill_tree.get_children())

    def set_busy(self, busy):
        self.btn_refresh.set_enabled(not busy)
        self.btn_refresh.set_text("LOADING…" if busy else "REFRESH")

    def fill(self, trader, data):
        state, fills = data["state"], data["fills"]
        positions = state["positions"]
        unrealised = sum(p["uPnl"] for p in positions)

        self.tiles[0].render("EQUITY", "$" + T.compact(state["accountValue"]), T.CYAN)
        self.tiles[1].render("OPEN POSITIONS", str(len(positions)), T.TEXT)
        self.tiles[2].render("NOTIONAL", "$" + T.compact(state["totalNotional"]), T.VIOLET)
        self.tiles[3].render("UNREALISED PNL", "$" + T.compact(unrealised),
                             T.pnl_color(unrealised))
        self.lbl_positions.config(text="OPEN POSITIONS  (%d)" % len(positions))

        self.pos_tree.delete(*self.pos_tree.get_children())
        if not positions:
            self.pos_tree.insert("", "end", values=(
                "—", "no open position", "", "", "", "", "", "", ""), tags=("plain",))
        for i, p in enumerate(positions):
            self.pos_tree.insert("", "end", iid="p%d" % i, values=(
                p["coin"], p["side"], "%.4f" % p["size"], T.money(p["entryPx"], 4),
                T.money(p["notional"], 0), "%.0fx %s" % (p["leverage"], LEV_LABEL.get(p["levType"], p["levType"].upper())),
                T.money(p["uPnl"], 0), T.signed(p["roe"], 1),
                T.money(p["liqPx"], 4) if p["liqPx"] else "—",
            ), tags=("up" if p["uPnl"] >= 0 else "down",))

        self.fill_tree.delete(*self.fill_tree.get_children())
        if not fills:
            self.fill_tree.insert("", "end", values=(
                "—", "no fills found", "", "", "", "", ""), tags=("plain",))
        for i, f in enumerate(fills):
            self.fill_tree.insert("", "end", iid="f%d" % i, values=(
                when(f["time"]), f["coin"], f["side"], f["dir"],
                "%.4f" % f["sz"], T.money(f["px"], 4),
                T.money(f["closedPnl"], 2) if f["closedPnl"] else "—",
            ), tags=("up" if f["side"] == "BUY" else "down",))


# ======================================================================
class CopyDialog(tk.Toplevel):
    """Scales the trader's real positions down onto your own capital."""

    def __init__(self, app, trader, detail):
        tk.Toplevel.__init__(self, app)
        self.app = app
        self.trader = trader
        self.detail = detail
        self.title("Copy Plan · %s" % T.short_addr(trader["address"]))
        self.geometry("920x720")
        self.configure(bg=T.VOID)
        self.transient(app)

        head = tk.Frame(self, bg=T.DEEP, height=60)
        head.pack(fill="x")
        head.pack_propagate(False)
        title = tk.Canvas(head, height=60, bg=T.DEEP, highlightthickness=0, bd=0)
        title.pack(fill="x", padx=20)
        title.create_text(0, 24, text="COPY PLAN", anchor="w", fill=T.LIME,
                          font=T.display(19))
        title.create_text(2, 44, text=trader["address"], anchor="w",
                          fill=T.FAINT, font=T.nums(9))
        tk.Frame(self, bg=T.STROKE, height=1).pack(fill="x")

        controls = tk.Frame(self, bg=T.VOID)
        controls.pack(fill="x", padx=18, pady=14)

        cap = tk.Frame(controls, bg=T.VOID)
        cap.pack(side="left")
        tk.Label(cap, text="YOUR CAPITAL ($)", bg=T.VOID, fg=T.FAINT,
                 font=T.display(9)).pack(anchor="w")
        box = tk.Frame(cap, bg=T.SURFACE, highlightbackground=T.STROKE_HI,
                       highlightthickness=1)
        box.pack(anchor="w", pady=(6, 0))
        self.capital = tk.StringVar(value="1000")
        field = tk.Entry(box, textvariable=self.capital, bg=T.SURFACE, fg=T.LIME,
                         insertbackground=T.LIME, relief="flat",
                         font=T.nums(18, "bold"), width=11, justify="left")
        field.pack(padx=12, pady=8)
        field.bind("<KeyRelease>", lambda _e: self.render())

        tiers = tk.Frame(controls, bg=T.VOID)
        tiers.pack(side="left", padx=24)
        tk.Label(tiers, text="RISK TIER", bg=T.VOID, fg=T.FAINT,
                 font=T.display(9)).pack(anchor="w")
        row = tk.Frame(tiers, bg=T.VOID)
        row.pack(anchor="w", pady=(6, 0))
        self.tier = copyplan.DEFAULT_TIER
        self.tier_buttons = {}
        for key in copyplan.TIER_ORDER:
            btn = W.NeonButton(row, key, command=lambda k=key: self.set_tier(k),
                               kind="ghost", width=110, height=40, bg=T.VOID)
            btn.pack(side="left", padx=(0, 8))
            self.tier_buttons[key] = btn

        self.blurb = tk.Label(self, text="", bg=T.VOID, fg=T.MUTED,
                              font=T.body(11), anchor="w")
        self.blurb.pack(fill="x", padx=18)

        summary = tk.Frame(self, bg=T.VOID)
        summary.pack(fill="x", padx=18, pady=12)
        self.tiles = []
        for caption in ("LEGS", "TOTAL NOTIONAL", "MARGIN NEEDED", "WORST CASE"):
            tile = W.StatTile(summary, caption, "—", bg=T.VOID, width=200, height=70)
            tile.pack(side="left", padx=(0, 12))
            self.tiles.append(tile)

        holder = tk.Frame(self, bg=T.SURFACE, highlightbackground=T.STROKE,
                          highlightthickness=1)
        holder.pack(fill="both", expand=True, padx=18)
        self.text = tk.Text(holder, bg=T.SURFACE, fg=T.TEXT, insertbackground=T.CYAN,
                            relief="flat", font=T.nums(11), wrap="none",
                            padx=14, pady=12, height=10)
        bar = tk.Scrollbar(holder, orient="vertical", command=self.text.yview,
                           troughcolor=T.DEEP, bg=T.STROKE, bd=0,
                           highlightthickness=0, width=10)
        self.text.configure(yscrollcommand=bar.set)
        self.text.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")

        actions = tk.Frame(self, bg=T.VOID)
        actions.pack(fill="x", padx=18, pady=14)
        W.NeonButton(actions, "COPY TO CLIPBOARD", command=self.copy_plan,
                     kind="go", width=230, height=44, font=T.display(13),
                     bg=T.VOID).pack(side="left")
        W.NeonButton(actions, "SAVE AS FILE", command=self.save_plan,
                     kind="primary", width=170, height=44, bg=T.VOID).pack(side="left", padx=10)
        W.NeonButton(actions, "CLOSE", command=self.destroy,
                     kind="ghost", width=120, height=44, bg=T.VOID).pack(side="right")

        self.set_tier(copyplan.DEFAULT_TIER)

    def set_tier(self, key):
        self.tier = key
        for name, btn in self.tier_buttons.items():
            btn.set_active(name == key)
        self.blurb.config(text=copyplan.TIER_BLURB[key])
        self.render()

    def _capital(self):
        raw = (self.capital.get() or "").replace(",", "").replace(" ", "")
        try:
            return max(0.0, float(raw))
        except ValueError:
            return 0.0

    def build(self):
        return copyplan.build_plan(self.detail["state"]["positions"],
                                   self._capital(), self.tier, self.detail["mids"])

    def render(self):
        plan = self.build()
        body = copyplan.plan_as_text(plan, self.trader["address"],
                                     self.trader.get("name", ""),
                                     self.detail["state"]["accountValue"])
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", body)
        self.text.config(state="disabled")

        if plan["legs"]:
            self.tiles[0].render("LEGS", str(len(plan["legs"])), T.TEXT)
            self.tiles[1].render("TOTAL NOTIONAL", "$" + T.money(plan["totalNotional"], 0), T.CYAN)
            self.tiles[2].render("MARGIN NEEDED", "$" + T.money(plan["totalMargin"], 0), T.VIOLET)
            self.tiles[3].render("WORST CASE", "-$" + T.money(plan["totalRisk"], 0), T.RED)
        else:
            for tile, caption in zip(self.tiles, ("LEGS", "TOTAL NOTIONAL",
                                                  "MARGIN NEEDED", "WORST CASE")):
                tile.render(caption, "—", T.FAINT)

    def copy_plan(self):
        self.clipboard_clear()
        self.clipboard_append(self.text.get("1.0", "end-1c"))
        self.app.say("Copy plan is on the clipboard.", T.LIME)

    def save_plan(self):
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".txt",
            initialfile="copyplan_%s.txt" % self.trader["address"][:10],
            filetypes=[("Text file", "*.txt")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(self.text.get("1.0", "end-1c"))
        except OSError as exc:
            messagebox.showerror("Could not save", str(exc), parent=self)
            return
        self.app.say("Plan saved to %s" % path, T.LIME)


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
