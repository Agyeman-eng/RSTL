"""Core calculations: financing cost, trade / month / segment tables, trend."""
import re
import numpy as np
import pandas as pd
from .loader import infer_rate


def financing(P, rate, asof):
    rows = []
    for tid, g in P.groupby("ID"):
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


def funder(tid):
    if re.fullmatch(r"A\d+.*", tid):
        return "FAB"
    m = re.match(r"([A-Za-z]+)", tid)
    return m.group(1).upper() if m else "Other"


def analyse(S, P, rate=None, asof=None):
    asof = asof or S.Date.max()
    rate = rate if rate is not None else infer_rate(P)
    F = financing(P, rate, asof)
    T = S.groupby("ID").agg(Sold=("Qty", "sum"), Rev=("Rev", "sum"), Cogs=("Cogs", "sum"), Other=("Other", "sum"),
                            GM=("GM", "sum"), Loadings=("Qty", "size")).join(F, how="left")
    T["Fin"] = T.Rec.fillna(0) + T.Est.fillna(0) + T.Accr.fillna(0)
    T["NM"] = T.GM - T.Fin
    T["GMpl"], T["NMpl"], T["NMpct"] = T.GM / T.Sold, T.NM / T.Sold, T.NM / T.Rev
    T["Liq"] = T.Sold / T.PQ
    T["Funder"] = [funder(i) for i in T.index]
    T["Status"] = np.where(T.Remaining.fillna(0) > 1, "Open", "Closed")
    T = T.sort_values("Start", kind="stable")
    S = S.copy()
    S["Fin"] = S.ID.map(T.Fin) * S.Qty / S.ID.map(T.Sold)
    S["NM"] = S.GM - S.Fin
    S["Days"] = (S.Date - S.ID.map(T.Start)).dt.days
    S["Funder"] = S.ID.map(T.Funder)
    T["DaysToSell"] = S.groupby("ID").apply(lambda d: np.average(d.Days, weights=d.Qty), include_groups=False)

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
               days=np.average(S.Days, weights=S.Qty), loadings=len(S), first=first, last=last, rate=rate)
    return dict(S=S, T=T, M=M, cuts=cuts, daily=daily, tot=tot)


def trend(M, col="Vol"):
    """Linear trend over full (non-partial) months. Returns (index, fitted values, slope per month)."""
    use = M[~M.Partial]
    if len(use) < 3:
        use = M
    pos = list(M.index)
    x = np.array([pos.index(i) for i in use.index], float)
    k, b = np.polyfit(x, use[col].values, 1)
    return use.index, k * x + b, k
