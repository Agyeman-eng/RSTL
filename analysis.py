"""RSTL analysis engine: workbook in, tables and narrative out."""
import re
import numpy as np
import pandas as pd

ALIASES = {  # merge common OMC name variants; extend as needed
    "DUKES PETROLEUM LTD.": "DUKES PETROLEUM", "DUKES PETROLEUM LTD": "DUKES PETROLEUM",
    "LA CLEM GHANA LIMITED": "LA CLEM GHANA", "JD-LINK OIL COMPANY LIMITED": "JD-LINK COMPANY",
    "KINGSPERP OIL": "KINGSPERP OIL LIMITED",
}
DEPOT_MAP = {"BOST - APD": "BOST", "BOST - KUMASI": "BOST", "BOST - BUIPE": "BOST", "BOST-BUIPE": "BOST",
             "TOR - PETHUB": "PETHUB", "VANA": "TOR"}


def _sheet(xl, name):
    for s in xl.sheet_names:
        if s.strip().lower() == name:
            return pd.read_excel(xl, s)
    raise ValueError(f"Sheet '{name.upper()}' not found. Sheets in file: {xl.sheet_names}")


def _col(df, *names):
    clean = {re.sub(r"\s+", " ", str(c)).strip().lower(): c for c in df.columns}
    for n in names:
        if n.lower() in clean:
            return clean[n.lower()]
    raise ValueError(f"Missing column (tried {names}). Found: {list(df.columns)[:20]}")


def load(file):
    xl = pd.ExcelFile(file)
    s, p = _sheet(xl, "sales"), _sheet(xl, "purchases")
    S = pd.DataFrame({
        "ID": s[_col(s, "ID")].astype(str).str.strip(),
        "Date": pd.to_datetime(s[_col(s, "Date")]),
        "OMC": s[_col(s, "OMC")].astype(str).str.strip().str.upper().replace(ALIASES),
        "Prod": s[_col(s, "Product")], "Depot": s[_col(s, "Depot")].astype(str).str.strip().str.upper(),
        "Qty": s[_col(s, "Quantity")], "SP": s[_col(s, "Selling Price")],
        "Rev": s[_col(s, "Sales Revenue")], "CP": s[_col(s, "Cost Price")],
        "Var": s[_col(s, "VARIABLE LICENSE + OTHER COSTS")].fillna(0),
        "CM": s[_col(s, "CM cost/ Ltr", "CM cost/Ltr")].fillna(0)})
    S = S.dropna(subset=["ID", "Date", "Qty"])
    S = S[S.ID.str.lower() != "nan"]
    S["Depot"] = S.Depot.replace({k.upper(): v for k, v in DEPOT_MAP.items()})
    S["Cogs"] = S.CP * S.Qty
    S["Other"] = (S.Var + S.CM) * S.Qty
    S["GM"] = S.Rev - S.Cogs - S.Other
    S["Loss"] = S.OMC.str.contains("OPERATIONAL LOSS")
    S["Month"] = S.Date.dt.to_period("M")
    P = pd.DataFrame({
        "ID": p[_col(p, "ID")].astype(str).str.strip(), "Date": pd.to_datetime(p[_col(p, "Date")], errors="coerce"),
        "Prod": p[_col(p, "Product")], "Sup": p[_col(p, "Supplier")], "Depot": p[_col(p, "Depot")],
        "Qty": p[_col(p, "Quantity")], "CPL": p[_col(p, "Cost / L")], "Pay": p[_col(p, "Payment")],
        "Inv": p[_col(p, "Invoice Amt")], "Int": p[_col(p, "Interest")],
        "Status": p[_col(p, "Status")].astype(str).str.strip().str.title()})
    return S, P


def infer_rate(P):
    """Implied annual rate from drawdowns that already carry booked interest."""
    rates = []
    for _, g in P.groupby("ID"):
        a = g[g.Status == "Actual"]
        if a.empty:
            continue
        bal = a.Inv.iloc[0] - g[g.Status == "Own"].Pay.sum()
        prev = a.Date.iloc[0]
        for _, r in g[g.Status == "Impact"].sort_values("Date", kind="stable").iterrows():
            d = (r.Date - prev).days
            if pd.notna(r.Int) and r.Int > 0 and d > 0 and bal > 0:
                rates.append(r.Int * 365 / (bal * d))
            bal -= r.Pay; prev = r.Date
    return float(np.median(rates)) if rates else 0.1303


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
            bal -= r.Pay; prev = r.Date
        rem = max(bal, 0)
        acc = rem * rate * max((asof - prev).days, 0) / 365 if rem > 1 else 0.0
        rows.append(dict(ID=tid, Start=a.Date, Prod=a.Prod, Sup=a.Sup, PDepot=a.Depot, PQ=a.Qty, CPL=a.CPL,
                         Invoice=a.Inv, Own=own, Loan=a.Inv - own, Impact=imp.Pay.sum(),
                         Rec=rec, Est=est, Accr=acc, Remaining=rem))
    return pd.DataFrame(rows).set_index("ID")


def funder(tid):
    m = re.match(r"([A-Za-z]+)", tid)
    return "FAB" if re.fullmatch(r"A\d+.*", tid) else (m.group(1).upper() if m else "Other")


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
    T["DaysToSell"] = S.groupby("ID").apply(lambda d: np.average(d.Days, weights=d.Qty), include_groups=False)
    # monthly
    M = S.groupby("Month").agg(Vol=("Qty", "sum"), Rev=("Rev", "sum"), Cogs=("Cogs", "sum"), Other=("Other", "sum"),
                               GM=("GM", "sum"), Fin=("Fin", "sum"), NM=("NM", "sum"))
    M["NMpl"], M["NMpct"] = M.NM / M.Vol, M.NM / M.Rev
    pur = P[P.Status == "Actual"].assign(Month=lambda d: d.Date.dt.to_period("M")).groupby("Month").agg(PVol=("Qty", "sum"), Invoiced=("Inv", "sum"))
    M = M.join(pur).fillna({"PVol": 0, "Invoiced": 0})
    first, last = S.Date.min(), S.Date.max()
    M["Partial"] = False
    if first.day > 7: M.loc[first.to_period("M"), "Partial"] = True
    if last.day < last.days_in_month - 7: M.loc[last.to_period("M"), "Partial"] = True
    # cuts
    def cut(col, df=None):
        d = (df if df is not None else S)[~S.Loss]
        g = d.groupby(col).agg(Vol=("Qty", "sum"), Rev=("Rev", "sum"), NM=("NM", "sum"), Loadings=("Qty", "size"))
        g["NMpl"], g["NMpct"], g["Share"] = g.NM / g.Vol, g.NM / g.Rev, g.Rev / g.Rev.sum()
        return g.sort_values("Rev", ascending=False)
    S["Funder"] = S.ID.map(T.Funder)
    cuts = dict(prod=cut("Prod"), funder=cut("Funder"), depot=cut("Depot"), cust=cut("OMC"))
    daily = S.groupby("Date").NM.sum().cumsum()
    tot = dict(vol=S.Qty.sum(), rev=S.Rev.sum(), cogs=S.Cogs.sum(), oth=S.Other.sum(), gm=S.GM.sum(), fin=T.Fin.sum(),
               rec=T.Rec.sum(), est=T.Est.sum(), accr=T.Accr.sum(), nm=T.NM.sum(), pq=T.PQ.sum(), inv=T.Invoice.sum(),
               own=T.Own.sum(), loan=T.Loan.sum(), impact=T.Impact.sum(), rem=T.Remaining.sum(),
               days=np.average(S.Days, weights=S.Qty), loadings=len(S), first=first, last=last, rate=rate)
    return dict(S=S, T=T, M=M, cuts=cuts, daily=daily, tot=tot)


def trend(M, col="Vol"):
    use = M[~M.Partial]
    if len(use) < 3:
        use = M
    x = np.array([list(M.index).index(i) for i in use.index], float)
    k, b = np.polyfit(x, use[col].values, 1)
    return use.index, k * x + b, k


def narrative(R):
    T, M, t, c = R["T"], R["M"], R["tot"], R["cuts"]
    f = lambda v: f"{v/1e6:,.1f}"
    out = []
    out.append(f"Between {t['first']:%d %b %Y} and {t['last']:%d %b %Y} the RSTL book sold **{f(t['vol'])} million litres** across "
               f"**{len(T)} trades** and {t['loadings']:,} loadings, generating **GHS {f(t['rev'])} million** in sales. "
               f"After cost of product, licence costs and RSTL financing, **net margin was GHS {f(t['nm'])} million** "
               f"({t['nm']/t['rev']:.1%} of sales, GHS {t['nm']/t['vol']:.2f} per litre). Financing consumed {t['fin']/t['gm']:.1%} of the pre-financing margin.")
    _, _, k = trend(M)
    full = M[~M.Partial]
    peak = M.Vol.idxmax()
    out.append(f"**Volume.** The strongest month was {peak.strftime('%B')} at {f(M.Vol.max())} million litres "
               f"({M.Vol.max()/t['vol']:.0%} of the total). The linear trend across full months is "
               f"{'+' if k>=0 else '−'}{abs(k)/1e6:.1f} million litres per month.")
    neg = M[(M.NM < 0) & ~M.Partial]
    best = full.NM.idxmax()
    out.append(f"**Monthly profit.** {best.strftime('%B')} was the most profitable full month (GHS {f(full.NM.max())} million). "
               + (f"Loss-making full months: {', '.join(m.strftime('%B') for m in neg.index)}." if len(neg) else "No full month made a loss."))
    top = T.sort_values("NM", ascending=False)
    tn = top.head(3)
    out.append(f"**Trades.** {int((T.NM>0).sum())} of {len(T)} trades were profitable. The top three ({', '.join(tn.index)}) produced "
               f"GHS {f(tn.NM.sum())} million, {tn.NM.sum()/t['nm']:.0%} of net margin. "
               + (f"Loss-making trades: {', '.join(T[T.NM<0].index)} (GHS {f(-T[T.NM<0].NM.sum())} million combined)." if (T.NM < 0).any() else ""))
    if len(T) >= 12:
        recent = T.iloc[-6:]; before = T.iloc[:-6]
        rl, bl = recent.NM.sum() / recent.Sold.sum(), before.NM.sum() / before.Sold.sum()
        if rl < 0.5 * bl:
            out.append(f"**Margin compression.** The six most recent trades by purchase date ({recent.index[0]} to {recent.index[-1]}) earned GHS {rl:+.2f} per litre "
                       f"against GHS {bl:+.2f} on earlier trades. Volume is growing faster than the spread.")
    p = c["prod"]
    out.append("**Product mix.** " + "; ".join(f"{i}: GHS {r.NMpl:.2f}/L on {r.Vol/1e6:.1f}m L" for i, r in p.iterrows()) + ".")
    fu = c["funder"]
    if len(fu) > 1:
        out.append("**By funder.** " + "; ".join(f"{i}: GHS {r.NMpl:.2f}/L on {r.Share:.0%} of sales" for i, r in fu.iterrows()) + ".")
    cu = c["cust"]
    lossy = cu[cu.NM < 0].sort_values("NM").head(3)
    out.append(f"**Customers.** {len(cu)} OMCs bought from the book; the top five account for {cu.Share.head(5).sum():.0%} of sales "
               f"(largest: {cu.index[0]}, {cu.Share.iloc[0]:.0%}). "
               + (f"Net losers: {', '.join(lossy.index)}." if len(lossy) else ""))
    if t["rem"] > 1:
        op = T[T.Status == "Open"]
        out.append(f"**Exposure.** GHS {f(t['rem'])} million of RSTL loan remains open on {', '.join(op.index)}; their results are provisional.")
    return out


def checks(R):
    """Data-quality flags."""
    T, S = R["T"], R["S"]
    notes = []
    over = T[(T.Sold - T.PQ) > 0.05 * T.PQ]
    under = T[(T.PQ - T.Sold) > 0.05 * T.PQ]
    if len(over): notes.append("Sold litres exceed purchased litres by more than 5% on: " + ", ".join(f"{i} (+{r.Sold-r.PQ:,.0f} L)" for i, r in over.iterrows()) + ". Loadings may be booked to a neighbouring trade code.")
    if len(under): notes.append("Purchased litres not yet sold by more than 5% on: " + ", ".join(f"{i} ({r.PQ-r.Sold:,.0f} L)" for i, r in under.iterrows()) + ".")
    if S.Loss.any(): notes.append(f"{int(S.Loss.sum())} OPERATIONAL LOSS rows (GHS {-S[S.Loss].GM.sum():,.0f}) are included in margin and excluded from customer analysis.")
    noP = set(S.ID) - set(R["T"].dropna(subset=["PQ"]).index)
    if noP: notes.append("Sales exist with no matching purchase in PURCHASES for: " + ", ".join(sorted(noP)) + ". Financing cost is zero for these.")
    notes.append(f"Interest is taken as booked in PURCHASES where present; missing drawdown interest is estimated at {R['tot']['rate']:.2%} p.a. on the outstanding loan "
                 f"(GHS {R['tot']['est']+R['tot']['accr']:,.0f} estimated of GHS {R['tot']['fin']:,.0f}). The workbook's own Facility Cost / Total Margin columns are not used.")
    return notes
