"""Core calculations: financing cost, trade / month / segment tables, trend."""
import re
import numpy as np
import pandas as pd
from .loader import facility_ok, funder, infer_rates


def financing(P, rates, asof):
    rows = []
    for tid, g in P.groupby("ID"):
        rate = rates[funder(tid)] if isinstance(rates, dict) else rates
        a = g[g.Status == "Actual"]
        if a.empty:
            continue
        a = a.iloc[0]
        own = g[g.Status == "Own"].Pay.sum()
        imp = g[g.Status == "Impact"].sort_values("Date", kind="stable")
        bal, prev, rec, est = a.Inv - own, a.Date, 0.0, 0.0
        for _, r in imp.iterrows():
            days = max((r.Date - prev).days, 0)
            if pd.notna(r.Int) and r.Int > 0:
                rec += r.Int
            else:
                est += bal * rate * days / 365
            bal -= r.Pay
            prev = r.Date
        rem = max(bal, 0)
        acc = rem * rate * max((asof - prev).days, 0) / 365 if rem > 1 else 0.0
        rows.append(dict(ID=tid, Start=a.Date, Prod=a.Prod, Sup=a.Sup, PDepot=a.Depot, PQ=a.Qty, CPL=a.CPL,
                         Invoice=a.Inv, Own=own, Loan=a.Inv - own, Impact=imp.Pay.sum(),
                         Rec=rec, Est=est, Accr=acc, Remaining=rem))
    return pd.DataFrame(rows).set_index("ID")


def analyse(S, P, rate=None, asof=None, fin_source="auto", rstl_qty=None, basis="rstl"):
    """rate: None (detect per funder), a single number, or a dict {funder: rate}.
    fin_source: "workbook" (Facility Cost column x litres, so net margin = the sheet's Total Margin),
                "purchases" (interest rebuilt from PURCHASES) or "auto" (workbook when its columns are clean)."""
    asof = asof or S.Date.max()
    # --- RSTL-only scope. SALES holds every loading tagged to a trade, including litres bought outside RSTL.
    # Sheet4's 'Total OMC loadings' gives the RSTL litres per trade. SALES rows are not tagged RSTL / non-RSTL,
    # so each trade's rows are scaled pro-rata (price and cost per litre are unchanged).
    S = S.copy()
    sold_all = S.groupby("ID").Qty.sum()
    S["QtyAll"], S["GMAll"] = S.Qty, S.GM
    f = pd.Series(1.0, index=sold_all.index)
    sheet_diff = pd.Series(dtype=float)
    if basis == "rstl" and rstl_qty is not None:
        r = rstl_qty.reindex(sold_all.index)
        sheet_diff = (sold_all - r).dropna()
        f = (r / sold_all).clip(lower=0, upper=1).fillna(1.0)
    S["f"] = S.ID.map(f)
    S["Qty"], S["Rev"] = S.Qty * S.f, S.Rev * S.f
    S["TM"] = S.TM * S.f
    S["Cogs"], S["Other"] = S.CP * S.Qty, (S.Var + S.CM) * S.Qty
    S["GM"] = S.Rev - S.Cogs - S.Other
    found = infer_rates(P)
    if rate is None:
        rates = found
    elif isinstance(rate, dict):
        rates = {**found, **rate}
    else:
        rates = {f: rate for f in found}
    F = financing(P, rates, asof)
    T = S.groupby("ID").agg(Sold=("Qty", "sum"), Rev=("Rev", "sum"), Cogs=("Cogs", "sum"), Other=("Other", "sum"),
                            GM=("GM", "sum"), Loadings=("Qty", "size")).join(F, how="left")
    fac_ok = facility_ok(S)
    src = ("workbook" if fac_ok else "purchases") if fin_source == "auto" else fin_source
    if src == "workbook" and not fac_ok:
        src = "purchases"
    S["FinW"] = S.Fac.fillna(0) * S.Qty
    T["FinP"] = T.Rec.fillna(0) + T.Est.fillna(0) + T.Accr.fillna(0)
    T["FinW"] = S.groupby("ID").FinW.sum()
    T["Fin"] = T.FinW if src == "workbook" else T.FinP
    T["NM"] = T.GM - T.Fin
    T["GMpl"], T["NMpl"], T["NMpct"] = T.GM / T.Sold, T.NM / T.Sold, T.NM / T.Rev
    T["Liq"] = T.Sold / T.PQ
    T["SoldAll"] = S.groupby("ID").QtyAll.sum()
    T["Outside"] = T.SoldAll - T.Sold
    T["Funder"] = [funder(i) for i in T.index]
    T["Status"] = np.where(T.Remaining.fillna(0) > 1, "Open", "Closed")
    T = T.sort_values("Start", kind="stable")
    S["Fin"] = S.FinW if src == "workbook" else S.ID.map(T.Fin) * S.Qty / S.ID.map(T.Sold)
    S["NM"] = S.GM - S.Fin
    S["TCL"] = (S.Cogs + S.Other + S.Fin) / S.Qty  # total cost per litre: product + licence/other + financing
    S["Days"] = (S.Date - S.ID.map(T.Start)).dt.days
    S["Funder"] = S.ID.map(T.Funder)
    T["DaysToSell"] = S.groupby("ID").apply(lambda d: np.average(d.Days, weights=d.Qty) if d.Qty.sum() > 0 else d.Days.mean(), include_groups=False)

    M = S.groupby("Month").agg(Vol=("Qty", "sum"), Rev=("Rev", "sum"), Cogs=("Cogs", "sum"), Other=("Other", "sum"),
                               GM=("GM", "sum"), Fin=("Fin", "sum"), NM=("NM", "sum"))
    M["NMpl"], M["NMpct"] = M.NM / M.Vol, M.NM / M.Rev
    pur = (P[P.Status == "Actual"].assign(Month=lambda d: d.Date.dt.to_period("M"))
           .groupby("Month").agg(PVol=("Qty", "sum"), Invoiced=("Inv", "sum")))
    M = M.join(pur).fillna({"PVol": 0, "Invoiced": 0})
    first, last = S.Date.min(), S.Date.max()
    M["Partial"] = False
    if first.day > 7:
        M.loc[first.to_period("M"), "Partial"] = True
    if last.day < last.days_in_month - 7:
        M.loc[last.to_period("M"), "Partial"] = True

    def cut(col):
        d = S[~S.Loss]
        g = d.groupby(col).agg(Vol=("Qty", "sum"), Rev=("Rev", "sum"), NM=("NM", "sum"), Loadings=("Qty", "size"))
        g["NMpl"], g["NMpct"], g["Share"] = g.NM / g.Vol, g.NM / g.Rev, g.Rev / g.Rev.sum()
        return g.sort_values("Rev", ascending=False)

    cuts = dict(prod=cut("Prod"), funder=cut("Funder"), depot=cut("Depot"), cust=cut("OMC"))
    # facility (bank loan) usage by product
    fp = T.groupby("Prod").agg(Trades=("Sold", "size"), Purchased=("PQ", "sum"), Invoice=("Invoice", "sum"),
                               Facility=("Loan", "sum"), Own=("Own", "sum"), NM=("NM", "sum"), Sold=("Sold", "sum"),
                               Fin=("Fin", "sum")).sort_values("Facility", ascending=False)
    fp["FacShare"] = fp.Facility / fp.Facility.sum()
    fp["NMpl"] = fp.NM / fp.Sold
    fp["RoOwn"] = fp.NM / fp.Own
    cuts["facility_prod"] = fp
    daily = S.groupby("Date").NM.sum().cumsum()
    tot = dict(vol=S.Qty.sum(), rev=S.Rev.sum(), cogs=S.Cogs.sum(), oth=S.Other.sum(), gm=S.GM.sum(), fin=T.Fin.sum(),
               rec=T.Rec.sum(), est=T.Est.sum(), accr=T.Accr.sum(), nm=T.NM.sum(), pq=T.PQ.sum(), inv=T.Invoice.sum(),
               own=T.Own.sum(), loan=T.Loan.sum(), impact=T.Impact.sum(), rem=T.Remaining.sum(),
               days=np.average(S.Days, weights=S.Qty), loadings=len(S), first=first, last=last, rates=rates,
               basis=basis if (basis == 'rstl' and rstl_qty is not None) else 'all', outside=T.Outside.sum(),
               outside_gm=S.GMAll.sum() - S.GM.sum(), sheet_diff=sheet_diff, fin_source=src, fac_ok=fac_ok, fin_w=S.FinW.sum(), fin_p=T.FinP.sum(),
               sheet_tm=(S.TM.sum() if S.TM.notna().any() else float('nan')))
    return dict(S=S, P=P, T=T, M=M, cuts=cuts, daily=daily, tot=tot)


def trend(M, col="Vol"):
    """Linear trend over full (non-partial) months. Returns (index, fitted values, slope per month)."""
    use = M[~M.Partial]
    if len(use) < 3:
        use = M
    pos = list(M.index)
    x = np.array([pos.index(i) for i in use.index], float)
    k, b = np.polyfit(x, use[col].values, 1)
    return use.index, k * x + b, k
