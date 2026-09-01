#!/usr/bin/env python3
"""
Builds the customer-facing tutorial: BEASTMODE_AI_TOOL_Tutorial.pdf

Only needed when the manual changes - the PDF is committed, so a normal
checkout already has it. Requires reportlab:  pip install reportlab
(The app itself stays dependency-free; this is a tool for the author.)

    python3 make_tutorial.py
"""
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether,
                                ListFlowable,
                                ListItem, NextPageTemplate, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table,
                                TableStyle)

OUT = "BEASTMODE_AI_TOOL_Tutorial.pdf"
IMAGES = "docs/images"

INK = colors.HexColor("#12121f")
BODY = colors.HexColor("#2a2a3d")
MUTED = colors.HexColor("#6b6b85")
CYAN = colors.HexColor("#0a8fa8")
LIME = colors.HexColor("#3f7d0a")
RED = colors.HexColor("#c0392b")
RULE = colors.HexColor("#d6d6e2")
PANEL = colors.HexColor("#f4f4f9")

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm

styles = getSampleStyleSheet()
S = {
    "h1": ParagraphStyle("h1", parent=styles["Heading1"], fontName="Helvetica-Bold",
                         fontSize=19, leading=23, textColor=INK,
                         spaceBefore=2, spaceAfter=8),
    "h2": ParagraphStyle("h2", parent=styles["Heading2"], fontName="Helvetica-Bold",
                         fontSize=12.5, leading=16, textColor=CYAN,
                         spaceBefore=13, spaceAfter=5),
    "p": ParagraphStyle("p", parent=styles["BodyText"], fontName="Helvetica",
                        fontSize=10, leading=14.5, textColor=BODY, spaceAfter=7),
    "small": ParagraphStyle("small", parent=styles["BodyText"], fontName="Helvetica",
                            fontSize=8.5, leading=12, textColor=MUTED, spaceAfter=5),
    "step": ParagraphStyle("step", parent=styles["BodyText"], fontName="Helvetica",
                           fontSize=10, leading=14.5, textColor=BODY, spaceAfter=4),
    "mono": ParagraphStyle("mono", parent=styles["BodyText"], fontName="Courier",
                           fontSize=9, leading=12.5, textColor=INK,
                           backColor=PANEL, borderPadding=6, spaceAfter=8),
    "caption": ParagraphStyle("caption", parent=styles["BodyText"], fontName="Helvetica-Oblique",
                              fontSize=8.5, leading=11, textColor=MUTED,
                              alignment=TA_CENTER, spaceAfter=10),
    "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=34,
                            leading=38, textColor=INK, alignment=TA_CENTER),
    "sub": ParagraphStyle("sub", fontName="Helvetica", fontSize=12.5, leading=17,
                          textColor=MUTED, alignment=TA_CENTER),
    "warnhead": ParagraphStyle("warnhead", fontName="Helvetica-Bold", fontSize=10,
                               leading=14, textColor=RED, spaceAfter=3),
}


def steps(items):
    """A numbered list - the format every instruction in here uses."""
    return ListFlowable(
        [ListItem(Paragraph(t, S["step"]), leftIndent=14) for t in items],
        bulletType="1", bulletFontName="Helvetica-Bold", bulletFontSize=10,
        leftIndent=16, bulletDedent=12, spaceAfter=8)


def bullets(items):
    return ListFlowable(
        [ListItem(Paragraph(t, S["step"]), leftIndent=14) for t in items],
        bulletType="bullet", bulletFontName="Helvetica", bulletFontSize=9,
        leftIndent=16, bulletDedent=10, spaceAfter=8)


def panel(title, body_lines, accent=CYAN):
    """A boxed aside - used for warnings and 'if this happens' blocks."""
    inner = [Paragraph(title, ParagraphStyle(
        "pt", fontName="Helvetica-Bold", fontSize=10, leading=14,
        textColor=accent, spaceAfter=4))]
    inner += [Paragraph(line, S["step"]) for line in body_lines]
    table = Table([[inner]], colWidths=[PAGE_W - 2 * MARGIN])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PANEL),
        ("BOX", (0, 0), (-1, -1), 0.8, accent),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def shot(name, caption, width=None):
    path = os.path.join(IMAGES, name)
    if not os.path.exists(path):
        return Paragraph("[missing image: %s]" % name, S["small"])
    from PIL import Image as PILImage
    w, h = PILImage.open(path).size
    target_w = width or (PAGE_W - 2 * MARGIN) * 0.84
    img = Image(path, width=target_w, height=target_w * h / w)
    img.hAlign = "CENTER"
    out = [img]
    if caption:
        out.append(Spacer(1, 3))
        out.append(Paragraph(caption, S["caption"]))
    return out


def table(rows, widths, header=True):
    """Cells are wrapped in Paragraphs - a bare string in a Table does not
    wrap and simply runs off the page edge."""
    cell = ParagraphStyle("cell", fontName="Helvetica", fontSize=9, leading=12,
                          textColor=BODY)
    head = ParagraphStyle("cellhead", parent=cell, fontName="Helvetica-Bold",
                          textColor=INK)
    wrapped = [[Paragraph(str(c), head if (header and r == 0) else cell)
                for c in row] for r, row in enumerate(rows)]
    t = Table(wrapped, colWidths=widths, hAlign="LEFT",
              repeatRows=1 if header else 0)
    style = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), BODY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), PANEL),
                  ("LINEBELOW", (0, 0), (-1, 0), 0.8, CYAN)]
    t.setStyle(TableStyle(style))
    return t


def chrome(canvas, doc):
    """Footer with the page number, on every page but the cover."""
    canvas.saveState()
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 15 * mm, PAGE_W - MARGIN, 15 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN, 10.5 * mm, "BEASTMODE AI TOOL - User Guide")
    canvas.drawRightString(PAGE_W - MARGIN, 10.5 * mm, "Page %d" % (doc.page - 1))
    canvas.restoreState()


def cover(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#0d0d1a"))
    canvas.rect(0, PAGE_H - 132 * mm, PAGE_W, 132 * mm, stroke=0, fill=1)
    canvas.setStrokeColor(colors.HexColor("#22e3ff"))
    canvas.setLineWidth(2)
    canvas.line(0, PAGE_H - 132 * mm, PAGE_W, PAGE_H - 132 * mm)
    canvas.restoreState()


def build():
    doc = BaseDocTemplate(OUT, pagesize=A4,
                          leftMargin=MARGIN, rightMargin=MARGIN,
                          topMargin=MARGIN, bottomMargin=22 * mm,
                          title="BEASTMODE AI TOOL - User Guide",
                          author="BEASTMODE", subject="User guide")
    frame = Frame(MARGIN, 22 * mm, PAGE_W - 2 * MARGIN,
                  PAGE_H - MARGIN - 22 * mm, id="body")
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame], onPage=cover),
        PageTemplate(id="body", frames=[frame], onPage=chrome),
    ])

    story = []

    # ---------------------------------------------------------------- cover
    story.append(Spacer(1, 18 * mm))
    icon = os.path.join(IMAGES, "icon.png")
    if os.path.exists(icon):
        img = Image(icon, width=34 * mm, height=34 * mm)
        img.hAlign = "CENTER"
        story.append(img)
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph('<font color="#ffffff">BEASTMODE</font> '
                           '<font color="#22e3ff">AI TOOL</font>', S["title"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph('<font color="#8a8ab5">LIVE COPY-TRADING INTELLIGENCE</font>',
                           S["sub"]))
    story.append(Spacer(1, 34 * mm))
    story.append(Paragraph("User Guide", ParagraphStyle(
        "ug", parent=S["title"], fontSize=22, textColor=INK)))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("Everything you need to install the app, read a "
                           "trader's live positions, and turn them into a plan "
                           "sized for your own account.", S["sub"]))
    story.append(NextPageTemplate("body"))
    story.append(PageBreak())

    # ------------------------------------------------------------ what it is
    story.append(Paragraph("What this tool does", S["h1"]))
    story.append(Paragraph(
        "On Hyperliquid, every trader's position is public on-chain. Not their "
        "name - their actual open trades, sizes and entry prices. BEASTMODE AI "
        "TOOL reads that public data and puts it in front of you:", S["p"]))
    story.append(bullets([
        "<b>Who is winning right now</b> - the public leaderboard, ranked over "
        "24 hours, 7 days, 30 days or all time.",
        "<b>What they are holding this second</b> - every open position with "
        "size, entry price, leverage, profit and liquidation price.",
        "<b>What they just bought and sold</b> - their most recent executed "
        "trades, to the second.",
        "<b>What that would mean for your account</b> - their positions scaled "
        "down to your capital, with concrete quantities, stop-loss and "
        "take-profit levels.",
    ]))
    story.append(Paragraph("What it does not do", S["h2"]))
    story.append(bullets([
        "It <b>places no orders</b> and is connected to no broker or exchange. "
        "It reads public data and does the arithmetic. Every trade is placed by "
        "you, by hand.",
        "It holds no keys, no passwords and no funds. It never asks you to "
        "connect a wallet.",
        "It does not predict prices. It shows you what large traders are "
        "actually doing and sizes it for your account.",
    ]))
    story.append(panel("Why Hyperliquid and not Binance", [
        "Hyperliquid is the one large exchange where every position is publicly "
        "visible on-chain. On Binance, Coinbase or Bybit you cannot see anyone "
        "else's book at all - which is why copy-trading tools there depend on "
        "people voluntarily publishing their trades.",
    ]))

    # ------------------------------------------------------------- install
    story.append(PageBreak())
    story.append(Paragraph("Installing on your Mac", S["h1"]))
    story.append(steps([
        "Download the file <font face='Courier'>BEASTMODE AI TOOL.dmg</font>.",
        "Double-click the downloaded file. A window opens showing the app icon "
        "next to an Applications folder.",
        "Drag the app icon onto the Applications folder.",
        "Open your Applications folder and double-click <b>BEASTMODE AI TOOL</b>.",
    ]))
    story.append(Paragraph("The window opens and the trader list starts loading. "
                           "The first load takes a few seconds because the full "
                           "ranking is downloaded once; after that it is instant.",
                           S["p"]))

    story.append(panel("First launch: macOS will probably block the app", [
        "This is normal for any app that is not distributed through the Mac App "
        "Store. macOS blocks it until you allow it once. Do this:",
        "<b>1.</b> Double-click the app. A warning appears - click <b>Done</b> "
        "or <b>Cancel</b>.",
        "<b>2.</b> Open <b>System Settings</b> from the Apple menu.",
        "<b>3.</b> Go to <b>Privacy &amp; Security</b> and scroll down.",
        "<b>4.</b> Next to the message about BEASTMODE AI TOOL, click "
        "<b>Open Anyway</b>.",
        "<b>5.</b> Confirm with your password or Touch ID.",
        "You only do this once. Every later launch is a plain double-click.",
    ], accent=RED))

    story.append(Paragraph("If the app opens but the list stays empty", S["h2"]))
    story.append(Paragraph("Look at the bottom left of the window. A red line "
                           "there tells you what went wrong:", S["p"]))
    story.append(table([
        ["Message contains", "What to do"],
        ["certificate", "Your Mac cannot verify secure connections. Open the "
                        "app folder and double-click fix_certificates.command, "
                        "then start the app again."],
        ["No connection", "You are offline, or a VPN or company firewall is "
                          "blocking the connection. Try another network."],
        ["HTTP 429 / 503", "Hyperliquid is rate-limiting or briefly down. Wait a "
                           "minute and press REFRESH RANKS."],
    ], [42 * mm, PAGE_W - 2 * MARGIN - 42 * mm]))

    # -------------------------------------------------------------- screen 1
    story.append(PageBreak())
    story.append(Paragraph("Screen 1 - Ranks", S["h1"]))
    story.append(Paragraph("This is the home screen: the public leaderboard, "
                           "best first.", S["p"]))
    story.extend(shot("screen-ranks.png", "The ranking, sorted by 30-day profit."))
    story.append(Paragraph("Choosing the timeframe", S["h2"]))
    story.append(Paragraph("The four buttons - <b>24H</b>, <b>7D</b>, <b>30D</b>, "
                           "<b>ALL TIME</b> - re-rank the whole list by profit "
                           "over that period. Each one shows its own real "
                           "leaders, so a trader who is hot today can top 24H "
                           "while sitting far down the monthly list.", S["p"]))
    story.append(Paragraph("Reading a card", S["h2"]))
    story.append(table([
        ["Element", "Meaning"],
        ["Number in the ring", "Rank in the selected timeframe. Gold, silver and "
                               "bronze mark the top three."],
        ["Name or address", "The trader's display name if they set one, "
                            "otherwise their wallet address."],
        ["Large green figure", "Profit in US dollars over the selected period. "
                               "Red means a loss."],
        ["ROI", "That profit as a percentage. A large ROI on a small account is "
                "easier than a small ROI on a huge one."],
        ["EQUITY", "How much the account is worth in total."],
        ["Green bar", "This trader's profit compared with the leader's."],
    ], [40 * mm, PAGE_W - 2 * MARGIN - 40 * mm]))
    story.append(Paragraph("Type any wallet address into the search box to find "
                           "one specific trader. <b>REFRESH RANKS</b> re-downloads "
                           "the ranking; <b>OPEN SITE</b> opens the same "
                           "leaderboard on Hyperliquid's own website so you can "
                           "verify anything you see here.", S["p"]))

    # -------------------------------------------------------------- screen 2
    story.append(PageBreak())
    story.append(Paragraph("Screen 2 - The trader", S["h1"]))
    story.append(Paragraph("Click any card to see what that trader is doing "
                           "right now.", S["p"]))
    story.extend(shot("screen-trader.png", "Live positions on top, recent "
                                           "executed trades below."))
    story.append(panel("Two things to check before copying anyone", [
        "<b>Do they hold anything at all?</b> A trader with a huge monthly "
        "profit but no open position has nothing for you to mirror.",
        "<b>Are their positions deep in the red?</b> Then you would be buying "
        "into a losing trade that is already running against them.",
    ]))

    story.append(Paragraph("Open positions", S["h2"]))
    story.append(table([
        ["Column", "Meaning"],
        ["SIDE", "LONG means they profit if the price rises, SHORT if it falls."],
        ["SIZE", "How many coins. Negative numbers are short positions."],
        ["ENTRY", "The average price they paid. Compare it with today's price - "
                  "if the market has already run far past it, you would be "
                  "entering on much worse terms than they did."],
        ["LEV", "Leverage. 5x means a 20 % move against them wipes the position."],
        ["UNREAL. PNL", "Profit or loss they are sitting on right now."],
        ["LIQ", "The price at which the exchange force-closes them."],
    ], [30 * mm, PAGE_W - 2 * MARGIN - 30 * mm]))
    story.append(KeepTogether([
        Paragraph("Recent fills", S["h2"]),
        Paragraph("The lower table is the answer to \"what did they just "
                  "buy?\" - every recent execution with time, asset, "
                  "direction, size and price. <b>REFRESH</b> pulls both "
                  "tables again.", S["p"])]))

    story.append(Paragraph("What goes wrong in practice", S["h1"]))
    story.append(bullets([
        "<b>They exit and you do not notice.</b> The tool shows their live "
        "position, but it cannot ring your phone. Check daily.",
        "<b>You enter later, at a worse price.</b> Their entry is on screen for "
        "exactly this reason - compare before you commit.",
        "<b>Their pain tolerance is not yours.</b> They trade many times your "
        "capital. A 30 % drawdown may be an ordinary week for them and the end "
        "of your account.",
        "<b>Past profit is not a promise.</b> A trader at the top of a 24-hour "
        "ranking may simply have taken one enormous risk that happened to work.",
    ]))

    # -------------------------------------------------------------- screen 3
    story.append(PageBreak())
    story.append(Paragraph("Screen 3 - The copy plan", S["h1"]))
    story.append(Paragraph("Press <b>COPY NOW</b>. Enter your capital, pick a "
                           "risk tier, and the tool scales the trader's real "
                           "positions down onto your account.", S["p"]))
    story.extend(shot("screen-plan.png", "The plan recalculates as you type."))
    story.append(Paragraph("The three risk tiers", S["h2"]))
    story.append(table([
        ["Tier", "Total exposure", "Stop distance", "Max leverage"],
        ["SAFE", "50 % of your capital", "5 %", "2x"],
        ["BALANCED", "100 %", "8 %", "3x"],
        ["DEGEN", "150 %", "12 %", "5x"],
    ], [30 * mm, 45 * mm, 35 * mm, 35 * mm]))
    story.append(Paragraph("A wider stop is not safer. It means each position is "
                           "allowed to move further against you before you cut "
                           "it, so a single trade can lose more.", S["small"]))

    story.append(KeepTogether([Paragraph("Reading one order", S["h2"]),
                               Paragraph(
        "<font face='Courier'>1) ETH  BUY / LONG<br/>"
        "&nbsp;&nbsp;&nbsp;Size&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; : 0.8065 ETH  at $3,100.00<br/>"
        "&nbsp;&nbsp;&nbsp;Notional&nbsp;&nbsp; : $2,500.00  (50.0 % of the plan)<br/>"
        "&nbsp;&nbsp;&nbsp;Leverage&nbsp;&nbsp; : 3.0x  -&gt;  $833.33 margin<br/>"
        "&nbsp;&nbsp;&nbsp;Stop loss&nbsp; : $2,852.00   (loses about $200.00)<br/>"
        "&nbsp;&nbsp;&nbsp;Take profit: $3,596.00</font>", S["mono"])]))
    story.append(table([
        ["Line", "What to do with it"],
        ["Size", "The quantity to buy, at roughly that price."],
        ["Notional", "The position's dollar value, and its share of the plan."],
        ["Leverage / margin", "Set this leverage; the margin is what is actually "
                              "taken from your balance."],
        ["Stop loss", "Place this together with the order, never later. The "
                      "figure in brackets is what you lose if it triggers."],
        ["Take profit", "Where the plan closes in profit - twice the stop "
                        "distance."],
    ], [36 * mm, PAGE_W - 2 * MARGIN - 36 * mm]))
    story.append(Paragraph("The four tiles above the text summarise the whole "
                           "plan. <b>WORST CASE</b> is the one that matters: what "
                           "you lose if every stop triggers at once. If that "
                           "number is uncomfortable, drop to a lower tier - that "
                           "is exactly what it is there for.", S["p"]))

    story.append(Paragraph("\"POSITION LIMIT APPLIED\"", S["h2"]))
    story.append(Paragraph("No single position in your plan may exceed 40 % of "
                           "it. When a trader is more concentrated than that, "
                           "the surplus is spread across their other positions "
                           "and the plan says so. Your mix is then deliberately "
                           "less concentrated than theirs.", S["p"]))
    story.append(Paragraph("Use <b>COPY TO CLIPBOARD</b> or <b>SAVE AS FILE</b> "
                           "to keep the plan while you place the orders.", S["p"]))

    # ------------------------------------------------------------- workflow
    story.append(PageBreak())
    story.append(Paragraph("A full run, start to finish", S["h1"]))
    story.append(steps([
        "Open the app and let the ranking load.",
        "Pick a timeframe. <b>30D</b> favours consistency; <b>24H</b> favours "
        "whoever is hot today.",
        "Click a trader near the top.",
        "Check they actually hold open positions, and that those positions are "
        "not deep in the red.",
        "Compare their entry prices with today's prices. Far past their entry "
        "means a worse deal for you.",
        "Press <b>COPY NOW</b>.",
        "Enter your real capital - not what you wish you had.",
        "Start at <b>SAFE</b>. Read the <b>WORST CASE</b> figure and decide "
        "whether you could live with that loss.",
        "Copy the plan, then place each order on your exchange <b>with its stop "
        "loss attached</b>.",
        "Come back daily, open the same trader and press <b>REFRESH</b>. If they "
        "have closed a position, decide whether you close yours too.",
    ]))


    # ------------------------------------------------------------ disclaimer
    story.append(PageBreak())
    story.append(Paragraph("Risk and disclaimer", S["h1"]))
    story.append(panel("Read this before you use the tool with real money", [
        "BEASTMODE AI TOOL is an information tool. It displays publicly "
        "available exchange data and performs arithmetic on it. It is "
        "<b>not investment advice</b>, not a recommendation to buy or sell any "
        "asset, and not a managed or automated trading service.",
        "The software places no orders and connects to no broker. Every trade "
        "you make is your own decision and your own responsibility.",
        "Trading leveraged crypto derivatives can lose you your entire deposit, "
        "and can do so quickly. Copying another trader does not reduce that "
        "risk - it adds the risk that they change their mind without telling "
        "you.",
        "The data comes from Hyperliquid's public endpoints. It can be delayed, "
        "incomplete or unavailable, and the authors of this software do not "
        "control it and do not warrant its accuracy.",
        "Never trade with money you cannot afford to lose.",
    ], accent=RED))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("About the data", S["h2"]))
    story.append(Paragraph("The app reads the same public endpoints that "
                           "Hyperliquid's own website uses. No account, no API "
                           "key and no registration is required, and nothing "
                           "about you is transmitted anywhere. The downloaded "
                           "ranking is cached on your own Mac in a hidden "
                           "folder called .beastmode in your home directory.",
                           S["p"]))
    story.append(Paragraph("Privacy", S["h2"]))
    story.append(Paragraph("The app has no analytics, no telemetry and no "
                           "account system. It talks to exactly one host, "
                           "hyperliquid.xyz, and to nothing else.", S["p"]))

    doc.build(story)
    size = os.path.getsize(OUT) / 1024.0
    print("wrote %s (%.0f KB)" % (OUT, size))


if __name__ == "__main__":
    build()
