"""RSTL Profitability App. Run: streamlit run app.py
Layout: app.py (screen) -> rstl/ (loader, analysis, narrative, charts, sections) -> rstl/export/ (pdf, pptx, excel)."""
import hashlib
import io

import pandas as pd
import streamlit as st

from rstl import analysis, loader, sections as SEC
from rstl.export import to_pdf, to_pptx, to_xlsx

st.set_page_config(page_title="RSTL Profitability", layout="wide")
st.title("RSTL Profitability Report")

up = st.sidebar.file_uploader("RSTL tracker (.xlsx)", type=["xlsx"])
if not up:
    st.caption("Upload the RSTL tracker workbook. It needs SALES and PURCHASES sheets in the usual layout.")
    st.info("Upload the tracker in the sidebar to generate the report.")
    st.stop()
data = up.getvalue()
fhash = hashlib.md5(data).hexdigest()


@st.cache_data(show_spinner="Reading workbook")
def read(b):
    return loader.load(io.BytesIO(b))


try:
    S, P = read(data)
except Exception as e:  # noqa: BLE001
    st.error(f"Could not read the workbook: {e}")
    st.stop()

st.sidebar.markdown("**Assumptions**")
rate = st.sidebar.number_input("Interest rate (% p.a.)", 0.0, 40.0, round(loader.infer_rate(P) * 100, 2), 0.01,
                               help="Detected from drawdowns with interest already booked. Used only where interest is missing.") / 100
asof = pd.Timestamp(st.sidebar.date_input("Accrue open loans to", S.Date.max().date()))


@st.cache_resource(show_spinner="Building charts and reports (about 20 seconds the first time)")
def build(_S, _P, key):
    R = analysis.analyse(_S, _P, rate, asof)
    secs, period = SEC.build_sections(R)
    pdfs = {s.key: to_pdf([s], period=period, cover=False) for s in secs}
    return dict(R=R, secs=secs, period=period, pdfs=pdfs, master_pdf=to_pdf(secs, period=period),
                master_pptx=to_pptx(secs, period=period), xlsx=to_xlsx(R, secs))


B = build(S, P, (fhash, round(rate, 6), str(asof.date())))
secs = {s.key: s for s in B["secs"]}

# ---- master report downloads, always visible
st.caption(f"Period: {B['period']}")
c1, c2, c3 = st.columns(3)
c1.download_button("Download master report (PowerPoint)", B["master_pptx"], "RSTL_Master_Report.pptx",
                   "application/vnd.openxmlformats-officedocument.presentationml.presentation", type="primary", width="stretch")
c2.download_button("Download master report (PDF)", B["master_pdf"], "RSTL_Master_Report.pdf", "application/pdf", width="stretch")
c3.download_button("Download all tables (Excel)", B["xlsx"], "RSTL_Tables.xlsx",
                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")

tabs = st.tabs([s.title for s in B["secs"]])
for tab, s in zip(tabs, B["secs"]):
    with tab:
        top, dl = st.columns([4, 1])
        top.subheader(s.title)
        dl.download_button("Download this section (PDF)", B["pdfs"][s.key], f"RSTL_{s.key}.pdf", "application/pdf",
                           key=f"dl_{s.key}", width="stretch")
        if s.kpis:
            cols = st.columns(len(s.kpis))
            for col, (lab, val, note) in zip(cols, s.kpis):
                col.metric(lab, val, note, delta_color="off")
        for p in s.paras:
            st.markdown(p if s.key != "notes" else f"- {p}")
        for f in s.figs:
            st.markdown(f"**{f.title}**")
            st.caption(f.caption)
            st.image(f.png, width="stretch")
        for t in s.tables:
            st.markdown(f"**{t.title}**")
            st.dataframe(t.df, width="stretch", hide_index=True)
