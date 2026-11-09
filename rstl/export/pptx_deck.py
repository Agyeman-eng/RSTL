"""PowerPoint master deck (16:9) built from the report sections."""
import io
import re
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt
from PIL import Image as PILImage

NAVY, BLUE, GREY, INK, LIGHT = RGBColor(0x14, 0x30, 0x4F), RGBColor(0x2A, 0x78, 0xD6), RGBColor(0x7A, 0x83, 0x8E), RGBColor(0x14, 0x18, 0x1D), RGBColor(0xF3, 0xF5, 0xF7)
W, H = 13.333, 7.5


def _runs(par, text, size, color=INK, bold=False):
    for chunk in re.split(r"(\*\*.+?\*\*)", text):
        if not chunk:
            continue
        r = par.add_run()
        b = chunk.startswith("**") and chunk.endswith("**")
        r.text = chunk[2:-2] if b else chunk
        r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(size), bold or b, color, "Calibri"


def _text(slide, x, y, w, h, text, size=14, color=INK, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf = tb.text_frame
    tf.word_wrap = True; tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    lines = text if isinstance(text, list) else [text]
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align; p.space_after = Pt(8)
        _runs(p, ln, size, color, bold)
    return tb


def _rect(slide, x, y, w, h, fill, line=None):
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid(); s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
    s.shadow.inherit = False
    return s


def to_pptx(sections, title="RSTL Profitability Report", period=""):
    prs = Presentation(); prs.slide_width, prs.slide_height = Inches(W), Inches(H)
    blank = prs.slide_layouts[6]; n = [0]

    def new(head=None, sub=None):
        s = prs.slides.add_slide(blank); n[0] += 1
        if head:
            _rect(s, 0, 0, .18, 1.25, BLUE)
            _text(s, .55, .32, 12.2, .6, head, 26, NAVY, True)
            if sub:
                _text(s, .55, .92, 12.2, .5, sub, 13.5, GREY)
            _text(s, .55, 7.08, 9, .3, f"{title}  |  {period}", 9, GREY)
            _text(s, 11.8, 7.08, 1, .3, str(n[0]), 9, GREY, align=PP_ALIGN.RIGHT)
        return s

    # cover
    s = new(); _rect(s, 0, 0, W, H, NAVY); _rect(s, .8, 3.0, 1.2, .07, BLUE)
    _text(s, .8, 1.7, 11.5, 1.2, title, 44, RGBColor(255, 255, 255), True)
    _text(s, .8, 3.3, 11.5, .6, period, 22, RGBColor(0x9D, 0xC3, 0xF0))
    _text(s, .8, 4.0, 11.5, .6, "Trading book analysis: volumes, sales, margin, funding and customers", 15, RGBColor(0xC9, 0xCE, 0xD4))

    for sec in sections:
        if sec.kpis:
            s = new(sec.title, "Headline figures")
            cols = 3 if len(sec.kpis) > 4 else len(sec.kpis); cw = (W - 1.1 - .3 * (cols - 1)) / cols
            for i, (l, v, note) in enumerate(sec.kpis):
                x = .55 + (i % cols) * (cw + .3); y = 1.65 + (i // cols) * 1.75
                _rect(s, x, y, cw, 1.55, LIGHT)
                _text(s, x + .2, y + .15, cw - .4, .3, l.upper(), 10.5, GREY, True)
                _text(s, x + .2, y + .5, cw - .4, .6, v, 28, NAVY, True)
                _text(s, x + .2, y + 1.15, cw - .4, .3, note, 10.5, GREY)
            rows = (len(sec.kpis) + cols - 1) // cols
            if sec.key == "summary" and sec.paras:
                _text(s, .55, 1.65 + rows * 1.75 + .1, 12.2, 1.2, sec.paras[0], 13, INK)
        paras = sec.paras[1:] if (sec.key == "summary" and sec.kpis) else (sec.paras if not sec.kpis or sec.key != "summary" else [])
        step = 5 if sec.key != "notes" else 6
        for i in range(0, len(paras), step):
            s = new(sec.title if sec.key != "summary" else "Key findings", "Findings" if sec.key != "notes" else None)
            _text(s, .55, 1.6, 12.2, 5.3, paras[i:i + step], 14, INK)
        for f in sec.figs:
            s = new(f.title, re.sub(r"\*\*", "", f.caption))
            w0, h0 = PILImage.open(io.BytesIO(f.png)).size
            maxw, maxh = 12.3, 5.35
            iw = min(maxw, maxh * w0 / h0); ih = iw * h0 / w0
            s.shapes.add_picture(io.BytesIO(f.png), Inches((W - iw) / 2), Inches(1.5 + (maxh - ih) / 2), Inches(iw), Inches(ih))
        for t in sec.tables:
            df = t.df
            pages = -(-len(df) // 15); per = -(-len(df) // pages)
            for i in range(0, len(df), per):
                chunk = df.iloc[i:i + per]
                s = new(t.title, f"Rows {i+1} to {i+len(chunk)} of {len(df)}" if len(df) > per else None)
                rows, cols = len(chunk) + 1, len(df.columns)
                tbl = s.shapes.add_table(rows, cols, Inches(.55), Inches(1.55), Inches(12.2), Inches(.33 * rows)).table
                fs = 11 if cols <= 7 else (9 if cols <= 10 else 7.5)
                for j, c in enumerate(df.columns):
                    cell = tbl.cell(0, j); cell.text = str(c); cell.fill.solid(); cell.fill.fore_color.rgb = NAVY
                    p = cell.text_frame.paragraphs[0]; p.runs[0].font.size = Pt(fs); p.runs[0].font.bold = True
                    p.runs[0].font.color.rgb = RGBColor(255, 255, 255); p.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.RIGHT
                for r in range(len(chunk)):
                    for j in range(cols):
                        cell = tbl.cell(r + 1, j); cell.text = str(chunk.iloc[r, j]); cell.fill.solid()
                        cell.fill.fore_color.rgb = RGBColor(255, 255, 255) if r % 2 == 0 else LIGHT
                        p = cell.text_frame.paragraphs[0]; p.runs[0].font.size = Pt(fs); p.runs[0].font.color.rgb = INK
                        p.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.RIGHT
                        cell.margin_top = cell.margin_bottom = Inches(.03)
    buf = io.BytesIO(); prs.save(buf)
    return buf.getvalue()
