"""
Custom canvas widgets: rounded neon cards, buttons, bars and a scrollable
card list. Tk's stock widgets are square and grey, so the playful look is
drawn by hand on a Canvas.
"""

import tkinter as tk

import theme as T


def rounded(canvas, x1, y1, x2, y2, r=14, **kw):
    """A rounded rectangle as a smoothed polygon."""
    r = min(r, abs(x2 - x1) / 2, abs(y2 - y1) / 2)
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=16, **kw)


class NeonButton(tk.Canvas):
    """Rounded, glowing button. `kind` picks the colour role."""

    def __init__(self, parent, text, command=None, kind="primary",
                 width=None, height=38, font=None, radius=12, bg=None):
        self.accent = {
            "primary": T.CYAN, "hot": T.MAGENTA, "go": T.LIME,
            "gold": T.GOLD, "ghost": T.STROKE_HI,
        }.get(kind, T.CYAN)
        self.kind = kind
        self.text = text
        self.command = command
        self.radius = radius
        self.enabled = True
        self._font = font or T.display(12)
        self._bg = bg or T.DEEP

        if width is None:
            width = max(96, len(text) * 9 + 34)
        tk.Canvas.__init__(self, parent, width=width, height=height,
                           bg=self._bg, highlightthickness=0, bd=0)
        self._cw, self._ch = width, height
        self._hover = False
        self._draw()
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.configure(cursor="hand2")

    def _draw(self):
        self.delete("all")
        solid = self.kind in ("go", "gold")
        if not self.enabled:
            fill, outline, fg = T.SURFACE, T.STROKE, T.FAINT
        elif solid:
            fill = self.accent if not self._hover else "#ffffff"
            outline, fg = fill, "#07070f"
        elif self._hover:
            fill, outline, fg = T.SURFACE_2, self.accent, self.accent
        else:
            fill, outline, fg = T.SURFACE, T.STROKE_HI, T.TEXT

        rounded(self, 1, 1, self._cw - 1, self._ch - 1, self.radius,
                fill=fill, outline=outline, width=1.5)
        self.create_text(self._cw / 2, self._ch / 2 + 1, text=self.text,
                         fill=fg, font=self._font)

    def set_text(self, text):
        self.text = text
        self._draw()

    def set_enabled(self, value):
        self.enabled = bool(value)
        self.configure(cursor="hand2" if self.enabled else "arrow")
        self._draw()

    def set_active(self, active):
        """For toggle groups: an active button is filled."""
        self.kind = "go" if active else "ghost"
        self.accent = T.LIME if active else T.STROKE_HI
        self._draw()

    def _on_enter(self, _e):
        self._hover = True
        self._draw()

    def _on_leave(self, _e):
        self._hover = False
        self._draw()

    def _on_click(self, _e):
        if self.enabled and self.command:
            self.command()


class Chip(tk.Canvas):
    """Small rounded label, e.g. a tier badge."""

    def __init__(self, parent, text, color=T.CYAN, bg=T.DEEP, font=None):
        font = font or T.display(9)
        width = len(text) * 7 + 20
        tk.Canvas.__init__(self, parent, width=width, height=22,
                           bg=bg, highlightthickness=0, bd=0)
        rounded(self, 1, 1, width - 1, 21, 10, fill="", outline=color, width=1.2)
        self.create_text(width / 2, 12, text=text, fill=color, font=font)


class StatTile(tk.Canvas):
    """A big number with a small caption — the HUD blocks."""

    def __init__(self, parent, caption, value, color=T.TEXT, width=190, height=76,
                 bg=T.DEEP):
        tk.Canvas.__init__(self, parent, width=width, height=height,
                           bg=bg, highlightthickness=0, bd=0)
        self._cw, self._ch = width, height
        self._bg = bg
        self.render(caption, value, color)

    def render(self, caption, value, color=T.TEXT):
        self.delete("all")
        rounded(self, 1, 1, self._cw - 1, self._ch - 1, 14,
                fill=T.SURFACE, outline=T.STROKE, width=1)
        self.create_text(16, 22, text=caption.upper(), anchor="w",
                         fill=T.FAINT, font=T.display(9))
        self.create_text(16, 50, text=value, anchor="w",
                         fill=color, font=T.nums(19, "bold"))


class ScrollArea(tk.Frame):
    """Canvas + scrollbar with mouse-wheel support on every platform."""

    def __init__(self, parent, bg=T.VOID):
        tk.Frame.__init__(self, parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.bar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview,
                                troughcolor=T.DEEP, bg=T.STROKE,
                                activebackground=T.STROKE_HI, bd=0,
                                highlightthickness=0, width=10)
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.bar.pack(side="right", fill="y")
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.bind_all(seq, self._wheel, add="+")

    def _wheel(self, event):
        widget = self.winfo_containing(event.x_root, event.y_root)
        parent = widget
        while parent is not None:
            if parent is self.canvas:
                break
            parent = getattr(parent, "master", None)
        if parent is not self.canvas:
            return
        if getattr(event, "num", None) == 4:
            delta = -1
        elif getattr(event, "num", None) == 5:
            delta = 1
        else:
            delta = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(delta, "units")


class TraderCards(ScrollArea):
    """The leaderboard: one neon card per trader, drawn on a canvas."""

    CARD_H = 100
    GAP = 12
    PAD = 18

    def __init__(self, parent, on_open):
        ScrollArea.__init__(self, parent, bg=T.VOID)
        self.on_open = on_open
        self.items = []
        self.window_key = "month"
        self._hover_id = None
        self.canvas.bind("<Configure>", lambda _e: self.render())
        self.canvas.bind("<Motion>", self._motion)
        self.canvas.bind("<Button-1>", self._click)
        self.canvas.bind("<Leave>", lambda _e: self._set_hover(None))

    def set_items(self, items, window_key):
        self.items = items
        self.window_key = window_key
        self.canvas.yview_moveto(0)
        self.render()

    def render(self):
        c = self.canvas
        c.delete("all")
        width = c.winfo_width()
        if width < 50:
            return

        if not self.items:
            c.create_text(width / 2, 80, text="NO TRADERS MATCH THAT FILTER",
                          fill=T.FAINT, font=T.display(13))
            c.configure(scrollregion=(0, 0, width, 160))
            return

        best = max(abs(i["perf"].get(self.window_key, {}).get("pnl", 0.0))
                   for i in self.items) or 1.0

        y = self.PAD
        for index, trader in enumerate(self.items, 1):
            self._card(c, index, trader, width, y, best)
            y += self.CARD_H + self.GAP
        c.configure(scrollregion=(0, 0, width, y + self.PAD))

    def _card(self, c, rank, trader, width, y, best):
        x1, x2 = self.PAD, width - self.PAD - 2
        y2 = y + self.CARD_H
        tag = "card%d" % rank
        perf = trader["perf"].get(self.window_key, {})
        pnl = perf.get("pnl", 0.0)
        roi = perf.get("roi", 0.0) * 100
        accent = T.MEDALS.get(rank, T.STROKE_HI)

        c.create_rectangle(x1, y, x2, y2, fill="", outline="", tags=(tag, "hit"))
        rounded(c, x1, y, x2, y2, 16, fill=T.SURFACE, outline=T.STROKE,
                width=1, tags=(tag, "bgrect"))
        # accent rail on the left edge
        c.create_rectangle(x1 + 1, y + 14, x1 + 4, y2 - 14, fill=accent,
                           outline="", tags=(tag,))

        # rank badge
        bx, by = x1 + 40, y + self.CARD_H / 2
        c.create_oval(bx - 20, by - 20, bx + 20, by + 20,
                      fill=T.DEEP, outline=accent, width=2, tags=(tag,))
        c.create_text(bx, by + 1, text=str(rank), fill=accent,
                      font=T.display(16), tags=(tag,))

        # identity, left column
        tx = x1 + 76
        label = trader.get("name") or T.short_addr(trader["address"], 10, 6)
        c.create_text(tx, y + 30, text=label, anchor="w", fill=T.TEXT,
                      font=T.display(14), tags=(tag,))
        c.create_text(tx, y + 54, text=T.short_addr(trader["address"], 12, 8),
                      anchor="w", fill=T.FAINT, font=T.nums(10), tags=(tag,))

        # pnl block, right column
        c.create_text(x2 - 24, y + 32, text="$" + T.compact(pnl), anchor="e",
                      fill=T.pnl_color(pnl), font=T.nums(21, "bold"), tags=(tag,))
        c.create_text(x2 - 24, y + 54, text="%s  ·  ROI %s" %
                      (self.window_key.upper(), T.signed(roi, 1, "%")),
                      anchor="e", fill=T.MUTED, font=T.nums(10), tags=(tag,))
        c.create_text(x2 - 24, y + 78, text="EQUITY  $%s" % T.compact(trader["accountValue"]),
                      anchor="e", fill=T.MUTED, font=T.nums(10), tags=(tag,))

        # xp-style bar comparing this trader's pnl with the leader's,
        # on its own row so nothing overlaps it
        bar_x1, bar_x2 = tx, x2 - 230
        if bar_x2 > bar_x1 + 40:
            c.create_rectangle(bar_x1, y + 76, bar_x2, y + 81,
                               fill=T.DEEP, outline="", tags=(tag,))
            filled = bar_x1 + (bar_x2 - bar_x1) * min(1.0, abs(pnl) / best)
            c.create_rectangle(bar_x1, y + 76, filled, y + 81,
                               fill=T.pnl_color(pnl), outline="", tags=(tag,))

        c.itemconfig(tag, tags=(tag, "hit"))
        self._bind_card(tag, trader)

    def _bind_card(self, tag, trader):
        self.canvas.tag_bind(tag, "<Button-1>",
                             lambda _e, t=trader: self.on_open(t))

    def _card_at(self, y_pixel):
        y = self.canvas.canvasy(y_pixel) - self.PAD
        if y < 0:
            return None
        index = int(y // (self.CARD_H + self.GAP))
        if 0 <= index < len(self.items) and (y % (self.CARD_H + self.GAP)) <= self.CARD_H:
            return index + 1
        return None

    def _set_hover(self, rank):
        if rank == self._hover_id:
            return
        for value, colour, fill in ((self._hover_id, T.STROKE, T.SURFACE),
                                    (rank, T.CYAN, T.SURFACE_2)):
            if value:
                for item in self.canvas.find_withtag("card%d" % value):
                    if "bgrect" in self.canvas.gettags(item):
                        self.canvas.itemconfig(item, outline=colour, fill=fill)
        self._hover_id = rank
        self.canvas.configure(cursor="hand2" if rank else "")

    def _motion(self, event):
        self._set_hover(self._card_at(event.y))

    def _click(self, event):
        rank = self._card_at(event.y)
        if rank:
            self.on_open(self.items[rank - 1])
