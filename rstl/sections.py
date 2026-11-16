"""Assemble the report: ordered sections of KPIs, text, charts (as PNG bytes) and tables.
To add a chart or table, write the function in charts.py and add one line here."""
from dataclasses import dataclass, field
import pandas as pd
from . import charts as C, theme as th
from .narrative import narrative, checks, rate_text


@dataclass
class Fig:
    title: str
    caption: str
    png: bytes


@dataclass
class Tbl:
    title: str
    df: pd.DataFrame  # already formatted as text


@dataclass
class Section:
    key: str
    title: str
    paras: list = field(default_factory=list)
    figs: list = field(default_factory=list)
    tables: list = field(default_factory=list)
    kpis: list = field(default_factory=list)  # (label, value, note)


n0 = lambda v: f"{v:,.0f}"
n2 = lambda v: f"{v:,.2f}"
pc = lambda v: f"{v:.1%}"


def _fig(title, caption, f):
    return None if f is None else Fig(title, caption, th.png(f))


def build_sections(R):
    T, M, t, cuts, S = R["T"], R["M"], R["tot"], R["cuts"], R["S"]
    full = M[~M.Partial] if (~M.Partial).sum() else M
    fp, prod, fu = cuts["facility_prod"], cuts["prod"], cuts["funder"]
    cnt = T.Funder.value_counts()
    period = f"{t['first']:%d %b %Y} to {t['last']:%d %b %Y}"

    # ---- summary
    s0 = Section("summary", "Executive summary", paras=narrative(R), kpis=[
        ("Volume sold" + (" (RSTL)" if t["basis"] == "rstl" else ""), f"{t['vol']/1e6:,.1f}m L", f"{t['vol']/t['pq']:.0%} of {t['pq']/1e6:,.1f}m L purchased"),
        ("Sales", f"GHS {t['rev']/1e6:,.1f}m", f"Avg GHS {t['rev']/t['vol']:.2f}/L"),
        ("Margin before financing", f"GHS {t['gm']/1e6:,.1f}m", f"{t['gm']/t['rev']:.1%} of sales"),
        ("Financing cost", f"GHS {t['fin']/1e6:,.2f}m", f"{t['fin']/t['gm']:.0%} of pre-financing margin"),
        ("Net margin", f"GHS {t['nm']/1e6:,.1f}m", f"{t['nm']/t['rev']:.1%} of sales, GHS {t['nm']/t['vol']:.2f}/L"),
        ("Return on own cash", f"{t['nm']/t['own']:.1%}", f"on GHS {t['own']/1e6:,.1f}m own cash")])
    s0.figs.append(_fig("From trading margin to net margin",
                        f"Financing takes {t['fin']/t['gm']:.0%} of the margin before financing; licence and other costs are GHS {t['oth']/1e6:,.2f}m.", C.bridge(R)))

    # ---- volume
    peak = M.Vol.idxmax()
    from .analysis import trend
    k = trend(M)[2]
    s1 = Section("volume", "Volume")
    s1.figs += [
        _fig("Monthly volume with trend", f"{peak.strftime('%B')} was the peak at {M.Vol.max()/1e6:,.1f}m L ({M.Vol.max()/t['vol']:.0%} of the total). "
             f"Trend across full months: {k/1e6:+.1f}m L per month.", C.volume_trend(R, "Sold")),
        _fig("Purchased vs sold", f"{t['vol']/t['pq']:.0%} of purchased litres have been sold. A gap means stock still to be lifted or loadings booked to other trade codes.", C.purchased_vs_sold(R))]
    vt = M.copy(); vt.index = [i.strftime("%b %Y") + (" (partial)" if p else "") for i, p in zip(M.index, M.Partial)]
    s1.tables.append(Tbl("Monthly volume", pd.DataFrame({
        "Litres sold": vt.Vol.map(n0), "Litres purchased": vt.PVol.map(n0), "Product purchased (GHS)": vt.Invoiced.map(n0)}).reset_index(names="Month")))

    # ---- sales & margin
    bad = M[(M.NM < 0) & ~M.Partial]
    s2 = Section("sales", "Sales and margin")
    s2.figs += [
        _fig("Monthly sales", f"Sales of GHS {t['rev']/1e6:,.1f}m at an average realised price of GHS {t['rev']/t['vol']:.2f} per litre.", C.sales_by_month(R)),
        _fig("Monthly net margin (GHS m and % of sales)", f"{full.NM.idxmax().strftime('%B')} was the best full month (GHS {full.NM.max()/1e6:,.1f}m). "
             + (f"Loss in {', '.join(i.strftime('%B') for i in bad.index)}." if len(bad) else "No full month made a loss."), C.net_margin_by_month(R)),
        _fig("Total net margin by product per month (GHS m)", _prod_caption(R), C.margin_by_product(R)),
        _fig("Margin per litre by product", "Net margin per litre after licence costs and financing. Falling lines mean the spread is narrowing.", C.margin_per_litre(R)),
        _fig("Selling price vs total cost per litre", "Total cost per litre = product cost + licence and other costs + financing (the Total Cost/Ltr in the sheet). "
             "The gap is the net margin per litre: green shading is profit, red is selling below total cost.", C.price_vs_cost(R)),
        _fig("Cumulative net margin", _half(R), C.cumulative(R))]
    mt = M.copy(); mt.index = [i.strftime("%b %Y") + (" (partial)" if p else "") for i, p in zip(M.index, M.Partial)]
    pm = S[~S.Loss].groupby(["Prod", "Month"]).NM.sum().unstack(0).reindex(M.index).fillna(0)
    pm = pm[pm.sum().sort_values(ascending=False).index]
    pm.index = [i.strftime("%b %Y") + (" (partial)" if p else "") for i, p in zip(M.index, M.Partial)]
    pmt = pm.map(n0); pmt["Total"] = pm.sum(axis=1).map(n0)
    s2.tables.append(Tbl("Net margin by product and month (GHS)", pmt.reset_index(names="Month")))
    s2.tables.append(Tbl("Monthly profit and loss (GHS)", pd.DataFrame({
        "Litres sold": mt.Vol.map(n0), "Sales": mt.Rev.map(n0), "Product cost": mt.Cogs.map(n0), "Licence & other": mt.Other.map(n0),
        "Margin pre-fin.": mt.GM.map(n0), "Financing": mt.Fin.map(n0), "Net margin": mt.NM.map(n0), "Net % sales": mt.NMpct.map(pc), "Net GHS/L": mt.NMpl.map(n2)}).reset_index(names="Month")))

    # ---- trades
    s3 = Section("trades", "Trades")
    top = T.sort_values("NM", ascending=False)
    s3.figs += [
        _fig("FAB vs OMNI", "  ·  ".join(f"{i}: {cnt[i]} trades, GHS {fu.NMpl.get(i, 0):.2f}/L net" for i in cnt.index) + ".", C.funder_split(R)),
        _fig("Net margin by trade", f"{int((T.NM > 0).sum())} of {len(T)} trades are profitable; {', '.join(top.index[:3])} contributed {top.NM.head(3).sum()/t['nm']:.0%} of net margin.", C.trade_margin(R)),
        _fig("Trade size vs profitability (bubble = sales)", "Larger bubbles are bigger sales. Trades below the zero line lost money per litre.", C.trade_scatter(R)),
        _fig("Days from purchase to loading", f"Litres take {t['days']:.0f} days on average from purchase to loading.", C.days_to_sell(R))]
    d = T.copy(); d["Start"] = d.Start.dt.strftime("%d %b %Y")
    s3.tables.append(Tbl("Trade scorecard (GHS)", pd.DataFrame({
        "Trade": d.index, "Funder": d.Funder.values, "Product": d.Prod.values, "Bought": d.Start.values, "Purchased L": d.PQ.map(n0).values,
        "Sold L": d.Sold.map(n0).values, "Sales": d.Rev.map(n0).values, "Margin pre-fin.": d.GM.map(n0).values, "Financing": d.Fin.map(n0).values,
        "Net margin": d.NM.map(n0).values, "Net GHS/L": d.NMpl.map(n2).values, "Net %": d.NMpct.map(pc).values, "Days": d.DaysToSell.map(n0).values,
        "Status": d.Status.values})))

    if t["basis"] == "rstl":
        sd = t["sheet_diff"]; ox = T[T.Outside.abs() > 0.5].copy()
        if len(ox):
            ox["sh"] = ox.Outside / ox.SoldAll
            s3.tables.append(Tbl("Loadings bought outside RSTL, excluded from this report", pd.DataFrame({
                "Trade": ox.index, "Loaded per SALES (L)": ox.SoldAll.map(n0).values, "Bought outside RSTL (L)": ox.Outside.map(n0).values,
                "RSTL litres (L)": ox.Sold.map(n0).values, "Share outside": ox.sh.map(pc).values,
                "Margin excluded, pre-financing (GHS)": (S[S.ID.isin(ox.index)].groupby("ID").apply(lambda d: (d.GMAll - d.GM).sum(), include_groups=False).reindex(ox.index)).map(n0).values})))

    # ---- product & depot mix
    s4 = Section("mix", "Product, facility and depot mix")
    lead = fp.index[0]
    s4.figs += [
        _fig("Product mix and facility use", f"{lead} used the most facility: GHS {fp.Facility.iloc[0]/1e6:,.0f}m, {fp.FacShare.iloc[0]:.0%} of the GHS {fp.Facility.sum()/1e6:,.0f}m drawn.", C.product_split(R)),
        _fig("Margin per litre by product", f"{prod.NMpl.idxmax()} earns the most per litre (GHS {prod.NMpl.max():.2f}); {prod.NMpl.idxmin()} the least (GHS {prod.NMpl.min():.2f}).", C.product_unit_margin(R)),
        _fig("Depot", f"{cuts['depot'].Vol.idxmax()} handles the most litres ({cuts['depot'].Vol.max()/cuts['depot'].Vol.sum():.0%}).", C.depot_chart(R))]
    s4.tables.append(Tbl("Facility use by product (GHS)", pd.DataFrame({
        "Product": fp.index, "Trades": fp.Trades.map(n0).values, "Litres purchased": fp.Purchased.map(n0).values, "Bank facility": fp.Facility.map(n0).values,
        "Share of facility": fp.FacShare.map(pc).values, "Own cash": fp.Own.map(n0).values, "Net margin": fp.NM.map(n0).values,
        "Net GHS/L": fp.NMpl.map(n2).values, "Return on own cash": fp.RoOwn.map(pc).values})))
    dp = cuts["depot"]
    s4.tables.append(Tbl("By depot", pd.DataFrame({"Depot": dp.index, "Litres": dp.Vol.map(n0).values, "Sales": dp.Rev.map(n0).values,
                                                   "Net margin": dp.NM.map(n0).values, "Net GHS/L": dp.NMpl.map(n2).values})))

    # ---- customers
    cu = cuts["cust"]
    s5 = Section("customers", "Customers")
    lossy = cu[cu.NM < 0].sort_values("NM").head(3)
    s5.figs += [
        _fig("Top 10 customers by sales (red = loss-making)", f"The top 5 customers take {cu.Share.head(5).sum():.0%} of sales; {cu.index[0]} alone is {cu.Share.iloc[0]:.0%}."
             + (f" Loss-making: {', '.join(lossy.index)}." if len(lossy) else ""), C.top_customers(R)),
        _fig("Customer concentration", f"{len(cu)} customers in total; the top 10 account for {cu.Share.head(10).sum():.0%} of sales.", C.concentration(R))]
    c15 = cu.head(15)
    s5.tables.append(Tbl("Top 15 customers (GHS)", pd.DataFrame({
        "Customer": c15.index, "Loadings": c15.Loadings.map(n0).values, "Litres": c15.Vol.map(n0).values, "Sales": c15.Rev.map(n0).values,
        "Share": c15.Share.map(pc).values, "Net margin": c15.NM.map(n0).values, "Net GHS/L": c15.NMpl.map(n2).values})))

    # ---- funding
    s6 = Section("funding", "Funding and exposure", kpis=[
        ("Product purchased", f"GHS {t['inv']/1e6:,.1f}m", ""), ("Own cash", f"GHS {t['own']/1e6:,.1f}m", f"{t['own']/t['inv']:.1%} of invoices"),
        ("Bank facility", f"GHS {t['loan']/1e6:,.1f}m", f"GHS {t['impact']/1e6:,.1f}m drawn down"), ("Loan still open", f"GHS {t['rem']/1e6:,.1f}m", ""),
        ("Financing cost in report", f"GHS {t['fin']/1e6:,.2f}m", "Workbook Facility Cost" if t["fin_source"] == "workbook" else "Rebuilt from PURCHASES"),
        ("Interest per PURCHASES", f"GHS {t['fin_p']/1e6:,.2f}m", f"booked {t['rec']/1e6:,.2f}m, estimated {(t['est']+t['accr'])/1e6:,.2f}m")])
    s6.figs += [
        _fig("Product purchased by month and how it was funded", f"Own cash funded {t['own']/t['inv']:.0%} of purchases; the bank facility the rest.", C.funding_by_month(R)),
        _fig("Financing cost by trade", (f"Workbook Facility Cost totals GHS {t['fin_w']/1e6:,.2f}m against GHS {t['fin_p']/1e6:,.2f}m of interest per PURCHASES; the totals agree closely but trades differ."
                                          if t["fin_source"] == "workbook" else f"GHS {t['fin']/1e6:,.2f}m in total, of which GHS {(t['est']+t['accr'])/1e6:,.2f}m is estimated."), C.interest_by_trade(R)),
        _fig("Outstanding loan", _open_caption(R), C.open_loans(R))]
    s6.figs = [x for x in s6.figs if x]
    ft = T.copy()
    s6.tables.append(Tbl("Funding by trade (GHS)", pd.DataFrame({
        "Trade": ft.index, "Invoice": ft.Invoice.map(n0).values, "Own cash": ft.Own.map(n0).values, "Bank loan": ft.Loan.map(n0).values,
        "Drawn down": ft.Impact.map(n0).values, "Facility Cost (sheet)": ft.FinW.map(n0).values, "Interest per PURCHASES": ft.FinP.map(n0).values,
        "Outstanding": ft.Remaining.map(n0).values})))

    # ---- notes
    s7 = Section("notes", "Method and data notes", paras=checks(R))
    secs = [s0, s1, s2, s3, s4, s5, s6, s7]
    for s in secs:
        s.figs = [x for x in s.figs if x]
    return secs, period


def _open_caption(R):
    T, t = R["T"], R["tot"]; o = T[T.Status == "Open"]
    if o.empty:
        return "No facility is outstanding."
    stock = (o.Remaining / o.CPL)
    return (f"GHS {t['rem']/1e6:,.1f}m of facility is still open, backed by {stock.sum()/1e6:,.2f}m L of stock held by the bank awaiting release ("
            + ", ".join(f"{i} {v/1e6:,.2f}m L" for i, v in stock.items()) + "). These trades are provisional.")


def _prod_caption(R):
    S = R["S"]; S = S[~S.Loss]
    tot = S.groupby("Prod").NM.sum().sort_values(ascending=False)
    g = S.groupby(["Month", "Prod"]).NM.sum().unstack().reindex(R["M"].index)
    full = g[~R["M"].Partial] if (~R["M"].Partial).sum() else g
    top = tot.index[0]
    return (f"{top} is the largest earner at GHS {tot.iloc[0]/1e6:,.1f}m of GHS {tot.sum()/1e6:,.1f}m ("
            f"{tot.iloc[0]/tot.sum():.0%}); " + ", ".join(f"{p} GHS {v/1e6:,.1f}m" for p, v in tot.iloc[1:].items())
            + f". Best full month: {full.sum(axis=1).idxmax().strftime("%B")} (GHS {full.sum(axis=1).max()/1e6:,.1f}m).")


def _half(R):
    d = R["daily"]; fin = d.iloc[-1]
    hit = d[d >= fin / 2].index[0]
    return f"Net margin reached GHS {fin/2e6:,.1f}m (half the total) on {hit:%d %b}; GHS {fin/1e6:,.1f}m by {d.index[-1]:%d %b}."
