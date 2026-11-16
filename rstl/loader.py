"""Read the RSTL tracker workbook into clean SALES and PURCHASES tables."""
import re
import numpy as np
import pandas as pd

# Merge common OMC name variants. Add new spellings here.
ALIASES = {
    "DUKES PETROLEUM LTD.": "DUKES PETROLEUM", "DUKES PETROLEUM LTD": "DUKES PETROLEUM",
    "LA CLEM GHANA LIMITED": "LA CLEM GHANA", "JD-LINK OIL COMPANY LIMITED": "JD-LINK COMPANY",
    "KINGSPERP OIL": "KINGSPERP OIL LIMITED",
}
# Merge depot spellings.
DEPOT_MAP = {"BOST - APD": "BOST", "BOST - KUMASI": "BOST", "BOST - BUIPE": "BOST", "BOST-BUIPE": "BOST",
             "TOR - PETHUB": "PETHUB", "VANA": "TOR"}


def funder(tid):
    """FAB trades are A001, A002...; others use their prefix (OMNI-001 -> OMNI)."""
    if re.fullmatch(r"A\d+.*", tid):
        return "FAB"
    m = re.match(r"([A-Za-z]+)", tid)
    return m.group(1).upper() if m else "Other"


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


def _opt(df, *names):
    """Optional column: the sheet's values if present, else NaN."""
    try:
        return df[_col(df, *names)]
    except ValueError:
        return pd.Series(float("nan"), index=df.index)


def facility_ok(S):
    """True when the workbook's Facility Cost is a clean per-litre figure and Total Cost/Ltr adds up on (almost) every row."""
    if S.Fac.isna().all() or S.TC.isna().all():
        return False
    if S.Fac.max() >= 1:  # totals mixed in with per-litre values (older, uncleaned sheets)
        return False
    ok = ((S.CP + S.Fac.fillna(0) + S.Var + S.CM - S.TC).abs() < 1e-4)
    return bool(ok.mean() > 0.99)


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
        "CM": s[_col(s, "CM cost/ Ltr", "CM cost/Ltr")].fillna(0),
        "Fac": _opt(s, "Facility Cost"), "TC": _opt(s, "Total Cost/Ltr", "Total Cost/ Ltr", "Total Cost"),
        "TM": _opt(s, "Total Margin")})
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


def load_rstl_qty(file):
    """RSTL-only litres per trade: Sheet4 'Total OMC loadings'. In the workbook this is the SALES total for the trade
    minus litres bought outside RSTL (the portal does not separate RSTL stock from other stock). Returns None if unavailable."""
    try:
        h = _sheet(pd.ExcelFile(file), "sheet4")
        idc, qc = _col(h, "ID"), _col(h, "Total OMC loadings")
    except ValueError:
        return None
    h = h.dropna(subset=[idc])
    s = pd.Series(pd.to_numeric(h[qc], errors="coerce").values, index=h[idc].astype(str).str.strip()).dropna()
    s = s[~s.index.duplicated()]
    return s if len(s) else None


def infer_rates(P):
    """Implied annual rate per funder, from drawdowns that already carry booked interest.
    Each facility can carry its own rate (e.g. FAB 13.03%, OMNI 13.59%)."""
    by = {}
    for tid, g in P.groupby("ID"):
        by.setdefault(funder(tid), []).append(g)
    allr = {f: _implied(pd.concat(gs)) for f, gs in by.items()}
    pool = [r for v in allr.values() for r in v]
    fallback = float(np.median(pool)) if pool else 0.1303
    return {f: (float(np.median(v)) if v else fallback) for f, v in allr.items()}


def infer_rate(P):
    """Single overall rate (median across all funders)."""
    r = list(infer_rates(P).values())
    return float(np.median(r)) if r else 0.1303


def _implied(P):
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
            bal -= r.Pay
            prev = r.Date
    return rates
