"""Look and feel of the app: CSS plus the landing-page and header blocks."""
import html
import streamlit as st

CSS = """
<style>
:root{--navy:#14304f;--blue:#2a78d6;--sky:#9dc3f0;--orange:#eb6834;--ink:#14181d;--ink2:#4a525c;--muted:#7a838e;--rule:#dfe3e7;--soft:#f3f6fa}
#MainMenu, footer, header[data-testid="stHeader"]{visibility:hidden;height:0}
.block-container{padding-top:1.4rem;padding-bottom:3rem;max-width:1180px}
html, body, [class*="css"]{font-family:'Inter','Segoe UI',system-ui,sans-serif}

/* hero */
.hero{position:relative;overflow:hidden;border-radius:18px;padding:46px 44px 40px;color:#fff;
  background:radial-gradient(900px 340px at 100% 0%,rgba(42,120,214,.55),transparent 60%),linear-gradient(135deg,#0d2038 0%,#14304f 55%,#1d4f86 100%)}
.hero:after{content:"";position:absolute;right:-60px;bottom:-90px;width:300px;height:300px;border-radius:50%;
  border:46px solid rgba(235,104,52,.22)}
.hero .eyebrow{font-size:12.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--sky);font-weight:600}
.hero h1{font-size:clamp(30px,5vw,46px);line-height:1.1;margin:10px 0 12px;color:#fff;font-weight:800;padding:0}
.hero p{max-width:640px;color:#d3deec;font-size:16.5px;line-height:1.55;margin:0 0 20px}
.chips{display:flex;flex-wrap:wrap;gap:8px;position:relative;z-index:1}
.chip{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);border-radius:999px;padding:5px 14px;font-size:13px;color:#fff}

/* feature cards */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:14px;margin:26px 0 8px}
.card{background:#fff;border:1px solid var(--rule);border-radius:14px;padding:18px 18px 16px;border-top:4px solid var(--blue);
  box-shadow:0 1px 2px rgba(20,48,79,.05);transition:transform .15s, box-shadow .15s}
.card:hover{transform:translateY(-2px);box-shadow:0 8px 22px rgba(20,48,79,.10)}
.card.o{border-top-color:var(--orange)}.card.g{border-top-color:#1a7f4b}.card.n{border-top-color:var(--navy)}
.card h4{margin:0 0 6px;font-size:15.5px;color:var(--navy);font-weight:700}
.card p{margin:0;font-size:13.5px;line-height:1.5;color:var(--ink2)}

/* steps */
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin:6px 0 4px}
.step{display:flex;gap:12px;align-items:flex-start;background:var(--soft);border-radius:12px;padding:14px 16px}
.step b.num{flex:0 0 30px;height:30px;border-radius:50%;background:var(--navy);color:#fff;display:flex;align-items:center;justify-content:center;font-size:14px}
.step span{font-size:13.5px;color:var(--ink2);line-height:1.45}.step span strong{color:var(--navy);display:block;font-size:14.5px}
.sec-title{font-size:13px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);font-weight:700;margin:26px 0 8px}
.note{font-size:12.5px;color:var(--muted);margin-top:10px}

/* upload card */
div[data-testid="stFileUploader"] section{border:2px dashed #7fb0ea;background:linear-gradient(180deg,#f6faff,#eef5fd);border-radius:14px;padding:26px}
div[data-testid="stFileUploader"] section:hover{border-color:var(--blue);background:#eaf3fe}
div[data-testid="stFileUploader"] button{background:var(--blue);color:#fff;border:0;border-radius:8px;font-weight:600}
div[data-testid="stFileUploader"] button:hover{background:#1f63b5;color:#fff}

/* report view */
.banner{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:10px;border-radius:14px;padding:18px 24px;color:#fff;
  background:linear-gradient(120deg,#0d2038,#14304f 60%,#1d4f86)}
.banner h2{margin:0;color:#fff;font-size:22px;font-weight:800;padding:0}
.banner small{color:#cddcf0;font-size:13px}
.pill{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.25);border-radius:999px;padding:4px 14px;font-size:12.5px;color:#fff}
div[data-testid="stMetric"]{background:#fff;border:1px solid var(--rule);border-left:4px solid var(--blue);border-radius:12px;padding:12px 14px;box-shadow:0 1px 2px rgba(20,48,79,.05)}
div[data-testid="stMetricLabel"] p{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
div[data-testid="stMetricValue"]{color:var(--navy);font-weight:800}
button[data-baseweb="tab"]{font-weight:600;color:var(--ink2)}
button[data-baseweb="tab"][aria-selected="true"]{color:var(--navy)}
div[data-baseweb="tab-highlight"]{background:var(--orange);height:3px}
.stDownloadButton button{border-radius:10px;font-weight:600;border:1px solid #c5d3e3;background:#fff;color:var(--navy)}
.stDownloadButton button:hover{border-color:var(--blue);color:var(--blue)}
.stDownloadButton button[kind="primary"]{background:var(--orange);border-color:var(--orange);color:#fff}
.stDownloadButton button[kind="primary"]:hover{background:#d2551f;color:#fff}
h3{color:var(--navy)}
.banner{margin-bottom:12px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:12px;margin:6px 0 14px}
.kpi{background:#fff;border:1px solid var(--rule);border-left:4px solid var(--blue);border-radius:12px;padding:12px 14px;box-shadow:0 1px 2px rgba(20,48,79,.05);min-width:0}
.kpi:nth-child(3n+2){border-left-color:var(--orange)}.kpi:nth-child(3n){border-left-color:#1a7f4b}
.kpi .l{font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:600}
.kpi .v{font-size:24px;font-weight:800;color:var(--navy);line-height:1.25;white-space:nowrap}
.kpi .n{font-size:12px;color:var(--ink2);line-height:1.35}
@media (max-width:640px){.hero{padding:30px 22px}}
</style>
"""


def inject():
    st.markdown(CSS, unsafe_allow_html=True)


def hero():
    st.markdown("""
<div class="hero">
  <div class="eyebrow">Trading book analytics</div>
  <h1>RSTL Profitability Report</h1>
  <p>Upload your RSTL tracker and get volumes, sales, margin, funding and customer performance in minutes, with a master report ready to present.</p>
  <div class="chips"><span class="chip">Volume trend</span><span class="chip">Sales</span><span class="chip">Margin realised</span>
  <span class="chip">FAB vs OMNI</span><span class="chip">Facility use</span><span class="chip">Customers</span></div>
</div>""", unsafe_allow_html=True)


def features():
    st.markdown("""
<div class="cards">
  <div class="card"><h4>Instant analysis</h4><p>Net margin rebuilt from SALES and PURCHASES, including RSTL financing cost on every drawdown.</p></div>
  <div class="card o"><h4>Charts that present</h4><p>Monthly volume with trend line, margin bridge, FAB vs OMNI split, product and facility mix.</p></div>
  <div class="card g"><h4>Findings in words</h4><p>A written summary of what changed, what earns most, and where the risks are.</p></div>
  <div class="card n"><h4>Master report</h4><p>Download a PowerPoint or PDF, or just one section. Excel tables included.</p></div>
</div>""", unsafe_allow_html=True)


def steps():
    st.markdown("""
<div class="sec-title">How it works</div>
<div class="steps">
  <div class="step"><b class="num">1</b><span><strong>Upload the tracker</strong>The .xlsx with SALES and PURCHASES sheets.</span></div>
  <div class="step"><b class="num">2</b><span><strong>Review the tabs</strong>Summary, volume, margin, trades, mix, customers, funding.</span></div>
  <div class="step"><b class="num">3</b><span><strong>Download and present</strong>Master report as PowerPoint or PDF.</span></div>
</div>
<div class="note">Your file is processed in this session only and is not stored.</div>""", unsafe_allow_html=True)


def upload_heading():
    st.markdown('<div class="sec-title">Start here</div>', unsafe_allow_html=True)


def banner(period, filename):
    st.markdown(f"""
<div class="banner">
  <div><h2>RSTL Profitability Report</h2><small>{html.escape(period)}</small></div>
  <span class="pill">{html.escape(filename)}</span>
</div>""", unsafe_allow_html=True)


def kpi_grid(kpis):
    cells = "".join(f'<div class="kpi"><div class="l">{html.escape(l)}</div><div class="v">{html.escape(v)}</div>'
                    f'<div class="n">{html.escape(n)}</div></div>' for l, v, n in kpis)
    st.markdown(f'<div class="kpis">{cells}</div>', unsafe_allow_html=True)
