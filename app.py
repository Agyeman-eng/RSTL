import io
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import analysis as A

st.set_page_config(page_title="RSTL Profitability", layout="wide")
BLUE, ORANGE, GOOD, BAD = "#2a78d6", "#eb6834", "#1a7f4b", "#c9302c"
m_ = lambda v: f"{v/1e6:,.2f}m"

st.title("RSTL Profitability Report")
st.caption("Upload the RSTL tracker workbook. It needs SALES and PURCHASES sheets in the usual layout.")
up = st.sidebar.file_uploader("RSTL tracker (.xlsx)", type=["xlsx"])
if not up:
    st.info("Upload the tracker in the sidebar to generate the report.")
    st.stop()

@st.cache_data(show_spinner="Reading workbook")
def _load(b): return A.load(io.BytesIO(b))
try:
    S, P = _load(up.getvalue())
except Exception as e:
    st.error(f"Could not read the workbook: {e}"); st.stop()

auto = A.infer_rate(P)
st.sidebar.markdown("**Assumptions**")
rate = st.sidebar.number_input("Interest rate (% p.a.)", 0.0, 40.0, round(auto * 100, 2), 0.01,
                               help="Detected from drawdowns with interest already booked. Used only where interest is missing.") / 100
asof = pd.Timestamp(st.sidebar.date_input("Accrue open loans to", S.Date.max().date()))
R = A.analyse(S, P, rate, asof)
T, M, t, C = R["T"], R["M"], R["tot"], R["cuts"]
lab = [f"{i.strftime('%b %Y')}{'*' if M.Partial[i] else ''}" for i in M.index]

k = st.columns(6)
k[0].metric("Volume sold", f"{t['vol']/1e6:,.1f}m L", f"{t['vol']/t['pq']:.0%} of purchased", delta_color="off")
k[1].metric("Sales", f"GHS {t['rev']/1e6:,.1f}m")
k[2].metric("Margin pre-financing", f"GHS {t['gm']/1e6:,.1f}m", f"{t['gm']/t['rev']:.1%} of sales", delta_color="off")
k[3].metric("Financing cost", f"GHS {t['fin']/1e6:,.2f}m")
k[4].metric("Net margin", f"GHS {t['nm']/1e6:,.1f}m", f"{t['nm']/t['rev']:.1%} of sales", delta_color="off")
k[5].metric("Return on own cash", f"{t['nm']/t['own']:.1%}" if t["own"] else "n/a")

tabs = st.tabs(["Summary", "Monthly", "Trades", "Mix", "Customers", "Funding", "Notes", "Export"])
with tabs[0]:
    for para in A.narrative(R): st.markdown(para)

with tabs[1]:
    basis = st.radio("Volume basis", ["Sold", "Purchased"], horizontal=True)
    col = "Vol" if basis == "Sold" else "PVol"
    idx, fit, slope = A.trend(M, col)
    fig = go.Figure()
    fig.add_bar(x=lab, y=M[col] / 1e6, marker_color=[BLUE if not p else "#9dc3f0" for p in M.Partial],
                text=[f"{v/1e6:.2f}" for v in M[col]], textposition="outside", name=f"Litres {basis.lower()}")
    fig.add_scatter(x=[lab[list(M.index).index(i)] for i in idx], y=fit / 1e6, mode="lines",
                    line=dict(color=ORANGE, dash="dash", width=3), name="Linear trend (full months)")
    fig.update_layout(yaxis_title="Million litres", height=430, margin=dict(t=30), legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, width="stretch")
    st.caption("* partial month, excluded from the trend. Trend slope: "
               f"{slope/1e6:+.2f} million litres per month.")
    c1, c2 = st.columns(2)
    f1 = go.Figure(go.Bar(x=lab, y=M.Rev / 1e6, marker_color=BLUE)); f1.update_layout(title="Sales revenue (GHS m)", height=320)
    f2 = go.Figure(go.Bar(x=lab, y=M.NM / 1e6, marker_color=[GOOD if v >= 0 else BAD for v in M.NM])); f2.update_layout(title="Net margin (GHS m)", height=320)
    c1.plotly_chart(f1, width="stretch"); c2.plotly_chart(f2, width="stretch")
    fc = go.Figure(go.Scatter(x=R["daily"].index, y=R["daily"] / 1e6, fill="tozeroy", line=dict(color=BLUE)))
    fc.update_layout(title="Cumulative net margin (GHS m)", height=300); st.plotly_chart(fc, width="stretch")
    show = M.copy(); show.index = lab
    st.dataframe(show[["Vol", "Rev", "Cogs", "Other", "GM", "Fin", "NM", "NMpct", "NMpl"]].rename(columns={
        "Vol": "Litres sold", "Rev": "Sales", "Cogs": "Cost of product", "Other": "Licence & other", "GM": "Margin pre-fin.",
        "Fin": "Financing", "NM": "Net margin", "NMpct": "Net % sales", "NMpl": "Net/L"}).style.format(
        {"Litres sold": "{:,.0f}", "Sales": "{:,.0f}", "Cost of product": "{:,.0f}", "Licence & other": "{:,.0f}", "Margin pre-fin.": "{:,.0f}",
         "Financing": "{:,.0f}", "Net margin": "{:,.0f}", "Net % sales": "{:.1%}", "Net/L": "{:.2f}"}), width="stretch")

with tabs[2]:
    d = T[["Funder", "Prod", "Sup", "Start", "PQ", "Sold", "Liq", "Rev", "GM", "Fin", "NM", "NMpl", "NMpct", "DaysToSell", "Status"]].copy()
    d["Start"] = d.Start.dt.date
    d.columns = ["Funder", "Product", "Supplier", "Bought", "Purchased L", "Sold L", "Sold %", "Sales", "Margin pre-fin.", "Financing", "Net margin", "Net/L", "Net %", "Days to sell", "Status"]
    st.dataframe(d.style.format({"Purchased L": "{:,.0f}", "Sold L": "{:,.0f}", "Sold %": "{:.0%}", "Sales": "{:,.0f}", "Margin pre-fin.": "{:,.0f}",
                 "Financing": "{:,.0f}", "Net margin": "{:,.0f}", "Net/L": "{:.2f}", "Net %": "{:.1%}", "Days to sell": "{:.0f}"}).map(
        lambda v: f"color:{BAD}" if isinstance(v, (int, float)) and v < 0 else "", subset=["Net margin", "Net/L", "Net %"]), width="stretch", height=600)
    fb = go.Figure(go.Bar(y=T.index, x=T.NM / 1e6, orientation="h", marker_color=[GOOD if v >= 0 else BAD for v in T.NM]))
    fb.update_layout(title="Net margin by trade (GHS m)", height=max(350, 22 * len(T)), yaxis=dict(autorange="reversed"))
    st.plotly_chart(fb, width="stretch")

with tabs[3]:
    for key, title in [("prod", "Product"), ("funder", "Funder"), ("depot", "Depot")]:
        st.subheader(f"By {title.lower()}")
        g = C[key].reset_index().rename(columns={C[key].index.name: title, "Vol": "Litres", "Rev": "Sales", "NM": "Net margin", "NMpl": "Net/L", "NMpct": "Net %", "Share": "Share of sales"})
        st.dataframe(g.style.format({"Litres": "{:,.0f}", "Sales": "{:,.0f}", "Net margin": "{:,.0f}", "Net/L": "{:.2f}", "Net %": "{:.1%}", "Share of sales": "{:.1%}"}), width="stretch", hide_index=True)

with tabs[4]:
    n = st.slider("Show top N customers", 5, 40, 15)
    g = C["cust"].head(n).reset_index().rename(columns={"OMC": "Customer", "Vol": "Litres", "Rev": "Sales", "NM": "Net margin", "NMpl": "Net/L", "Share": "Share of sales"})
    st.dataframe(g.style.format({"Litres": "{:,.0f}", "Sales": "{:,.0f}", "Net margin": "{:,.0f}", "Net/L": "{:.2f}", "Share of sales": "{:.1%}", "NMpct": "{:.1%}"}), width="stretch", hide_index=True)
    st.caption(f"{len(C['cust'])} customers. Top 5 = {C['cust'].Share.head(5).sum():.1%} of sales, top 10 = {C['cust'].Share.head(10).sum():.1%}.")

with tabs[5]:
    a = st.columns(4)
    a[0].metric("Product purchased", f"GHS {t['inv']/1e6:,.1f}m"); a[1].metric("Own cash", f"GHS {t['own']/1e6:,.1f}m", f"{t['own']/t['inv']:.1%}", delta_color="off")
    a[2].metric("Bank loan", f"GHS {t['loan']/1e6:,.1f}m"); a[3].metric("Loan still open", f"GHS {t['rem']/1e6:,.1f}m")
    b = st.columns(4)
    b[0].metric("Interest recorded", f"GHS {t['rec']/1e6:,.2f}m"); b[1].metric("Interest estimated", f"GHS {(t['est']+t['accr'])/1e6:,.2f}m")
    b[2].metric("Rate used", f"{t['rate']:.2%}"); b[3].metric("Avg days to sell", f"{t['days']:.0f}")
    st.dataframe(T[["Funder", "Invoice", "Own", "Loan", "Impact", "Rec", "Est", "Accr", "Remaining"]].rename(columns={"Rec": "Interest recorded", "Est": "Interest estimated", "Accr": "Accrued (open)"}).style.format("{:,.0f}", subset=pd.IndexSlice[:, ["Invoice", "Own", "Loan", "Impact", "Interest recorded", "Interest estimated", "Accrued (open)", "Remaining"]]), width="stretch")

with tabs[6]:
    st.markdown("**Method.** Net margin = sales − cost of product − licence and other costs − financing cost. The first appearance of a trade code in PURCHASES is the actual purchase; Own and Impact rows are equity and bank drawdowns.")
    for n_ in A.checks(R): st.markdown(f"- {n_}")

with tabs[7]:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        T.reset_index().assign(Start=lambda d: d.Start.dt.date).to_excel(w, sheet_name="Trades", index=False)
        M.reset_index().assign(Month=lambda d: d.Month.astype(str)).to_excel(w, sheet_name="Monthly", index=False)
        for k_, v in C.items(): v.reset_index().to_excel(w, sheet_name=k_.title(), index=False)
        pd.DataFrame({"Summary": [p.replace("**", "") for p in A.narrative(R)]}).to_excel(w, sheet_name="Summary", index=False)
    st.download_button("Download all tables (.xlsx)", buf.getvalue(), "RSTL_report_tables.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
