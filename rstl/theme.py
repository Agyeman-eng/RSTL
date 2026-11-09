"""Shared look for every chart and export."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

NAVY, BLUE, BLUE_L = "#14304f", "#2a78d6", "#9dc3f0"
ORANGE, GOOD, BAD, GREY, GRID = "#eb6834", "#1a7f4b", "#c9302c", "#7a838e", "#e3e6ea"
INK, INK2 = "#14181d", "#4a525c"
CAT = [BLUE, ORANGE, "#1baf7a", "#6250d6", "#eda100", "#e87ba4", "#008300", "#e34948"]

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
    "font.family": "DejaVu Sans", "font.size": 10.5, "text.color": INK, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.edgecolor": "#c9ced4",
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "axes.axisbelow": True,
    "grid.color": GRID, "grid.linewidth": .8, "axes.grid.axis": "y",
    "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlelocation": "left", "legend.frameon": False,
})


def fig(w=11, h=4.6, **kw):
    f, ax = plt.subplots(figsize=(w, h), **kw)
    return f, ax


def m(v, d=1):
    """Millions with sign-safe minus."""
    s = f"{abs(v)/1e6:,.{d}f}"
    return ("−" if v < 0 else "") + s


def png(f, dpi=170):
    import io
    b = io.BytesIO()
    f.savefig(b, format="png", dpi=dpi, bbox_inches="tight", pad_inches=.15)
    plt.close(f)
    return b.getvalue()
