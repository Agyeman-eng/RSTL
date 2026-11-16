"""All charts. Each function takes the analysis result R and returns a matplotlib Figure (or None if not applicable)."""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from . import theme as th
from .analysis import trend


def _labs(R):
    M = R["M"]
    multi = len({i.year for i in M.index}) > 1
    fmt = "%b %y" if multi else "%b"
    return [i.strftime(fmt) + ("*" if M.Partial[i] else "") for i in M.index]


def _title(ax, *a, **k):
    """Chart titles are supplied by the report heading; kept as a hook."""
    return None


def _pcolors(R):
    """One fixed colour per product (largest by litres first), used by every product chart."""
    order = R["S"][~R["S"].Loss].groupby("Prod").Qty.sum().sort_values(ascending=False).index
    return {p: th.CAT[i % len(th.CAT)] for i, p in enumerate(order)}


def _note_partial(ax, R):
    if R["M"].Partial.any():
        ax.annotate("* partial month", xy=(1, -0.13), xycoords="axes fraction", ha="right", fontsize=8.5, color=th.GREY)


def _donut(ax, labels, values, title, fmt, center=None, colors=None):
    vals = np.array(values, float)
    ax.set_title(title, fontsize=12, loc="center", pad=6)
    ax.grid(False)
    if (vals <= 0).any():
        ax.axis("off"); ax.text(.5, .5, "n/a (negative values)", ha="center", color=th.GREY); return
    cols = colors or th.CAT[:len(vals)]
    wedges, _ = ax.pie(vals, colors=cols, startangle=90, counterclock=False,
                       wedgeprops=dict(width=.38, edgecolor="white", linewidth=2))
    tot = vals.sum()
    ax.text(0, 0, center if center is not None else fmt(tot), ha="center", va="center", fontsize=14, fontweight="bold")
    ax.legend(wedges, [f"{l}  {fmt(v)}  ({v/tot:.0%})" for l, v in zip(labels, vals)], loc="upper center",
              bbox_to_anchor=(.5, 0.02), fontsize=9.5, ncol=1)


# ---------- volume ----------
def volume_trend(R, basis="Sold"):
    M = R["M"]; col = "Vol" if basis == "Sold" else "PVol"
    f, ax = th.fig(); x = np.arange(len(M))
    bars = ax.bar(x, M[col] / 1e6, color=[th.BLUE_L if p else th.BLUE for p in M.Partial], width=.62)
    for b, v in zip(bars, M[col] / 1e6):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.2f}", ha="center", va="bottom", fontsize=10, fontweight="bold")
    idx, fit, k = trend(M, col)
    ax.plot([list(M.index).index(i) for i in idx], fit / 1e6, color=th.ORANGE, ls="--", lw=2.6,
            label=f"Linear trend, full months ({k/1e6:+.1f}m L per month)")
    ax.set_xticks(x); ax.set_xticklabels(_labs(R)); ax.set_ylabel("Million litres")
    ax.set_ylim(0, M[col].max() / 1e6 * 1.16)
    _title(ax, f"Litres {basis.lower()} per month"); ax.legend(loc="upper left")
    _note_partial(ax, R); return f


def purchased_vs_sold(R):
    M = R["M"]; f, ax = th.fig(); x = np.arange(len(M)); w = .38
    ax.bar(x - w / 2, M.PVol / 1e6, w, color=th.NAVY, label="Purchased (RSTL actual purchases)")
    ax.bar(x + w / 2, M.Vol / 1e6, w, color=th.BLUE, label="Sold (OMC loadings)")
    ax.set_xticks(x); ax.set_xticklabels(_labs(R)); ax.set_ylabel("Million litres")
    _title(ax, "Litres purchased vs sold"); ax.legend(loc="upper left"); _note_partial(ax, R); return f


# ---------- sales & margin ----------
def sales_by_month(R):
    M = R["M"]; f, ax = th.fig(); x = np.arange(len(M))
    bars = ax.bar(x, M.Rev / 1e6, color=[th.BLUE_L if p else th.BLUE for p in M.Partial], width=.62)
    for b, v in zip(bars, M.Rev / 1e6):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:,.1f}", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(_labs(R)); ax.set_ylabel("GHS million")
    ax.set_ylim(0, M.Rev.max() / 1e6 * 1.14); _title(ax, "Sales revenue per month"); _note_partial(ax, R); return f


def net_margin_by_month(R):
    M = R["M"]; f, ax = th.fig(); x = np.arange(len(M))
    cols = [(th.GOOD if v >= 0 else th.BAD) for v in M.NM]
    bars = ax.bar(x, M.NM / 1e6, color=cols, width=.62, alpha=1)
    for b, v, p in zip(bars, M.NM / 1e6, M.NMpct):
        ax.text(b.get_x() + b.get_width() / 2, v + (0.04 * abs(M.NM).max() / 1e6 if v >= 0 else -0.04 * abs(M.NM).max() / 1e6),
                f"{th.m(v*1e6,2)}\n{p:.1%}", ha="center", va="bottom" if v >= 0 else "top", fontsize=9.5, fontweight="bold")
    ax.axhline(0, color=th.INK2, lw=1)
    ax.set_xticks(x); ax.set_xticklabels(_labs(R)); ax.set_ylabel("GHS million")
    lo, hi = M.NM.min() / 1e6, M.NM.max() / 1e6
    ax.set_ylim(min(lo * 1.4, -0.5), hi * 1.25); _title(ax, "Net margin per month (GHS m, % of sales)"); _note_partial(ax, R); return f


def margin_per_litre(R):
    S = R["S"]; S = S[~S.Loss]
    g = S.groupby(["Month", "Prod"]).apply(lambda d: d.NM.sum() / d.Qty.sum(), include_groups=False).unstack()
    f, ax = th.fig(); labs = _labs(R); pos = {m: i for i, m in enumerate(R["M"].index)}
    pc = _pcolors(R)
    for p in pc:
        if p not in g.columns:
            continue
        s = g[p].dropna()
        ax.plot([pos[i] for i in s.index], s.values, marker="o", lw=2.4, color=pc[p], label=p)
    ax.axhline(0, color=th.INK2, lw=1)
    ax.set_xticks(list(pos.values())); ax.set_xticklabels(labs); ax.set_ylabel("GHS per litre")
    _title(ax, "Net margin per litre by product"); ax.legend(loc="best"); _note_partial(ax, R); return f


def margin_by_product(R):
    """Total net margin (GHS m) per product per month; same layout as margin_per_litre."""
    S = R["S"]; S = S[~S.Loss]
    g = S.groupby(["Month", "Prod"]).NM.sum().unstack()
    order = S.groupby("Prod").NM.sum().sort_values(ascending=False).index
    f, ax = th.fig(); labs = _labs(R); pos = {m: i for i, m in enumerate(R["M"].index)}
    pc = _pcolors(R)
    for p in [p for p in pc if p in g.columns]:
        s = g[p].dropna()
        ax.plot([pos[i] for i in s.index], s.values / 1e6, marker="o", lw=2.4, color=pc[p], label=p)
    ax.axhline(0, color=th.INK2, lw=1)
    ax.set_xticks(list(pos.values())); ax.set_xticklabels(labs); ax.set_ylabel("GHS million")
    _title(ax, "Total net margin by product"); ax.legend(loc="best"); _note_partial(ax, R); return f


def price_vs_cost(R):
    S = R["S"]; S = S[~S.Loss]
    prods = S.groupby("Prod").Qty.sum().sort_values(ascending=False).index[:3]
    f, axes = plt.subplots(1, len(prods), figsize=(11, 4.4), sharex=False)
    axes = np.atleast_1d(axes)
    for ax, p in zip(axes, prods):
        d = S[S.Prod == p].groupby("Month").apply(lambda d: pd.Series({"asp": d.Rev.sum() / d.Qty.sum(), "acp": (d.Cogs.sum() + d.Other.sum() + d.Fin.sum()) / d.Qty.sum()}), include_groups=False)
        x = np.arange(len(d))
        ax.plot(x, d.asp, color=th.BLUE, marker="o", lw=2.3, label="Avg selling price")
        ax.plot(x, d.acp, color=th.ORANGE, marker="o", lw=2.3, label="Avg total cost")
        ax.fill_between(x, d.acp, d.asp, where=d.asp >= d.acp, color=th.GOOD, alpha=.18, interpolate=True)
        ax.fill_between(x, d.acp, d.asp, where=d.asp < d.acp, color=th.BAD, alpha=.25, interpolate=True)
        ax.set_xticks(x); ax.set_xticklabels([i.strftime("%b") for i in d.index], fontsize=9)
        ax.set_title(p, loc="center"); ax.set_ylabel("GHS per litre" if ax is axes[0] else "")
    axes[0].legend(loc="upper left", fontsize=8.5)
    f.tight_layout(); return f


def bridge(R):
    t = R["tot"]; gross = t["rev"] - t["cogs"]
    steps = [("Gross trading margin\n(sales − product cost)", gross, "total"), ("Licence &\nother costs", -t["oth"], "delta"),
             ("Margin before\nfinancing", t["gm"], "total"), ("RSTL financing\ncost", -t["fin"], "delta"), ("Net margin", t["nm"], "total")]
    f, ax = th.fig(); run = 0
    for i, (lab, v, kind) in enumerate(steps):
        if kind == "total":
            ax.bar(i, v / 1e6, color=th.NAVY if i < 4 else th.GOOD, width=.58); run = v; top = v
        else:
            ax.bar(i, v / 1e6, bottom=run / 1e6, color=th.ORANGE, width=.58); run += v; top = run - v
        ax.text(i, max(top, run) / 1e6, th.m(v, 2), ha="center", va="bottom", fontsize=11, fontweight="bold")
    ax.set_xticks(range(len(steps))); ax.set_xticklabels([s[0] for s in steps]); ax.set_ylabel("GHS million")
    ax.set_ylim(0, gross / 1e6 * 1.15); _title(ax, "From trading margin to net margin"); ax.grid(False, axis="x"); return f


def cumulative(R):
    d = R["daily"]; f, ax = th.fig()
    ax.plot(d.index, d / 1e6, color=th.BLUE, lw=2.4); ax.fill_between(d.index, 0, d / 1e6, color=th.BLUE, alpha=.12)
    ax.axhline(0, color=th.INK2, lw=1)
    ax.annotate(f"GHS {th.m(d.iloc[-1],1)}m", xy=(d.index[-1], d.iloc[-1] / 1e6), xytext=(-8, 10), textcoords="offset points",
                ha="right", fontweight="bold", color=th.BLUE)
    import matplotlib.dates as mdates
    ax.xaxis.set_major_locator(mdates.MonthLocator()); ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.set_ylabel("GHS million"); return f


# ---------- trades ----------
def funder_split(R):
    T = R["T"]; cnt = T.Funder.value_counts(); vol = T.groupby("Funder").Sold.sum().reindex(cnt.index)
    nm = T.groupby("Funder").NM.sum().reindex(cnt.index)
    f, axes = plt.subplots(1, 3, figsize=(11, 4.9))
    _donut(axes[0], list(cnt.index), cnt.values, "Number of trades", lambda v: f"{v:,.0f}")
    _donut(axes[1], list(vol.index), vol.values, "Litres sold", lambda v: f"{v/1e6:,.1f}m L")
    _donut(axes[2], list(nm.index), nm.values, "Net margin", lambda v: f"GHS {v/1e6:,.1f}m")
    f.tight_layout(); return f


def trade_margin(R):
    T = R["T"]; f, ax = th.fig(11, 4.8); x = np.arange(len(T))
    ax.bar(x, T.NM / 1e6, color=[th.GOOD if v >= 0 else th.BAD for v in T.NM], width=.7)
    for i, (v, st) in enumerate(zip(T.NM / 1e6, T.Status)):
        ax.text(i, v + (.05 if v >= 0 else -.05), f"{v:.1f}", ha="center", va="bottom" if v >= 0 else "top", fontsize=7.5)
    ax.axhline(0, color=th.INK2, lw=1)
    ax.set_xticks(x); ax.set_xticklabels([i + ("†" if s == "Open" else "") for i, s in zip(T.index, T.Status)], rotation=70, ha="right", fontsize=8.5)
    ax.set_ylabel("GHS million"); _title(ax, "Net margin by trade, in order of purchase")
    if (T.Status == "Open").any():
        ax.annotate("† trade still open (provisional)", xy=(1, 1.02), xycoords="axes fraction", ha="right", fontsize=8.5, color=th.GREY)
    return f


def trade_scatter(R):
    T = R["T"]; f, ax = th.fig(11, 4.9)
    for fu, c in zip(T.Funder.unique(), th.CAT):
        d = T[T.Funder == fu]
        ax.scatter(d.Sold / 1e6, d.NMpl, s=d.Rev / 1e6 * 4 + 25, color=c, alpha=.75, edgecolor="white", label=fu)
    for i, r in T.iterrows():
        ax.annotate(i, (r.Sold / 1e6, r.NMpl), xytext=(4, 4), textcoords="offset points", fontsize=7.5, color=th.INK2)
    ax.axhline(0, color=th.INK2, lw=1); ax.grid(True, axis="both")
    ax.set_xlabel("Litres sold (million)"); ax.set_ylabel("Net margin, GHS per litre")
    _title(ax, "Trade size vs profitability (bubble = sales)"); ax.legend(loc="best", title="Funder"); return f


def days_to_sell(R):
    T = R["T"]; f, ax = th.fig(11, 4.4); x = np.arange(len(T))
    ax.bar(x, T.DaysToSell, color=th.BLUE, width=.7)
    avg = R["tot"]["days"]; ax.axhline(avg, color=th.ORANGE, ls="--", lw=2, label=f"Volume-weighted average: {avg:.0f} days")
    ax.set_xticks(x); ax.set_xticklabels(T.index, rotation=70, ha="right", fontsize=8.5)
    ax.set_ylabel("Days"); _title(ax, "Days from purchase to loading (volume-weighted)"); ax.legend(loc="upper left"); return f


# ---------- product / depot ----------
def product_split(R):
    T, fp = R["T"], R["cuts"]["facility_prod"]
    vol = R["cuts"]["prod"].Vol.reindex(fp.index).fillna(0)
    nm = fp.NM
    f, axes = plt.subplots(1, 3, figsize=(11, 4.9))
    pc = _pcolors(R); cols = [pc.get(p, th.GREY) for p in fp.index]
    _donut(axes[0], list(vol.index), vol.values, "Litres sold", lambda v: f"{v/1e6:,.1f}m L", colors=cols)
    _donut(axes[1], list(fp.index), fp.Facility.values, "Bank facility drawn", lambda v: f"GHS {v/1e6:,.0f}m", colors=cols)
    _donut(axes[2], list(nm.index), nm.values, "Net margin", lambda v: f"GHS {v/1e6:,.1f}m", colors=cols)
    f.tight_layout(); return f


def product_unit_margin(R):
    p = R["cuts"]["prod"].copy(); T = R["T"]
    gm = R["S"][~R["S"].Loss].groupby("Prod").apply(lambda d: d.GM.sum() / d.Qty.sum(), include_groups=False).reindex(p.index)
    f, ax = th.fig(8.5, 4.4); x = np.arange(len(p)); w = .36
    b1 = ax.bar(x - w / 2, gm, w, color=th.NAVY, label="Before financing")
    b2 = ax.bar(x + w / 2, p.NMpl, w, color=th.BLUE, label="Net of financing")
    for b in list(b1) + list(b2):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{b.get_height():.2f}", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(p.index); ax.set_ylabel("GHS per litre"); ax.axhline(0, color=th.INK2, lw=1)
    _title(ax, "Margin per litre by product"); ax.set_ylim(min(0, p.NMpl.min()*1.3), max(gm.max(), p.NMpl.max())*1.32); ax.legend(loc="upper left"); return f


def depot_chart(R):
    d = R["cuts"]["depot"].sort_values("Vol"); f, ax = th.fig(11, max(3.6, .5 * len(d) + 1.2))
    bars = ax.barh(d.index, d.Vol / 1e6, color=th.BLUE, height=.62)
    for b, (_, r) in zip(bars, d.iterrows()):
        ax.text(b.get_width(), b.get_y() + b.get_height() / 2, f"  {r.Vol/1e6:.1f}m L · net GHS {r.NMpl:.2f}/L",
                va="center", fontsize=9.5, color=th.GOOD if r.NMpl >= 0 else th.BAD)
    ax.set_xlim(0, d.Vol.max() / 1e6 * 1.4); ax.set_xlabel("Million litres sold"); ax.grid(True, axis="x"); ax.grid(False, axis="y")
    _title(ax, "Litres sold by depot"); return f


# ---------- customers ----------
def top_customers(R, n=10):
    c = R["cuts"]["cust"].head(n).iloc[::-1]; f, ax = th.fig(11, 4.9)
    bars = ax.barh(c.index, c.Rev / 1e6, color=[th.BAD if v < 0 else th.BLUE for v in c.NM], height=.64)
    for b, (_, r) in zip(bars, c.iterrows()):
        ax.text(b.get_width(), b.get_y() + b.get_height() / 2, f"  {r.Share:.1%} of sales · net GHS {r.NMpl:.2f}/L",
                va="center", fontsize=9.3, color=th.INK2)
    ax.set_xlim(0, c.Rev.max() / 1e6 * 1.42); ax.set_xlabel("Sales, GHS million"); ax.grid(True, axis="x"); ax.grid(False, axis="y")
    _title(ax, f"Top {n} customers by sales (red = loss-making)"); return f


def concentration(R):
    c = R["cuts"]["cust"]; cum = c.Share.cumsum().values; f, ax = th.fig(8.5, 4.4)
    ax.plot(np.arange(1, len(cum) + 1), cum * 100, color=th.BLUE, lw=2.5)
    for k in (5, 10, 20):
        if len(cum) >= k:
            ax.scatter([k], [cum[k - 1] * 100], color=th.ORANGE, zorder=3)
            ax.annotate(f"Top {k}: {cum[k-1]:.0%}", (k, cum[k - 1] * 100), xytext=(8, -14), textcoords="offset points", fontsize=10, fontweight="bold")
    ax.set_ylim(0, 105); ax.set_xlabel("Customers, ranked by sales"); ax.set_ylabel("Cumulative share of sales (%)")
    ax.grid(True, axis="both"); _title(ax, "Customer concentration"); return f


# ---------- funding ----------
def funding_by_month(R):
    T = R["T"].copy(); T["Month"] = T.Start.dt.to_period("M")
    g = T.groupby("Month").agg(Own=("Own", "sum"), Loan=("Loan", "sum")); f, ax = th.fig(); x = np.arange(len(g))
    ax.bar(x, g.Loan / 1e6, color=th.NAVY, width=.6, label="Bank facility (80%)")
    ax.bar(x, g.Own / 1e6, bottom=g.Loan / 1e6, color=th.ORANGE, width=.6, label="Own cash (20%)")
    for i, (a, b) in enumerate(zip(g.Loan, g.Own)):
        ax.text(i, (a + b) / 1e6, f"{(a+b)/1e6:,.0f}", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels([i.strftime("%b") for i in g.index]); ax.set_ylabel("GHS million")
    ax.set_ylim(0, (g.Loan + g.Own).max() / 1e6 * 1.14); _title(ax, "Product purchased by month: how it was funded"); ax.legend(loc="upper left"); return f


def interest_by_trade(R):
    T = R["T"]; f, ax = th.fig(11, 4.4); x = np.arange(len(T))
    if R["tot"]["fin_source"] == "workbook":
        w = .38
        ax.bar(x - w / 2, T.FinW / 1e3, w, color=th.NAVY, label="Workbook Facility Cost (used in report)")
        ax.bar(x + w / 2, T.FinP / 1e3, w, color=th.ORANGE, label="Interest per PURCHASES (booked + estimated)")
    else:
        ax.bar(x, T.Rec.fillna(0) / 1e3, color=th.NAVY, width=.7, label="Recorded in PURCHASES")
        ax.bar(x, (T.Est.fillna(0) + T.Accr.fillna(0)) / 1e3, bottom=T.Rec.fillna(0) / 1e3, color=th.ORANGE, width=.7, label="Estimated / accrued")
    ax.set_xticks(x); ax.set_xticklabels(T.index, rotation=70, ha="right", fontsize=8.5)
    ax.set_ylabel("GHS thousand"); _title(ax, "RSTL financing cost by trade"); ax.legend(loc="upper left"); return f


def open_loans(R):
    T = R["T"]; o = T[T.Status == "Open"]
    if o.empty:
        return None
    f, ax = th.fig(8.5, 3.6)
    bars = ax.bar(o.index, o.Remaining / 1e6, color=th.ORANGE, width=.5)
    for b, v in zip(bars, o.Remaining / 1e6):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:,.1f}", ha="center", va="bottom", fontsize=11, fontweight="bold")
    ax.set_ylim(0, o.Remaining.max() / 1e6 * 1.18); ax.set_ylabel("GHS million"); _title(ax, "Bank loan still outstanding"); return f
