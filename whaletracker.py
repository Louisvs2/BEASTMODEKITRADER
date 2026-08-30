#!/usr/bin/env python3
"""
WHALE TRACKER  -  Desktop-Programm (Windows / macOS / Linux)

Zeigt die oeffentliche Trader-Rangliste von Hyperliquid, deren LIVE offene
Positionen und deren zuletzt ausgefuehrte Trades - und rechnet daraus einen
konkreten Copy-Plan fuer das eigene Kapital.

Start:  python3 whaletracker.py      (oder start.command / start.bat)
Nur Standardbibliothek - nichts zu installieren.
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
        "\nFEHLER: Python wurde ohne tkinter installiert.\n"
        "  Windows: Python von python.org neu installieren und dabei\n"
        "           'tcl/tk and IDLE' angehakt lassen.\n"
        "  macOS  : 'brew install python-tk' oder Python von python.org nutzen.\n"
        "  Linux  : 'sudo apt install python3-tk'\n\n"
    )
    raise SystemExit(1)

import hyperliquid_source as src
import copyplan

# ---------------------------------------------------------------- Farben
BG      = "#080b0a"
PANEL   = "#0c110f"
LINE    = "#1e3a2c"
FG      = "#c7dcd1"
DIM     = "#5c7a6c"
ACC     = "#00ff9c"
WARN    = "#ffb020"
BAD     = "#ff4d5e"
SEL     = "#12261d"

MONO = ("Consolas", 10) if sys.platform.startswith("win") else ("Menlo", 11) \
    if sys.platform == "darwin" else ("DejaVu Sans Mono", 10)
MONO_B = (MONO[0], MONO[1], "bold")
MONO_L = (MONO[0], MONO[1] + 8, "bold")
MONO_M = (MONO[0], MONO[1] + 3, "bold")
MONO_S = (MONO[0], max(8, MONO[1] - 1))


def money(value, decimals=2):
    return ("{:,.%df}" % decimals).format(value).replace(",", " ")


def compact(value):
    a = abs(value)
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= div:
            return "%s%.2f%s" % ("-" if value < 0 else "", a / div, suf)
    return "%s%.2f" % ("-" if value < 0 else "", a)


def short_addr(addr):
    return addr if len(addr) <= 14 else addr[:8] + "..." + addr[-6:]


def when(ms):
    if not ms:
        return "-"
    try:
        return datetime.datetime.fromtimestamp(ms / 1000.0).strftime("%d.%m. %H:%M:%S")
    except Exception:
        return "-"


class App(tk.Tk):
    def __init__(self):
        tk.Tk.__init__(self)
        self.title("WHALE TRACKER  //  Hyperliquid Live")
        self.geometry("1180x760")
        self.minsize(900, 600)
        self.configure(bg=BG)

        self.jobs = queue.Queue()
        self.traders = []
        self.window_key = "month"
        self.current = None          # ausgewaehlter Trader
        self.current_detail = None   # dessen Positionen/Fills/Preise

        self._style()
        self._build_header()

        self.container = tk.Frame(self, bg=BG)
        self.container.pack(fill="both", expand=True)
        self.board = BoardView(self.container, self)
        self.detail = DetailView(self.container, self)
        self.show_board()

        self._build_status()
        self.after(80, self._pump)
        self.after(200, self.load_leaderboard)

    # ------------------------------------------------------------ Styling
    def _style(self):
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure("Treeview",
                     background=PANEL, fieldbackground=PANEL, foreground=FG,
                     rowheight=25, borderwidth=0, font=MONO)
        st.configure("Treeview.Heading",
                     background="#0a1712", foreground=DIM, relief="flat",
                     font=(MONO[0], max(8, MONO[1] - 1), "bold"))
        st.map("Treeview.Heading", background=[("active", "#123023")])
        st.map("Treeview",
               background=[("selected", SEL)], foreground=[("selected", ACC)])
        st.configure("Vertical.TScrollbar", background=PANEL, troughcolor=BG,
                     bordercolor=BG, arrowcolor=DIM)

    def _build_header(self):
        head = tk.Frame(self, bg="#0a100e", height=58)
        head.pack(fill="x")
        head.pack_propagate(False)

        left = tk.Frame(head, bg="#0a100e")
        left.pack(side="left", padx=16)
        tk.Label(left, text=">_ WHALETRACKER", bg="#0a100e", fg=ACC,
                 font=MONO_L).pack(anchor="w", pady=(8, 0))
        tk.Label(left, text="Live-Daten von Hyperliquid  //  oeffentlich, ohne Account",
                 bg="#0a100e", fg=DIM, font=MONO_S).pack(anchor="w")

        right = tk.Frame(head, bg="#0a100e")
        right.pack(side="right", padx=16)
        self.btn_reload = tk.Button(
            right, text="RANGLISTE NEU LADEN", command=lambda: self.load_leaderboard(force=True),
            bg=PANEL, fg=ACC, activebackground=ACC, activeforeground="#04120c",
            font=MONO_S, relief="flat", bd=1, padx=12, pady=6,
            highlightbackground=LINE, cursor="hand2")
        self.btn_reload.pack(side="right", pady=12)
        tk.Button(right, text="WEBSITE OEFFNEN",
                  command=lambda: webbrowser.open(src.WEB_LEADERBOARD),
                  bg=PANEL, fg=DIM, activebackground=LINE, activeforeground=FG,
                  font=MONO_S, relief="flat", bd=1, padx=12, pady=6,
                  highlightbackground=LINE, cursor="hand2").pack(side="right", padx=8, pady=12)

        tk.Frame(self, bg=LINE, height=1).pack(fill="x")

    def _build_status(self):
        tk.Frame(self, bg=LINE, height=1).pack(fill="x", side="bottom")
        bar = tk.Frame(self, bg="#0a100e", height=26)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        self.status = tk.Label(bar, text="bereit", bg="#0a100e", fg=DIM,
                               font=MONO_S, anchor="w")
        self.status.pack(side="left", padx=14)
        tk.Label(bar, text="fuehrt keine Orders aus  //  keine Anlageberatung",
                 bg="#0a100e", fg=WARN, font=MONO_S).pack(side="right", padx=14)

    def say(self, text, color=DIM):
        self.status.config(text=text, fg=color)

    # ------------------------------------------------ Hintergrund-Threads
    def run_bg(self, fn, on_done, on_error=None):
        """fn() laeuft im Thread; on_done(ergebnis) laeuft wieder im UI-Thread."""
        def worker():
            try:
                result = fn()
            except src.SourceError as exc:
                self.jobs.put(("err", (on_error, str(exc))))
            except Exception as exc:  # nichts soll das Fenster killen
                self.jobs.put(("err", (on_error, "Unerwarteter Fehler: %s" % exc)))
            else:
                self.jobs.put(("ok", (on_done, result)))
        threading.Thread(target=worker, daemon=True).start()

    def _pump(self):
        try:
            while True:
                kind, (cb, payload) = self.jobs.get_nowait()
                if kind == "ok":
                    if cb:
                        cb(payload)
                elif kind == "msg":
                    self.say(payload)
                else:
                    self.say(payload, BAD)
                    if cb:
                        cb(payload)
        except queue.Empty:
            pass
        self.after(80, self._pump)

    def progress(self, text):
        self.jobs.put(("msg", (None, text)))

    # ------------------------------------------------------------ Ansichten
    def show_board(self):
        self.detail.pack_forget()
        self.board.pack(fill="both", expand=True)

    def show_detail(self):
        self.board.pack_forget()
        self.detail.pack(fill="both", expand=True)

    # ------------------------------------------------------------- Laden
    def load_leaderboard(self, force=False):
        self.btn_reload.config(state="disabled", text="LAEDT ...")
        self.say("Rangliste wird geladen ...")

        def work():
            return src.fetch_leaderboard(progress=self.progress, force=force)

        def done(result):
            traders, age = result
            self.traders = traders
            self.board.fill(traders)
            self.btn_reload.config(state="normal", text="RANGLISTE NEU LADEN")
            hint = " (Cache, %d Min alt)" % (age // 60) if age else " (frisch geladen)"
            self.say("%d Trader in der Rangliste%s" % (len(traders), hint), ACC)

        def failed(_msg):
            self.btn_reload.config(state="normal", text="RANGLISTE NEU LADEN")
            cached = src.load_cached_leaderboard()
            if cached:
                self.traders = cached
                self.board.fill(cached)
                self.say("Netzwerkfehler - zeige zuletzt gespeicherte Rangliste.", WARN)

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
        addr = trader["address"]
        self.say("Hole Live-Positionen von %s ..." % short_addr(addr))
        self.detail.set_busy(True)

        def work():
            state = src.fetch_positions(addr)
            fills = src.fetch_fills(addr)
            try:
                mids = src.fetch_mids()
            except src.SourceError:
                mids = {}
            return {"state": state, "fills": fills, "mids": mids}

        def done(data):
            if self.current is not trader:
                return  # der Nutzer ist inzwischen woanders
            self.current_detail = data
            self.detail.fill(trader, data)
            self.detail.set_busy(False)
            self.say("Live-Daten von %s aktualisiert (%s)"
                     % (short_addr(addr), datetime.datetime.now().strftime("%H:%M:%S")), ACC)

        def failed(_msg):
            self.detail.set_busy(False)

        self.run_bg(work, done, failed)

    def open_copy_dialog(self):
        if not self.current or not self.current_detail:
            messagebox.showinfo("Noch keine Daten",
                                "Die Live-Positionen sind noch nicht geladen.")
            return
        positions = self.current_detail["state"]["positions"]
        if not positions:
            messagebox.showinfo(
                "Nichts zu kopieren",
                "Dieser Trader hat gerade keine offene Position.\n\n"
                "Es gibt also nichts, was man jetzt nachbauen koennte.")
            return
        CopyDialog(self, self.current, self.current_detail)


# ====================================================================
class BoardView(tk.Frame):
    """Startseite: die Rangliste der Trader."""

    COLS = [
        ("rank",  "#",             46,  "center"),
        ("addr",  "WALLET",        210, "w"),
        ("value", "KONTOWERT $",   130, "e"),
        ("pnl",   "PNL $",         130, "e"),
        ("roi",   "ROI %",         90,  "e"),
        ("vlm",   "VOLUMEN $",     130, "e"),
    ]

    def __init__(self, parent, app):
        tk.Frame.__init__(self, parent, bg=BG)
        self.app = app
        self.rows = []

        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(bar, text="// TOP TRADER", bg=BG, fg=DIM, font=MONO_B).pack(side="left")

        self.win_buttons = {}
        for key in src.WINDOWS:
            btn = tk.Button(bar, text=src.WINDOW_LABEL[key],
                            command=lambda k=key: self.set_window(k),
                            bg=PANEL, fg=DIM, activebackground=ACC,
                            activeforeground="#04120c", font=MONO_S, relief="flat",
                            bd=1, padx=10, pady=4, highlightbackground=LINE,
                            cursor="hand2")
            btn.pack(side="right", padx=3)
            self.win_buttons[key] = btn

        srch = tk.Frame(self, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        srch.pack(fill="x", padx=16)
        tk.Label(srch, text=">", bg=PANEL, fg=ACC, font=MONO_B).pack(side="left", padx=(10, 4))
        self.query = tk.StringVar()
        self.query.trace_add("write", lambda *_: self.render())
        entry = tk.Entry(srch, textvariable=self.query, bg=PANEL, fg=FG,
                         insertbackground=ACC, relief="flat", font=MONO)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 10), pady=7)
        tk.Label(srch, text="Wallet-Adresse suchen", bg=PANEL, fg="#3f574c",
                 font=MONO_S).pack(side="right", padx=10)

        wrap = tk.Frame(self, bg=BG)
        wrap.pack(fill="both", expand=True, padx=16, pady=12)
        self.tree = ttk.Treeview(wrap, columns=[c[0] for c in self.COLS],
                                 show="headings", selectmode="browse")
        for key, label, width, anchor in self.COLS:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor=anchor, stretch=(key == "addr"))
        self.tree.tag_configure("up", foreground=ACC)
        self.tree.tag_configure("down", foreground=BAD)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self._open)
        self.tree.bind("<Return>", self._open)

        tk.Label(self, text="Doppelklick auf einen Trader zeigt seine offenen Positionen "
                            "und seine letzten Trades.",
                 bg=BG, fg=DIM, font=MONO_S).pack(anchor="w", padx=16, pady=(0, 10))

        self.set_window("month", render=False)

    def set_window(self, key, render=True):
        self.app.window_key = key
        for k, btn in self.win_buttons.items():
            if k == key:
                btn.config(bg=ACC, fg="#04120c")
            else:
                btn.config(bg=PANEL, fg=DIM)
        if render:
            self.render()

    def fill(self, traders):
        self.rows = traders
        self.render()

    def render(self):
        self.tree.delete(*self.tree.get_children())
        key = self.app.window_key
        needle = self.query.get().strip().lower()

        rows = [t for t in self.rows
                if not needle or needle in t["address"].lower()
                or needle in (t.get("name") or "").lower()]
        rows.sort(key=lambda t: t["perf"].get(key, {}).get("pnl", 0.0), reverse=True)

        for i, t in enumerate(rows, 1):
            p = t["perf"].get(key, {})
            pnl = p.get("pnl", 0.0)
            label = short_addr(t["address"])
            if t.get("name"):
                label = "%s  %s" % (label, t["name"])
            self.tree.insert("", "end", iid=t["address"], values=(
                i, label, money(t["accountValue"], 0),
                money(pnl, 0), "%+.1f" % (p.get("roi", 0.0) * 100),
                compact(p.get("vlm", 0.0)),
            ), tags=("up" if pnl >= 0 else "down",))

    def _open(self, _event=None):
        addr = self.tree.focus()
        if not addr:
            return
        for t in self.rows:
            if t["address"] == addr:
                self.app.open_trader(t)
                return


# ====================================================================
class DetailView(tk.Frame):
    """Ein einzelner Trader: offene Positionen + letzte Trades."""

    POS_COLS = [
        ("coin", "ASSET",       90,  "w"),
        ("side", "RICHTUNG",    90,  "w"),
        ("size", "GROESSE",     120, "e"),
        ("entry", "EINSTIEG $", 120, "e"),
        ("notional", "POSITION $", 130, "e"),
        ("lev", "HEBEL",        80,  "e"),
        ("upnl", "OFFEN PNL $", 120, "e"),
        ("roe", "ROE %",        90,  "e"),
        ("liq", "LIQUIDATION $", 120, "e"),
    ]
    FILL_COLS = [
        ("time", "ZEIT",        150, "w"),
        ("coin", "ASSET",       80,  "w"),
        ("side", "AKTION",      90,  "w"),
        ("dir",  "ART",         140, "w"),
        ("sz",   "MENGE",       120, "e"),
        ("px",   "PREIS $",     120, "e"),
        ("pnl",  "REALISIERT $", 120, "e"),
    ]

    def __init__(self, parent, app):
        tk.Frame.__init__(self, parent, bg=BG)
        self.app = app

        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=16, pady=(12, 0))
        tk.Button(top, text="< ZURUECK ZUR RANGLISTE", command=app.show_board,
                  bg=BG, fg=DIM, activebackground=BG, activeforeground=ACC,
                  font=MONO_S, relief="flat", bd=0, cursor="hand2").pack(side="left")
        self.btn_refresh = tk.Button(top, text="AKTUALISIEREN", command=app.refresh_detail,
                                     bg=PANEL, fg=ACC, activebackground=ACC,
                                     activeforeground="#04120c", font=MONO_S, relief="flat",
                                     bd=1, padx=12, pady=4, highlightbackground=LINE,
                                     cursor="hand2")
        self.btn_refresh.pack(side="right")

        head = tk.Frame(self, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        head.pack(fill="x", padx=16, pady=10)
        self.lbl_addr = tk.Label(head, text="", bg=PANEL, fg=ACC, font=MONO_M,
                                 anchor="w", wraplength=1000, justify="left")
        self.lbl_addr.pack(anchor="w", padx=14, pady=(12, 2))
        row = tk.Frame(head, bg=PANEL)
        row.pack(anchor="w", padx=14, pady=(0, 6))
        tk.Button(row, text="ADRESSE KOPIEREN", command=self._copy_addr,
                  bg=PANEL, fg=DIM, activebackground=LINE, activeforeground=FG,
                  font=MONO_S, relief="flat", bd=1, padx=8, pady=2,
                  highlightbackground=LINE, cursor="hand2").pack(side="left")
        tk.Button(row, text="AUF HYPERLIQUID ANSEHEN", command=self._open_web,
                  bg=PANEL, fg=DIM, activebackground=LINE, activeforeground=FG,
                  font=MONO_S, relief="flat", bd=1, padx=8, pady=2,
                  highlightbackground=LINE, cursor="hand2").pack(side="left", padx=6)
        self.lbl_metrics = tk.Label(head, text="", bg=PANEL, fg=FG, font=MONO,
                                    anchor="w", justify="left")
        self.lbl_metrics.pack(anchor="w", padx=14, pady=(0, 12))

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=16)

        self.lbl_pos = tk.Label(body, text="// OFFENE POSITIONEN", bg=BG, fg=DIM, font=MONO_B)
        self.lbl_pos.pack(anchor="w", pady=(4, 4))
        self.pos_tree = self._table(body, self.POS_COLS, height=7)

        tk.Label(body, text="// ZULETZT AUSGEFUEHRTE TRADES  (was er gerade gekauft/verkauft hat)",
                 bg=BG, fg=DIM, font=MONO_B).pack(anchor="w", pady=(12, 4))
        self.fill_tree = self._table(body, self.FILL_COLS, height=9)

        self.btn_copy = tk.Button(self, text=">_  COPY NOW", command=app.open_copy_dialog,
                                  bg=ACC, fg="#04120c", activebackground="#5affc0",
                                  activeforeground="#04120c", font=MONO_M, relief="flat",
                                  bd=0, pady=12, cursor="hand2")
        self.btn_copy.pack(fill="x", padx=16, pady=12)

    def _table(self, parent, cols, height):
        wrap = tk.Frame(parent, bg=BG)
        wrap.pack(fill="both", expand=True)
        tree = ttk.Treeview(wrap, columns=[c[0] for c in cols], show="headings",
                            height=height, selectmode="browse")
        for key, label, width, anchor in cols:
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor=anchor, stretch=False)
        tree.tag_configure("up", foreground=ACC)
        tree.tag_configure("down", foreground=BAD)
        tree.tag_configure("plain", foreground=FG)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        tree.configure(yscroll=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        return tree

    def begin(self, trader):
        self.lbl_addr.config(text=trader["address"])
        name = ("  //  %s" % trader["name"]) if trader.get("name") else ""
        self.lbl_metrics.config(
            text="Rangliste: Kontowert %s $   |   30-Tage-PnL %s $%s\nLive-Daten werden geladen ..."
                 % (money(trader["accountValue"], 0),
                    money(trader["perf"]["month"]["pnl"], 0), name))
        self.pos_tree.delete(*self.pos_tree.get_children())
        self.fill_tree.delete(*self.fill_tree.get_children())

    def set_busy(self, busy):
        self.btn_refresh.config(state="disabled" if busy else "normal",
                                text="LAEDT ..." if busy else "AKTUALISIEREN")

    def fill(self, trader, data):
        state, fills, mids = data["state"], data["fills"], data["mids"]
        positions = state["positions"]
        upnl = sum(p["uPnl"] for p in positions)

        self.lbl_metrics.config(
            text="Kontowert %s $   |   Offene Positionen %d   |   Nominal %s $   "
                 "|   Nicht realisiert %s $   |   Frei %s $"
                 % (money(state["accountValue"], 0), len(positions),
                    money(state["totalNotional"], 0), money(upnl, 0),
                    money(state["withdrawable"], 0)))
        self.lbl_pos.config(text="// OFFENE POSITIONEN  (%d)" % len(positions))

        self.pos_tree.delete(*self.pos_tree.get_children())
        if not positions:
            self.pos_tree.insert("", "end", values=(
                "-", "keine offene Position", "", "", "", "", "", "", ""), tags=("plain",))
        for i, p in enumerate(positions):
            self.pos_tree.insert("", "end", iid="p%d" % i, values=(
                p["coin"], p["side"], "%.4f" % p["size"], money(p["entryPx"], 4),
                money(p["notional"], 0), "%.0fx %s" % (p["leverage"], p["levType"]),
                money(p["uPnl"], 0), "%+.1f" % p["roe"],
                money(p["liqPx"], 4) if p["liqPx"] else "-",
            ), tags=("up" if p["uPnl"] >= 0 else "down",))

        self.fill_tree.delete(*self.fill_tree.get_children())
        if not fills:
            self.fill_tree.insert("", "end", values=(
                "-", "keine Trades gefunden", "", "", "", "", ""), tags=("plain",))
        for i, f in enumerate(fills):
            self.fill_tree.insert("", "end", iid="f%d" % i, values=(
                when(f["time"]), f["coin"], f["side"], f["dir"],
                "%.4f" % f["sz"], money(f["px"], 4),
                money(f["closedPnl"], 2) if f["closedPnl"] else "-",
            ), tags=("up" if f["side"] == "KAUF" else "down",))

    def _copy_addr(self):
        if self.app.current:
            self.clipboard_clear()
            self.clipboard_append(self.app.current["address"])
            self.app.say("Adresse in die Zwischenablage kopiert.", ACC)

    def _open_web(self):
        if self.app.current:
            webbrowser.open("https://app.hyperliquid.xyz/trade")


# ====================================================================
class CopyDialog(tk.Toplevel):
    """Rechnet die echten Positionen auf das eigene Kapital herunter."""

    def __init__(self, app, trader, detail):
        tk.Toplevel.__init__(self, app)
        self.app = app
        self.trader = trader
        self.detail = detail
        self.title("COPY NOW  -  %s" % short_addr(trader["address"]))
        self.geometry("900x680")
        self.configure(bg=BG)
        self.transient(app)

        head = tk.Frame(self, bg="#0a100e")
        head.pack(fill="x")
        tk.Label(head, text=">_ COPY ENGINE", bg="#0a100e", fg=ACC,
                 font=MONO_M).pack(side="left", padx=14, pady=10)
        tk.Label(head, text=short_addr(trader["address"]), bg="#0a100e", fg=DIM,
                 font=MONO_S).pack(side="right", padx=14)
        tk.Frame(self, bg=LINE, height=1).pack(fill="x")

        ctl = tk.Frame(self, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        ctl.pack(fill="x", padx=14, pady=12)

        tk.Label(ctl, text="DEIN KAPITAL ($)", bg=PANEL, fg=DIM,
                 font=MONO_S).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))
        self.capital = tk.StringVar(value="1000")
        entry = tk.Entry(ctl, textvariable=self.capital, bg="#060908", fg=ACC,
                         insertbackground=ACC, relief="flat", font=MONO_M, width=12)
        entry.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 12), ipady=4)
        entry.bind("<KeyRelease>", lambda _e: self.render())

        tk.Label(ctl, text="RISIKO", bg=PANEL, fg=DIM,
                 font=MONO_S).grid(row=0, column=1, sticky="w", padx=12, pady=(10, 2))
        modes = tk.Frame(ctl, bg=PANEL)
        modes.grid(row=1, column=1, sticky="w", padx=12, pady=(0, 12))
        self.mode = copyplan.DEFAULT_MODE
        self.mode_buttons = {}
        for key in ("VORSICHTIG", "AUSGEWOGEN", "AGGRESSIV"):
            btn = tk.Button(modes, text=key, command=lambda k=key: self.set_mode(k),
                            bg=PANEL, fg=DIM, activebackground=ACC,
                            activeforeground="#04120c", font=MONO_S, relief="flat",
                            bd=1, padx=12, pady=6, highlightbackground=LINE,
                            cursor="hand2")
            btn.pack(side="left", padx=3)
            self.mode_buttons[key] = btn

        self.summary = tk.Label(self, text="", bg=BG, fg=ACC, font=MONO_B,
                                anchor="w", justify="left")
        self.summary.pack(fill="x", padx=14)

        wrap = tk.Frame(self, bg=BG)
        wrap.pack(fill="both", expand=True, padx=14, pady=10)
        self.text = tk.Text(wrap, bg=PANEL, fg=FG, insertbackground=ACC,
                            relief="flat", font=MONO, wrap="none", padx=12, pady=10)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        self.text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        actions = tk.Frame(self, bg=BG)
        actions.pack(fill="x", padx=14, pady=(0, 14))
        tk.Button(actions, text="PLAN IN DIE ZWISCHENABLAGE", command=self.copy_plan,
                  bg=ACC, fg="#04120c", activebackground="#5affc0",
                  activeforeground="#04120c", font=MONO_B, relief="flat",
                  bd=0, padx=18, pady=10, cursor="hand2").pack(side="left")
        tk.Button(actions, text="ALS DATEI SPEICHERN", command=self.save_plan,
                  bg=PANEL, fg=ACC, activebackground=LINE, activeforeground=ACC,
                  font=MONO_S, relief="flat", bd=1, padx=14, pady=10,
                  highlightbackground=LINE, cursor="hand2").pack(side="left", padx=8)
        tk.Button(actions, text="SCHLIESSEN", command=self.destroy,
                  bg=PANEL, fg=DIM, activebackground=LINE, activeforeground=FG,
                  font=MONO_S, relief="flat", bd=1, padx=14, pady=10,
                  highlightbackground=LINE, cursor="hand2").pack(side="right")

        self.set_mode(copyplan.DEFAULT_MODE)

    def set_mode(self, key):
        self.mode = key
        for k, btn in self.mode_buttons.items():
            if k == key:
                btn.config(bg=ACC, fg="#04120c")
            else:
                btn.config(bg=PANEL, fg=DIM)
        self.render()

    def _capital(self):
        raw = (self.capital.get() or "").replace(",", ".").replace(" ", "")
        try:
            return max(0.0, float(raw))
        except ValueError:
            return 0.0

    def build(self):
        return copyplan.build_plan(
            self.detail["state"]["positions"],
            self._capital(), self.mode, self.detail["mids"])

    def render(self):
        plan = self.build()
        text = copyplan.plan_as_text(
            plan, self.trader["address"], self.trader.get("name", ""),
            self.detail["state"]["accountValue"])
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.text.config(state="disabled")

        if plan["legs"]:
            self.summary.config(
                text="%d Positionen  |  Nominal %s $  |  Margin %s $  |  Maximaler Verlust %s $"
                     % (len(plan["legs"]), money(plan["totalNotional"]),
                        money(plan["totalMargin"]), money(plan["totalRisk"])), fg=ACC)
        else:
            self.summary.config(text="Kein umsetzbarer Plan - Kapital zu klein oder "
                                     "keine offenen Positionen.", fg=WARN)

    def copy_plan(self):
        self.clipboard_clear()
        self.clipboard_append(self.text.get("1.0", "end-1c"))
        self.app.say("Copy-Plan in die Zwischenablage kopiert.", ACC)

    def save_plan(self):
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".txt",
            initialfile="copyplan_%s.txt" % self.trader["address"][:10],
            filetypes=[("Textdatei", "*.txt")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.text.get("1.0", "end-1c"))
        except OSError as exc:
            messagebox.showerror("Fehler beim Speichern", str(exc), parent=self)
            return
        self.app.say("Plan gespeichert: %s" % path, ACC)


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
