"""PDF report (landscape A4) for the master report or any subset of sections."""
import io
import re
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)
from PIL import Image as PILImage

NAVY, BLUE, GREY = colors.HexColor("#14304f"), colors.HexColor("#2a78d6"), colors.HexColor("#7a838e")
ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=20, textColor=NAVY, spaceAfter=10)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=12.5, textColor=NAVY, spaceBefore=8, spaceAfter=2)
BODY = ParagraphStyle("B", parent=ss["BodyText"], fontName="Helvetica", fontSize=10, leading=14, spaceAfter=6)
CAP = ParagraphStyle("C", parent=BODY, textColor=GREY, fontSize=9.5, spaceAfter=4)
KL = ParagraphStyle("KL", parent=BODY, fontSize=8, textColor=GREY, spaceAfter=0, leading=10)
KV = ParagraphStyle("KV", parent=BODY, fontName="Helvetica-Bold", fontSize=15, textColor=NAVY, spaceAfter=0, leading=18)
KN = ParagraphStyle("KN", parent=BODY, fontSize=8, textColor=GREY, spaceAfter=0, leading=10)


def _md(s):
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)


def _img(png, width):
    w, h = PILImage.open(io.BytesIO(png)).size
    return Image(io.BytesIO(png), width=width, height=width * h / w)


def _table(df, avail):
    data = [list(df.columns)] + df.astype(str).values.tolist()
    n = len(df.columns)
    fs = 8 if n <= 9 else 6.8
    first = max(2.6 * cm, avail * (0.14 if n > 9 else 0.18))
    widths = [first] + [(avail - first) / (n - 1)] * (n - 1)
    cell = ParagraphStyle("cell", fontName="Helvetica", fontSize=fs, leading=fs + 2)
    data = [[Paragraph(str(c), ParagraphStyle("h", parent=cell, fontName="Helvetica-Bold", textColor=colors.white)) for c in data[0]]] + \
           [[Paragraph(str(c), cell) for c in r] for r in data[1:]]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f5f7")]),
                           ("LINEBELOW", (0, 0), (-1, -1), .25, colors.HexColor("#dfe3e7")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


def to_pdf(sections, title="RSTL Profitability Report", period="", cover=True):
    buf = io.BytesIO()
    pw, ph = landscape(A4); m = 1.5 * cm; avail = pw - 2 * m
    doc = SimpleDocTemplate(buf, pagesize=(pw, ph), leftMargin=m, rightMargin=m, topMargin=1.4 * cm, bottomMargin=1.4 * cm, title=title)
    story = []
    if cover:
        story += [Spacer(1, 5 * cm), Paragraph(title, ParagraphStyle("T", parent=H1, fontSize=34, leading=40)),
                  Paragraph(period, ParagraphStyle("S", parent=BODY, fontSize=15, textColor=BLUE)),
                  Paragraph("Trading book analysis: volumes, sales, margin, funding and customers", ParagraphStyle("S2", parent=BODY, textColor=GREY)), PageBreak()]
    for i, s in enumerate(sections):
        if i:
            story.append(PageBreak())
        story.append(Paragraph(s.title, H1))
        if s.kpis:
            cells = [[Paragraph(l, KL), Paragraph(v, KV), Paragraph(n, KN)] for l, v, n in s.kpis]
            rows = [cells[j:j + 3] for j in range(0, len(cells), 3)]
            kt = Table([[[c for c in cell] for cell in row] for row in rows], colWidths=[avail / 3] * 3)
            kt.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#dfe3e7")), ("INNERGRID", (0, 0), (-1, -1), .5, colors.HexColor("#dfe3e7")),
                                    ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f7f9fb"))]))
            story += [kt, Spacer(1, 8)]
        for p in s.paras:
            story.append(Paragraph(_md(p), BODY))
        for f in s.figs:
            story.append(KeepTogether([Paragraph(f.title, H2), Paragraph(_md(f.caption), CAP), _img(f.png, min(avail, 22.5 * cm)), Spacer(1, 6)]))
        for t in s.tables:
            blk = [Paragraph(t.title, H2), Spacer(1, 3), _table(t.df, avail), Spacer(1, 8)]
            story += [KeepTogether(blk)] if len(t.df) <= 12 else blk

    def footer(c, d):
        c.saveState(); c.setFont("Helvetica", 8); c.setFillColor(GREY)
        c.drawString(m, .8 * cm, f"{title}  |  {period}"); c.drawRightString(pw - m, .8 * cm, f"Page {d.page}"); c.restoreState()
    doc.build(story, onFirstPage=lambda c, d: None if cover else footer(c, d), onLaterPages=footer)
    return buf.getvalue()
