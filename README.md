# RSTL Profitability App

Upload the RSTL tracker workbook and get a full profitability report with charts, tables and written findings,
plus a master report to download and present.

    pip install -r requirements.txt
    streamlit run app.py        # main file path on Streamlit Cloud: app.py

## Where things live

    app.py                  Screen: upload, tabs, download buttons. Keep thin.
    rstl/loader.py          Reads the workbook (SALES, PURCHASES), merges customer/depot name variants (ALIASES, DEPOT_MAP)
    rstl/analysis.py        Financing cost rebuild, trade / month / segment tables, trend
    rstl/narrative.py       Written findings and data-quality notes
    rstl/charts.py          Every chart (one function each)
    rstl/sections.py        Report structure: which charts/tables go in which section, with captions
    rstl/theme.py           Colours and chart style
    rstl/export/            pdf.py (PDF), pptx_deck.py (PowerPoint), excel.py (Excel)
    .streamlit/config.toml  App theme

## Adding a chart
1. Write `def my_chart(R): ... return fig` in `rstl/charts.py`.
2. Add `_fig("Title", "Caption", C.my_chart(R))` to the right section in `rstl/sections.py`.
It then appears in the app, the section PDF, the master PDF and the master PowerPoint.

## Adding a section
Create a `Section` in `build_sections` and append it to the `secs` list.
