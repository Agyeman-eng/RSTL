import io
import pandas as pd


def to_xlsx(R, sections):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame({"Summary": [p.replace("**", "") for p in sections[0].paras]}).to_excel(w, sheet_name="Summary", index=False)
        R["T"].reset_index().assign(Start=lambda d: d.Start.dt.date).to_excel(w, sheet_name="Trades", index=False)
        R["M"].reset_index().assign(Month=lambda d: d.Month.astype(str)).to_excel(w, sheet_name="Monthly", index=False)
        for k, v in R["cuts"].items():
            v.reset_index().to_excel(w, sheet_name=k[:30], index=False)
        for ws in w.book.worksheets:
            for col in ws.iter_cols(min_row=1, max_row=1):
                ws.column_dimensions[col[0].column_letter].width = max(13, len(str(col[0].value)) + 3)
            ws.freeze_panes = "B2"
    return buf.getvalue()
