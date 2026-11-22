"""Construit la base SQLite en schéma en étoile et exporte les tables pour Power BI.

Tables :
    dim_actif         un actif par ligne (ticker, nom, secteur, pays)
    dim_date          calendrier (date, année, mois, trimestre, jour de semaine)
    fait_prix         cours et rendement journalier par actif
    fait_portefeuille rendement journalier de chaque stratégie backtestée
    fait_poids        poids de chaque actif à chaque rebalancement

Utilisation :
    python src/build_database.py
"""
import sqlite3
from pathlib import Path

import pandas as pd

import quant as q

ROOT = Path(__file__).resolve().parents[1]
TICKERS = ["AAPL", "MSFT", "NVDA", "GOOG", "META", "SAP", "TSM", "NFLX"]
ACTIFS = pd.DataFrame([
    ("AAPL", "Apple", "Matériel et logiciels", "États Unis"),
    ("MSFT", "Microsoft", "Logiciels et cloud", "États Unis"),
    ("NVDA", "Nvidia", "Semiconducteurs", "États Unis"),
    ("GOOG", "Alphabet", "Internet et publicité", "États Unis"),
    ("META", "Meta Platforms", "Internet et publicité", "États Unis"),
    ("SAP", "SAP", "Logiciels d'entreprise", "Allemagne"),
    ("TSM", "TSMC", "Semiconducteurs", "Taïwan"),
    ("NFLX", "Netflix", "Médias et streaming", "États Unis"),
], columns=["ticker", "nom", "secteur", "pays"])

STRATEGIES = {
    "Équipondéré": q.equal_weight,
    "Variance minimale": q.min_variance,
    "Parité de risque": q.risk_parity,
    "Sharpe maximal": q.max_sharpe,
    "Momentum 12 moins 1": q.momentum,
}


def run_backtests(r: pd.DataFrame):
    rets, weights = {}, []
    for name, fn in STRATEGIES.items():
        port, w = q.backtest(r, fn)
        rets[name] = port
        w = w.stack().rename("poids").reset_index()
        w.columns = ["date", "ticker", "poids"]
        w["strategie"] = name
        weights.append(w)
    rets = pd.DataFrame(rets).dropna()
    return rets, pd.concat(weights, ignore_index=True)


def main() -> None:
    prices = q.load_prices(ROOT / "data" / "raw", TICKERS)
    r = q.returns(prices)
    strat, poids = run_backtests(r)

    fait_prix = (prices.stack().rename("cloture").to_frame()
                 .join(r.stack().rename("rendement")).reset_index())
    fait_prix.columns = ["date", "ticker", "cloture", "rendement"]
    fait_portefeuille = strat.stack().rename("rendement").reset_index()
    fait_portefeuille.columns = ["date", "strategie", "rendement"]

    dates = pd.DataFrame({"date": prices.index})
    dates["annee"] = dates.date.dt.year
    dates["trimestre"] = dates.date.dt.quarter
    dates["mois"] = dates.date.dt.month
    dates["jour_semaine"] = dates.date.dt.dayofweek + 1

    out = ROOT / "data" / "processed"
    out.mkdir(parents=True, exist_ok=True)
    tables = {"dim_actif": ACTIFS, "dim_date": dates, "fait_prix": fait_prix,
              "fait_portefeuille": fait_portefeuille, "fait_poids": poids}
    db = out / "marches.db"
    db.unlink(missing_ok=True)
    with sqlite3.connect(db) as con:
        con.executescript((ROOT / "sql" / "schema.sql").read_text(encoding="utf8"))
        for name, df in tables.items():
            df = df.copy()
            if "date" in df:
                df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
            df.to_sql(name, con, if_exists="append", index=False)
            df.to_csv(ROOT / "powerbi" / "donnees" / f"{name}.csv", index=False)
    print(f"Base créée : {db} ({len(fait_prix)} lignes de prix, {len(STRATEGIES)} stratégies)")


if __name__ == "__main__":
    (ROOT / "powerbi" / "donnees").mkdir(parents=True, exist_ok=True)
    main()
