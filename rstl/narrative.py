"""Plain-language findings and data-quality notes, written from the numbers."""
from .analysis import trend

f1 = lambda v: f"{v/1e6:,.1f}"


def narrative(R):
    T, M, t, c = R["T"], R["M"], R["tot"], R["cuts"]
    out = []
    out.append(f"Between {t['first']:%d %b %Y} and {t['last']:%d %b %Y} the RSTL book sold **{f1(t['vol'])} million litres** across "
               f"**{len(T)} trades** and {t['loadings']:,} loadings, generating **GHS {f1(t['rev'])} million** in sales. "
               f"After cost of product, licence costs and RSTL financing, **net margin was GHS {f1(t['nm'])} million** "
               f"({t['nm']/t['rev']:.1%} of sales, GHS {t['nm']/t['vol']:.2f} per litre). Financing consumed {t['fin']/t['gm']:.1%} of the pre-financing margin.")
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
    over = T[(T.Sold - T.PQ) > 0.05 * T.PQ]
    under = T[(T.PQ - T.Sold) > 0.05 * T.PQ]
    if len(over):
        notes.append("Sold litres exceed purchased litres by more than 5% on: " + ", ".join(f"{i} (+{r.Sold-r.PQ:,.0f} L)" for i, r in over.iterrows()) + ". Loadings may be booked to a neighbouring trade code.")
    if len(under):
        notes.append("Purchased litres not yet sold by more than 5% on: " + ", ".join(f"{i} ({r.PQ-r.Sold:,.0f} L)" for i, r in under.iterrows()) + ".")
    if S.Loss.any():
        notes.append(f"{int(S.Loss.sum())} OPERATIONAL LOSS rows (GHS {-S[S.Loss].GM.sum():,.0f}) are included in margin and excluded from customer analysis.")
    noP = set(S.ID) - set(T.dropna(subset=["PQ"]).index)
    if noP:
        notes.append("Sales exist with no matching purchase in PURCHASES for: " + ", ".join(sorted(noP)) + ". Financing cost is zero for these.")
    notes.append(f"Interest is taken as booked in PURCHASES where present; missing drawdown interest is estimated at {t['rate']:.2%} p.a. on the outstanding loan "
                 f"(GHS {t['est']+t['accr']:,.0f} estimated of GHS {t['fin']:,.0f}). The workbook's own Facility Cost and Total Margin columns are not used.")
    notes.append("Net margin = sales − cost of product − licence and other costs − financing cost. The first appearance of a trade code in PURCHASES is the actual purchase; Own and Impact rows are equity and bank drawdowns.")
    return notes
