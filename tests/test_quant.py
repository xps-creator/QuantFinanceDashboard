import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import quant as q  # noqa: E402


def fake_returns(n=600, k=4, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=n)
    return pd.DataFrame(rng.normal(0.0005, 0.015, (n, k)), index=idx, columns=list("ABCD"))


def test_drawdown_is_never_positive():
    r = fake_returns()["A"]
    assert (q.drawdown(r) <= 1e-12).all()


def test_cvar_is_worse_than_var():
    r = fake_returns()["A"]
    assert q.cvar(r) >= q.var_historique(r)


def test_optimisers_return_valid_weights():
    r = fake_returns()
    for fn in (q.min_variance, q.max_sharpe, q.risk_parity, q.equal_weight):
        w = fn(r)
        assert np.isclose(w.sum(), 1) and (w >= -1e-9).all()


def test_min_variance_has_lowest_variance():
    r = fake_returns()
    cov = r.cov().values
    w_min, w_eq = q.min_variance(r, max_weight=1).values, q.equal_weight(r).values
    assert w_min @ cov @ w_min <= w_eq @ cov @ w_eq + 1e-12


def test_backtest_uses_only_past_data():
    r = fake_returns()
    port, weights = q.backtest(r, q.equal_weight, lookback=252)
    assert port.index.min() > r.index[251]
    assert np.allclose(weights.sum(axis=1), 1)
