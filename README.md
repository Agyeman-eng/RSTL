# RSTL Profitability App

    pip install -r requirements.txt
    streamlit run app.py

Upload the RSTL tracker (.xlsx) in the sidebar. Needs SALES and PURCHASES sheets with the standard headers.
The app produces KPIs, a written summary, monthly volume with trend line, sales and margin charts, trade scorecard,
product / funder / depot / customer cuts, funding and exposure, data-quality notes, and an Excel export.

Assumptions in the sidebar: interest rate (auto-detected from booked interest) and the date open loans accrue to.
Customer name variants are merged in `ALIASES` at the top of analysis.py; add new ones there.
