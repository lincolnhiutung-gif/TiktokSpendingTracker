"""Draws the Matplotlib charts as PNG images (no JavaScript needed)."""
import io

import matplotlib

matplotlib.use("Agg")  # draw to memory, not to a window
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, StrMethodFormatter

BAR_COLOUR = "#673ab7"  # same purple as the research screenshots
ACCENT = "#b39ddb"  # lighter purple for the second bar
TEXT = "#1f2430"
TITLE = "#4527a0"  # dark purple titles
GRID = "#e6ddf5"  # pale purple grid lines


def _style(ax, title, xlabel, ylabel, horizontal=False):
    ax.set_title(title, fontsize=14, color=TITLE, loc="left", pad=12, fontweight="bold")
    ax.set_xlabel(xlabel, fontsize=11, color=TEXT)
    ax.set_ylabel(ylabel, fontsize=11, color=TEXT)
    ax.tick_params(colors=TEXT, labelsize=10)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(BAR_COLOUR)
    # Counts are whole numbers, so never show ticks like 0.2 or 0.4 (only on the axis with the numbers)
    value_axis = ax.xaxis if horizontal else ax.yaxis
    value_axis.set_major_locator(MaxNLocator(nbins=5, integer=True))  # at most ~5 ticks so labels never overlap


def _to_png(fig):
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    buffer.seek(0)
    return buffer


def bar_chart(labels, values, title, xlabel, ylabel, money=False, horizontal=False):
    fig, ax = plt.subplots(figsize=(7, 4.2))
    if not labels:
        ax.text(0.5, 0.5, "No data for this filter", ha="center", va="center", fontsize=13, color=TEXT)
        ax.axis("off")
        return _to_png(fig)

    if horizontal:
        bars = ax.barh(labels, values, color=BAR_COLOUR)
        ax.invert_yaxis()  # largest at the top
        ax.grid(axis="x", color=GRID, linewidth=0.8)
    else:
        bars = ax.bar(labels, values, color=BAR_COLOUR)
        plt.setp(ax.get_xticklabels(), rotation=20, ha="right")

    _style(ax, title, xlabel, ylabel, horizontal)
    if horizontal:
        ax.grid(axis="y", visible=False)

    if money:  # show €1,000,000 on the axis instead of "1e6"
        (ax.xaxis if horizontal else ax.yaxis).set_major_formatter(StrMethodFormatter("€{x:,.0f}"))

    # Write the value on each bar so the chart can be read without guessing
    fmt = "€{:,.0f}" if money else "{:,.0f}"
    ax.bar_label(bars, labels=[fmt.format(v) for v in values], padding=3, fontsize=10, color=TEXT)
    ax.margins(x=0.12 if horizontal else 0.02, y=0.02 if horizontal else 0.12)
    return _to_png(fig)


def yes_no_chart(yes, no, title):
    fig, ax = plt.subplots(figsize=(7, 4.2))
    total = yes + no
    if total == 0:
        ax.text(0.5, 0.5, "No data for this filter", ha="center", va="center", fontsize=13, color=TEXT)
        ax.axis("off")
        return _to_png(fig)

    labels = ["Would have bought it anyway", "Only bought it because of TikTok"]
    values = [yes, no]
    bars = ax.barh(labels, values, color=[BAR_COLOUR, ACCENT])
    ax.invert_yaxis()
    _style(ax, title, "Number of purchases", "", horizontal=True)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.bar_label(bars, labels=[f"{v} ({v / total:.0%})" for v in values], padding=3, fontsize=10, color=TEXT)
    ax.margins(x=0.25)
    return _to_png(fig)
