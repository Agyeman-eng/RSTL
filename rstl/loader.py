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
            bal -= r.Pay
            prev = r.Date
    return float(np.median(rates)) if rates else 0.1303
