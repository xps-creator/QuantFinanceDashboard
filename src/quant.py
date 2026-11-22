"""Outils de finance quantitative : rendements, risque, backtesting et optimisation.

Toutes les fonctions prennent des DataFrame pandas indexés par date, avec une
colonne par actif. Les rendements sont des rendements simples journaliers.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import norm

JOURS = 252


# Chargement

def load_prices(folder: str | Path, tickers: list[str], start: str = "2019-01-01",
                end: str | None = None) -> pd.DataFrame:
    """Lit un fichier CSV par actif (colonnes date, open, high, low, close, volume)."""
    series = {}
    for t in tickers:
        df = pd.read_csv(Path(folder) / f"{t}.csv", parse_dates=["date"])
        series[t] = df.set_index("date")["close"]
    prices = pd.DataFrame(series).sort_index().loc[start:end]
    return prices.dropna(how="any")


def returns(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.pct_change().dropna(how="all")


# Mesures de performance et de risque

def annual_return(r: pd.Series | pd.DataFrame):
    growth = (1 + r).prod()
    return growth ** (JOURS / len(r)) - 1


def annual_volatility(r):
    return r.std() * np.sqrt(JOURS)


def sharpe(r, rf: float = 0.02):
    return (annual_return(r) - rf) / annual_volatility(r)


def sortino(r, rf: float = 0.02):
    downside = r.clip(upper=0).pow(2).mean() ** 0.5 * np.sqrt(JOURS)
    return (annual_return(r) - rf) / downside


def drawdown(r: pd.Series) -> pd.Series:
    wealth = (1 + r).cumprod()
    return wealth / wealth.cummax() - 1


def max_drawdown(r):
    if isinstance(r, pd.DataFrame):
        return r.apply(lambda s: drawdown(s).min())
    return drawdown(r).min()


def var_historique(r, alpha: float = 0.95):
    """Perte journalière dépassée seulement (1 - alpha) % du temps (en valeur positive)."""
    return -np.percentile(r, 100 * (1 - alpha), axis=0)


def var_parametrique(r, alpha: float = 0.95):
    """VaR gaussienne : moyenne et écart type des rendements."""
    return -(r.mean() + norm.ppf(1 - alpha) * r.std())


def cvar(r, alpha: float = 0.95):
    """Expected shortfall : perte moyenne au delà de la VaR historique."""
    r = pd.DataFrame(r)
    out = {}
    for c in r:
        v = -var_historique(r[c], alpha)
        out[c] = -r[c][r[c] <= v].mean()
    s = pd.Series(out)
    return s.iloc[0] if len(s) == 1 else s


def summary(r: pd.DataFrame, rf: float = 0.02) -> pd.DataFrame:
    r = pd.DataFrame(r)
    return pd.DataFrame({
        "Rendement annualisé": annual_return(r),
        "Volatilité annualisée": annual_volatility(r),
        "Sharpe": sharpe(r, rf),
        "Sortino": sortino(r, rf),
        "Drawdown max": max_drawdown(r),
        "VaR 95 % historique": var_historique(r),
        "CVaR 95 %": pd.Series(cvar(r)) if r.shape[1] > 1 else cvar(r),
    })


# Optimisation de portefeuille

def _check(w):
    w = np.clip(w, 0, None)
    return w / w.sum()


def min_variance(r: pd.DataFrame, max_weight: float = 0.35) -> pd.Series:
    cov = r.cov().values * JOURS
    n = cov.shape[0]
    res = minimize(lambda w: w @ cov @ w, np.full(n, 1 / n), method="SLSQP",
                   bounds=[(0, max_weight)] * n, constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}])
    return pd.Series(_check(res.x), index=r.columns)


def max_sharpe(r: pd.DataFrame, rf: float = 0.02, max_weight: float = 0.35) -> pd.Series:
    mu = r.mean().values * JOURS
    cov = r.cov().values * JOURS
    n = len(mu)

    def neg_sharpe(w):
        return -(w @ mu - rf) / np.sqrt(w @ cov @ w)

    res = minimize(neg_sharpe, np.full(n, 1 / n), method="SLSQP", bounds=[(0, max_weight)] * n,
                   constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}])
    return pd.Series(_check(res.x), index=r.columns)


def risk_parity(r: pd.DataFrame) -> pd.Series:
    """Chaque actif contribue autant au risque total du portefeuille."""
    cov = r.cov().values * JOURS
    n = cov.shape[0]

    def objective(w):
        port = np.sqrt(w @ cov @ w)
        contrib = w * (cov @ w) / port
        return ((contrib - port / n) ** 2).sum()

    res = minimize(objective, np.full(n, 1 / n), method="SLSQP", bounds=[(1e-4, 1)] * n,
                   constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}])
    return pd.Series(_check(res.x), index=r.columns)


def efficient_frontier(r: pd.DataFrame, n_portfolios: int = 4000, seed: int = 0) -> pd.DataFrame:
    """Portefeuilles aléatoires pour visualiser la frontière efficiente."""
    rng = np.random.default_rng(seed)
    mu, cov = r.mean().values * JOURS, r.cov().values * JOURS
    w = rng.dirichlet(np.ones(r.shape[1]), n_portfolios)
    ret = w @ mu
    vol = np.sqrt(np.einsum("ij,jk,ik->i", w, cov, w))
    return pd.DataFrame({"rendement": ret, "volatilite": vol, "sharpe": (ret - 0.02) / vol})


# Backtesting

def backtest(r: pd.DataFrame, weight_fn, lookback: int = 252, rebalance: str = "ME",
             cost_bps: float = 10) -> tuple[pd.Series, pd.DataFrame]:
    """Backtest hors échantillon : à chaque date de rebalancement, les poids sont
    calculés uniquement avec les `lookback` jours précédents, puis appliqués
    jusqu'au rebalancement suivant. Des frais de transaction sont déduits.
    """
    dates = r.resample(rebalance).last().index
    weights, rows = None, []
    port = pd.Series(0.0, index=r.index)
    history = {}
    for i, d in enumerate(dates[:-1]):
        past = r.loc[:d].tail(lookback)
        if len(past) < lookback:
            continue
        new_w = weight_fn(past)
        turnover = 0.0 if weights is None else (new_w - weights).abs().sum()
        weights = new_w
        history[d] = weights
        period = r.loc[(r.index > d) & (r.index <= dates[i + 1])]
        if period.empty:
            continue
        drift = (1 + period).cumprod()
        value = (drift * weights).sum(axis=1)
        period_ret = value.pct_change().fillna(value.iloc[0] - 1)
        period_ret.iloc[0] -= turnover * cost_bps / 1e4
        port.loc[period_ret.index] = period_ret.values
        rows.append(d)
    start = rows[0] if rows else r.index[0]
    return port.loc[port.index > start], pd.DataFrame(history).T


def equal_weight(past: pd.DataFrame) -> pd.Series:
    return pd.Series(1 / past.shape[1], index=past.columns)


def momentum(past: pd.DataFrame, top: int = 4) -> pd.Series:
    """Momentum 12 moins 1 mois : on achète les actifs qui ont le plus monté
    sur un an, en excluant le dernier mois (effet de retour à la moyenne)."""
    perf = (1 + past.iloc[:-21]).prod() - 1
    winners = perf.nlargest(top).index
    w = pd.Series(0.0, index=past.columns)
    w[winners] = 1 / top
    return w
