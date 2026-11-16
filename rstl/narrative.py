"""Plain-language findings and data-quality notes, written from the numbers."""
import pandas as pd
from .analysis import trend


def rate_text(rates):
    """'13.03%' if every funder shares a rate, else 'FAB 13.03%, OMNI 13.59%'."""
    vals = {round(v, 4) for v in rates.values()}
    if len(vals) == 1:
        return f"{next(iter(rates.values())):.2%}"
    return ", ".join(f"{k} {v:.2%}" for k, v in rates.items())


def reconcile(R, min_l=50_000, pct=0.05):
    """Litres sold vs litres purchased, grouped by product and cost price (so loadings booked to
    a neighbouring trade code still net out). Returns a DataFrame of groups that do not tally."""
    S = R["S"]; P = R["P"]
    a = P[P.Status == "Actual"].groupby(["Prod", "CPL"]).agg(Purchased=("Qty", "sum"), Trades=("ID", lambda x: ", ".join(x)))
    a.index.names = ["Prod", "CP"]
    s = S.groupby(["Prod", "CP"]).agg(Sold=("Qty", "sum"), SoldTrades=("ID", lambda x: ", ".join(sorted(set(x)))), GM=("GM", "sum"))
    j = a.join(s, how="outer").fillna({"Purchased": 0, "Sold": 0, "Trades": "", "SoldTrades": "", "GM": 0})
    j["Diff"] = j.Sold - j.Purchased
    j["GMpl"] = j.GM / j.Sold.where(j.Sold > 0)
    bad = j[(j.Diff.abs() > min_l) & (j.Diff.abs() > pct * j[["Purchased", "Sold"]].max(axis=1))]
    return j, bad

f1 = lambda v: f"{v/1e6:,.1f}"


def narrative(R):
    T, M, t, c = R["T"], R["M"], R["tot"], R["cuts"]
    out = []
    out.append(f"Between {t['first']:%d %b %Y} and {t['last']:%d %b %Y} the RSTL book sold **{f1(t['vol'])} million litres** across "
               f"**{len(T)} trades** and {t['loadings']:,} loadings, generating **GHS {f1(t['rev'])} million** in sales. "
               f"After cost of product, licence costs and RSTL financing, **net margin was GHS {f1(t['nm'])} million** "
               f"({t['nm']/t['rev']:.1%} of sales, GHS {t['nm']/t['vol']:.2f} per litre). Financing consumed {t['fin']/t['gm']:.1%} of the pre-financing margin.")
    if t["basis"] == "rstl" and abs(t["outside"]) > 0:
        out.insert(1, f"**Scope.** Figures cover RSTL litres only. {t['outside']/1e6:,.2f} million litres of the loadings recorded in SALES were bought outside RSTL "
                      f"(deducted in Sheet4's Total OMC loadings) and are excluded, together with GHS {t['outside_gm']/1e6:,.2f} million of margin before financing that they earned. "
                      f"Where a trade has outside litres, its sales rows are scaled down pro-rata.")
    _, _, k = trend(M)
    full = M[~M.Partial]
    peak = M.Vol.idxmax()
    out.append(f"**Volume.** The strongest month was {peak.strftime('%B')} at {f1(M.Vol.max())} million litres "
               f"({M.Vol.max()/t['vol']:.0%} of the total). The linear trend across full months is "
               f"{'+' if k >= 0 else '−'}{abs(k)/1e6:.1f} million litres per month.")
    neg = M[(M.NM < 0) & ~M.Partial]
    best = full.NM.idxmax()
    out.append(f"**Monthly profit.** {best.strftime('%B')} was the most profitable full month (GHS {f1(full.NM.max())} million). "
               + (f"Loss-making full months: {', '.join(m.strftime('%B') for m in neg.index)}." if len(neg) else "No full month made a loss."))
    top = T.sort_values("NM", ascending=False)
    tn = top.head(3)
    out.append(f"**Trades.** {int((T.NM > 0).sum())} of {len(T)} trades were profitable. The top three ({', '.join(tn.index)}) produced "
               f"GHS {f1(tn.NM.sum())} million, {tn.NM.sum()/t['nm']:.0%} of net margin. "
               + (f"Loss-making trades: {', '.join(T[T.NM < 0].index)} (GHS {f1(-T[T.NM < 0].NM.sum())} million combined)." if (T.NM < 0).any() else ""))
    if len(T) >= 12:
        recent, before = T.iloc[-6:], T.iloc[:-6]
        rl, bl = recent.NM.sum() / recent.Sold.sum(), before.NM.sum() / before.Sold.sum()
        if rl < 0.5 * bl:
            out.append(f"**Margin compression.** The six most recent trades by purchase date ({recent.index[0]} to {recent.index[-1]}) earned GHS {rl:+.2f} per litre "
                       f"against GHS {bl:+.2f} on earlier trades. Volume is growing faster than the spread.")
    p = c["prod"]
    out.append("**Product mix.** " + "; ".join(f"{i}: GHS {r.NMpl:.2f}/L on {r.Vol/1e6:.1f}m L" for i, r in p.iterrows()) + ".")
    fp = c["facility_prod"]
    lead = fp.index[0]
    out.append(f"**Facility use.** {lead} drew the most bank facility: GHS {f1(fp.Facility.iloc[0])} million, {fp.FacShare.iloc[0]:.0%} of the "
               f"GHS {f1(fp.Facility.sum())} million drawn across {len(T)} trades.")
    fu = c["funder"]
    if len(fu) > 1:
        cnt = T.Funder.value_counts()
        out.append("**By funder.** " + "; ".join(f"{i}: {cnt.get(i, 0)} trades, GHS {r.NMpl:.2f}/L, {r.Share:.0%} of sales" for i, r in fu.iterrows()) + ".")
    cu = c["cust"]
    lossy = cu[cu.NM < 0].sort_values("NM").head(3)
    out.append(f"**Customers.** {len(cu)} OMCs bought from the book; the top five account for {cu.Share.head(5).sum():.0%} of sales "
               f"(largest: {cu.index[0]}, {cu.Share.iloc[0]:.0%}). "
               + (f"Net losers: {', '.join(lossy.index)}." if len(lossy) else ""))
    if t["rem"] > 1:
        op = T[T.Status == "Open"]
        out.append(f"**Exposure.** GHS {f1(t['rem'])} million of RSTL loan remains open on {', '.join(op.index)}; their results are provisional.")
    return out


def checks(R):
    T, S, t = R["T"], R["S"], R["tot"]
    notes = []
    if t["basis"] == "rstl" and abs(t["outside"]) > 0:
        o = T[T.Outside.abs() > 0.5].sort_values("Outside", ascending=False)
        notes.append(f"RSTL scope: {t['outside']/1e6:,.2f}m L of loadings in SALES were bought outside RSTL and are excluded (trades: "
                     + ", ".join(f"{i} {r.Outside:,.0f} L" for i, r in o.iterrows()) + "). The SALES sheet does not tag which rows are RSTL, so each trade's rows are scaled pro-rata; "
                     "totals per trade are exact, but the split by month, depot and customer within those trades is an approximation.")
        sd = t["sheet_diff"]
        extra = sd[sd < -0.5]
        if len(extra):
            notes.append("Sheet4 shows more RSTL litres than SALES holds on " + ", ".join(f"{i} (+{-v:,.0f} L)" for i, v in extra.items())
                         + ". These litres have no sales rows (possibly booked under another trade code), so they are not added.")
    j, bad = reconcile(R)
    tot_diff = j.Sold.sum() - j.Purchased.sum()
    notes.append(f"Litres check ({'RSTL litres' if t['basis'] == 'rstl' else 'all loadings'}): {j.Sold.sum()/1e6:,.2f}m L sold against {j.Purchased.sum()/1e6:,.2f}m L purchased "
                 f"({'+' if tot_diff >= 0 else '−'}{abs(tot_diff)/1e6:,.2f}m L).")
    over, under = bad[bad.Diff > 0], bad[bad.Diff < 0]
    if len(over):
        notes.append("Sold litres exceed purchased litres, by product and cost price, on: " + "; ".join(
            f"{p} at {c:g} (+{r.Diff:,.0f} L, bought under {r.Trades or 'no recorded purchase'})" for (p, c), r in over.iterrows())
            + ". These litres have a sale and a cost price but no matching RSTL purchase, so their financing cost and own cash are not in the report. "
              "Check whether a purchase is missing from PURCHASES or a quantity needs correcting.")
    if len(under):
        notes.append("Purchased litres not yet sold, by product and cost price, on: " + "; ".join(
            f"{p} at {c:g} ({-r.Diff:,.0f} L, {r.Trades})" for (p, c), r in under.iterrows()) + ".")
    if S.Loss.any():
        notes.append(f"{int(S.Loss.sum())} OPERATIONAL LOSS rows (GHS {-S[S.Loss].GM.sum():,.0f}) are included in margin and excluded from customer analysis.")
    noP = set(S.ID) - set(T.dropna(subset=["PQ"]).index)
    if noP:
        notes.append("Sales exist with no matching purchase in PURCHASES for: " + ", ".join(sorted(noP)) + ". Financing cost is zero for these.")
    if t["fin_source"] == "workbook":
        d = (T.FinW - T.FinP).abs().sort_values(ascending=False)
        top = ", ".join(f"{i} (sheet {T.FinW[i]/1e3:,.0f}k vs PURCHASES {T.FinP[i]/1e3:,.0f}k)" for i in d.index[:3])
        tie = ""
        if t["sheet_tm"] == t["sheet_tm"]:
            gap = t["sheet_tm"] - t["nm"]
            tie = (" Net margin equals the sheet's Total Margin column" + (" (scaled to RSTL litres)." if t["basis"] == "rstl" else ".") if abs(gap) < 1 else f" The sheet's Total Margin column differs from this net margin by GHS {gap:,.0f}.")
        notes.append(f"Financing cost is the sheet's Facility Cost per litre x litres (GHS {t['fin_w']:,.0f}), so total cost per litre is the sheet's Total Cost/Ltr.{tie} "
                     f"Interest per PURCHASES (booked plus estimated at {rate_text(t['rates'])} p.a.) is GHS {t['fin_p']:,.0f}, a difference of GHS {t['fin_w']-t['fin_p']:,.0f} in total. "
                     f"Trades that differ most: {top}.")
    else:
        notes.append(f"Interest is taken as booked in PURCHASES where present; missing drawdown interest is estimated at {rate_text(t['rates'])} p.a. (per funder, detected from booked drawdowns) on the outstanding loan "
                     f"(GHS {t['est']+t['accr']:,.0f} estimated of GHS {t['fin']:,.0f}). The workbook's Facility Cost and Total Margin columns are not used in this mode.")
    notes.append("Net margin = sales − total cost, where total cost = cost price + licence and other costs + financing (per litre, x litres). The first appearance of a trade code in PURCHASES is the actual purchase; Own and Impact rows are equity and bank drawdowns.")
    return notes
