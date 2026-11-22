"""Génère le tableau de bord à partir de la base SQLite.

Deux sorties :
    reports/dashboard.png    vue statique du rapport (style Power BI)
    reports/dashboard.html   version interactive (Plotly), un onglet par stratégie

Utilisation :
    python src/dashboard.py --strategie "Parité de risque"
"""
import argparse
import sqlite3
from pathlib import Path

import matplotlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch

import quant as q

matplotlib.use("Agg")
ROOT = Path(__file__).resolve().parents[1]
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
BG, CARD, INK, SOFT, NAV, TEAL = "#f3f6f9", "#ffffff", "#1b2733", "#6b7a86", "#0f2240", "#2ec4b0"
COLS = ["#2ec4b0", "#2563eb", "#f59e0b", "#8b5cf6", "#ef4444", "#0ea5e9", "#84cc16", "#ec4899"]


def load():
    with sqlite3.connect(ROOT / "data" / "processed" / "marches.db") as con:
        prix = pd.read_sql("SELECT p.date, a.nom, p.cloture, p.rendement FROM fait_prix p "
                           "JOIN dim_actif a USING (ticker)", con, parse_dates=["date"])
        strat = pd.read_sql("SELECT * FROM fait_portefeuille", con, parse_dates=["date"])
        poids = pd.read_sql("SELECT f.date, a.nom, f.poids, f.strategie FROM fait_poids f "
                            "JOIN dim_actif a USING (ticker)", con, parse_dates=["date"])
    r_actifs = prix.pivot(index="date", columns="nom", values="rendement").dropna()
    r_strat = strat.pivot(index="date", columns="strategie", values="rendement").dropna()
    return r_actifs, r_strat, poids


def fr(x, d=1, pct=True):
    s = f"{x * 100:.{d}f} %" if pct else f"{x:.{d}f}"
    return s.replace(".", ",")


def date_fmt(x, _):
    d = mdates.num2date(x)
    return f"{MOIS[d.month - 1]} {d.year}"


def card(fig, x, y, w, h):
    ax = fig.add_axes([x, y, w, h])
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.04", fc=CARD,
                                ec="#dfe6ec", lw=1, transform=ax.transAxes, mutation_aspect=w / h * 1.6))
    return ax


def style(ax, title, pad=10):
    ax.set_facecolor(CARD)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=SOFT, labelsize=10, length=0)
    ax.grid(axis="y", color="#eef2f5", lw=1)
    ax.set_axisbelow(True)
    ax.set_title(title, loc="left", fontsize=14, fontweight="bold", color=INK, pad=pad)


def static_dashboard(r_actifs, r_strat, poids, choix, out):
    port = r_strat[choix]
    debut, fin = port.index.min(), port.index.max()
    fig = plt.figure(figsize=(16, 10), dpi=110, facecolor=BG)

    nav = fig.add_axes([0, 0, 0.13, 1]); nav.axis("off")
    nav.add_patch(plt.Rectangle((0, 0), 1, 1, color=NAV, transform=nav.transAxes))
    nav.text(0.12, 0.95, "Marchés", color="white", fontsize=19, fontweight="bold", transform=nav.transAxes)
    nav.text(0.12, 0.925, "Finance quantitative", color="#8fb3d9", fontsize=11, transform=nav.transAxes)
    for i, t in enumerate(["Vue d'ensemble", "Rendements", "Risque et VaR", "Drawdown", "Backtesting", "Portefeuille"]):
        y = 0.84 - i * 0.055
        if i == 0:
            nav.add_patch(FancyBboxPatch((0.07, y - 0.017), 0.86, 0.042, boxstyle="round,pad=0,rounding_size=0.02",
                                         fc=TEAL, alpha=.25, ec="none", transform=nav.transAxes))
        nav.text(0.14, y, t, color="white" if i == 0 else "#b9c8d8", fontsize=12.5, transform=nav.transAxes, va="center")
    nav.text(0.12, 0.08, "Période", color="#8fb3d9", fontsize=10, transform=nav.transAxes)
    nav.text(0.12, 0.05, f"{MOIS[debut.month - 1].capitalize()} {debut.year} à {MOIS[fin.month - 1]} {fin.year}",
             color="white", fontsize=11.5, transform=nav.transAxes)

    fig.text(0.155, 0.945, "Tableau de bord des marchés financiers", fontsize=22, fontweight="bold", color=INK)
    fig.text(0.155, 0.915, f"Stratégie affichée : {choix.lower()}, rebalancement mensuel, frais de 10 points de base inclus",
             fontsize=12, color=SOFT)

    kpis = [("Rendement annualisé", fr(q.annual_return(port)), TEAL),
            ("Volatilité annualisée", fr(q.annual_volatility(port)), "#2563eb"),
            ("VaR 95 % journalière", fr(q.var_historique(port), 2), "#f59e0b"),
            ("Drawdown maximal", fr(abs(q.max_drawdown(port))), "#ef4444"),
            ("Ratio de Sharpe", fr(q.sharpe(port), 2, pct=False), "#8b5cf6")]
    for i, (t, v, c) in enumerate(kpis):
        ax = card(fig, 0.155 + i * 0.167, 0.765, 0.155, 0.115)
        ax.add_patch(plt.Rectangle((0.08, 0.78), 0.12, 0.05, color=c, transform=ax.transAxes))
        ax.text(0.08, 0.6, t, fontsize=12, color=SOFT, transform=ax.transAxes)
        ax.text(0.08, 0.2, v, fontsize=27, fontweight="bold", color=INK, transform=ax.transAxes)

    card(fig, 0.155, 0.385, 0.53, 0.355)
    ax = fig.add_axes([0.185, 0.42, 0.48, 0.245])
    style(ax, "Stratégies en base 100", pad=26)
    base = 100 * (1 + r_strat).cumprod()
    for i, c in enumerate(base.columns):
        ax.plot(base.index, base[c], color=COLS[i], lw=2.6 if c == choix else 1.5, alpha=1 if c == choix else .8, label=c)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(date_fmt))
    ax.legend(ncol=5, fontsize=9.5, frameon=False, loc="lower left", bbox_to_anchor=(0, 1.0), handlelength=1.4)

    card(fig, 0.7, 0.385, 0.29, 0.355)
    ax = fig.add_axes([0.79, 0.42, 0.18, 0.27])
    style(ax, "Volatilité annualisée par action")
    v = (q.annual_volatility(r_actifs) * 100).sort_values()
    ax.barh(range(len(v)), v.values, color=TEAL, height=.6)
    ax.set_yticks(range(len(v))); ax.set_yticklabels(v.index, color=INK, fontsize=10.5)
    ax.grid(axis="y", visible=False); ax.set_xticks([])
    for i, val in enumerate(v.values):
        ax.text(val + 1, i, f"{val:.0f} %", va="center", fontsize=10, color=INK)
    ax.set_xlim(0, v.max() * 1.25)

    card(fig, 0.155, 0.035, 0.35, 0.325)
    ax = fig.add_axes([0.185, 0.07, 0.3, 0.235])
    style(ax, "Drawdown de la stratégie")
    dd = q.drawdown(port) * 100
    ax.fill_between(dd.index, dd, 0, color="#ef4444", alpha=.22); ax.plot(dd.index, dd, color="#ef4444", lw=1.3)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(date_fmt))
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{abs(x):.0f} %"))

    card(fig, 0.52, 0.035, 0.235, 0.325)
    ax = fig.add_axes([0.545, 0.07, 0.19, 0.235])
    style(ax, "Distribution et VaR 95 %")
    ax.hist(port.clip(-.08, .08) * 100, bins=60, color="#2563eb", alpha=.75)
    var = q.var_historique(port) * 100
    ax.axvline(-var, color="#f59e0b", lw=2.2)
    ax.text(-var, ax.get_ylim()[1] * .9, "  VaR", color="#b45309", fontsize=10.5, fontweight="bold")
    ax.set_xticks([-4, 0, 4]); ax.set_xticklabels(["perte 4 %", "0 %", "gain 4 %"]); ax.set_yticks([])

    card(fig, 0.77, 0.035, 0.22, 0.325)
    w = poids[poids.strategie == choix]
    w = w[w.date == w.date.max()].set_index("nom").poids.sort_values(ascending=False)
    w = w[w > 0.005]
    ax = fig.add_axes([0.785, 0.07, 0.11, 0.235])
    ax.set_title("Allocation actuelle", loc="left", fontsize=14, fontweight="bold", color=INK, pad=10, x=0.0)
    ax.pie(w.values, colors=COLS[:len(w)], startangle=90, wedgeprops=dict(width=.38, ec="white", lw=2))
    ax.set_aspect("equal")
    for i, (nom, val) in enumerate(w.items()):
        y = 0.285 - i * 0.03
        fig.patches.append(plt.Rectangle((0.9, y), 0.006, 0.011, color=COLS[i], transform=fig.transFigure, figure=fig))
        fig.text(0.91, y, f"{nom}  {val * 100:.0f} %", fontsize=10, color=INK)

    fig.savefig(out, facecolor=BG)
    plt.close(fig)


def interactive_dashboard(r_actifs, r_strat, out):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    base = 100 * (1 + r_strat).cumprod()
    dd = r_strat.apply(q.drawdown) * 100
    table = q.summary(r_strat)
    fig = make_subplots(rows=2, cols=2, row_heights=[0.6, 0.4], vertical_spacing=0.12,
                        specs=[[{"colspan": 2}, None], [{}, {"type": "table"}]],
                        subplot_titles=("Valeur en base 100", "Drawdown (%)", "Indicateurs par stratégie"))
    for i, c in enumerate(base.columns):
        fig.add_trace(go.Scatter(x=base.index, y=base[c], name=c, line=dict(color=COLS[i], width=2),
                                 legendgroup=c), 1, 1)
        fig.add_trace(go.Scatter(x=dd.index, y=dd[c], name=c, line=dict(color=COLS[i], width=1),
                                 legendgroup=c, showlegend=False), 2, 1)
    fmt = table.copy()
    for col in fmt:
        fmt[col] = [f"{v:.2f}" if col in ("Sharpe", "Sortino") else f"{v * 100:.1f} %" for v in table[col]]
    fig.add_trace(go.Table(header=dict(values=["Stratégie"] + list(fmt.columns), fill_color=NAV, font=dict(color="white")),
                           cells=dict(values=[fmt.index] + [fmt[c] for c in fmt.columns])), 2, 2)
    fig.update_layout(title="Tableau de bord des marchés financiers", template="plotly_white", height=900,
                      legend=dict(orientation="h", y=1.06))
    fig.write_html(out, include_plotlyjs="cdn")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategie", default="Parité de risque")
    args = parser.parse_args()
    r_actifs, r_strat, poids = load()
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    static_dashboard(r_actifs, r_strat, poids, args.strategie, reports / "dashboard.png")
    interactive_dashboard(r_actifs, r_strat, reports / "dashboard.html")
    print("Tableau de bord écrit dans", reports)


if __name__ == "__main__":
    main()
