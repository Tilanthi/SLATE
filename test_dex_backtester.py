"""Tests for the DEX bar-level backtester (slate_core.dex.backtester.dex_backtester)."""
import pandas as pd

from slate_core.dex.backtester.dex_backtester import (
    DexBacktester, DexBacktestConfig,
)
from slate_core.dex.strategies.action import DexStrategy, Order


def _df(rows):
    idx = pd.date_range("2026-01-01", periods=len(rows), freq="1h")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = 100.0
    return df


class _BuyHold(DexStrategy):
    def __init__(self):
        self.done = False

    def act(self, state):
        if not self.done:
            self.done = True
            return [Order("B", px=0.0, sz=1.0, tif="Market")]
        return []


class _MakerEnter(DexStrategy):
    def act(self, state):
        if state.i == 0:
            return [Order("B", px=state.open - 0.5, sz=1.0, tif="Limit")]
        return []


class _TooBig(DexStrategy):
    def act(self, state):
        return [Order("B", px=0.0, sz=1000.0, tif="Market")]


def test_buy_hold_pnl_and_taker_fee():
    df = _df([(100, 100, 100, 100), (100, 105, 105, 105), (105, 110, 110, 110)])
    r = DexBacktester(DexBacktestConfig(warmup=0, funding_interval_bars=0)).backtest(_BuyHold(), df)
    # 1 SOL bought @ open 100 + 1bps slippage = 100.01 (taker); close 110
    # PnL = (110 - 100.01) - 100.01*0.00045 ≈ 9.945
    assert abs(r.total_pnl - 9.945) < 0.01
    assert r.taker_fills == 1 and r.maker_fills == 0 and r.maker_fraction == 0.0


def test_maker_fill_costs_less_than_taker():
    # 2 bars: decide at bar0 (limit 99.5), fill at bar1 (low 99 touches the bid)
    df = _df([(100, 101, 99, 100.5), (100, 101, 99, 100.5)])
    r = DexBacktester(DexBacktestConfig(warmup=0, funding_interval_bars=0)).backtest(_MakerEnter(), df)
    assert r.maker_fills == 1 and r.taker_fills == 0 and r.maker_fraction == 1.0
    assert abs(r.total_fees - 99.5 * 0.00015) < 1e-6      # < taker 0.045


def test_leverage_cap_rejects_oversized_orders():
    df = _df([(100, 100, 100, 100), (100, 100, 100, 100)])
    r = DexBacktester(DexBacktestConfig(warmup=0, funding_interval_bars=0)).backtest(_TooBig(), df)
    assert r.total_trades == 0
    assert r.rejections.get("capped", 0) >= 1


def test_rebate_earns_cash_when_maker_rate_negative():
    df = _df([(100, 101, 99, 100.5), (100, 101, 99, 100.5)])
    from slate_core.dex.backtester.economics import HLFeeSchedule
    cfg = DexBacktestConfig(warmup=0, funding_interval_bars=0,
                            fee_schedule=HLFeeSchedule(maker=-0.0001))
    r = DexBacktester(cfg).backtest(_MakerEnter(), df)
    assert r.maker_fills == 1
    assert r.total_rebates > 0 and r.total_fees == 0.0     # maker <0 => pure rebate


class _MakerBuy(DexStrategy):
    def act(self, state):
        if state.i < 2:
            return [Order("B", px=state.close * 0.99, sz=1, tif="Alo")]
        return []


def test_l2_provider_blocks_maker_fills_vs_bar_proxy():
    """With an L2 provider returning a huge queue, maker fills are blocked
    (definitive); without it, the bar proxy fills them (indicative)."""
    df = _df([(100, 101, 99, 100.5)] * 4)
    r_proxy = DexBacktester(DexBacktestConfig(warmup=0, funding_interval_bars=0)).backtest(_MakerBuy(), df)
    r_l2 = DexBacktester(DexBacktestConfig(warmup=0, funding_interval_bars=0,
                                           l2_provider=lambda side, px: 1e9)).backtest(_MakerBuy(), df)
    assert r_proxy.total_trades > 0          # proxy: touched = filled
    assert r_l2.total_trades == 0            # definitive: queue never consumed


def test_backtester_uses_per_bar_funding_column():
    """P2: a long held across funding events pays the per-bar funding rate."""
    import pandas as pd
    n = 20
    idx = pd.date_range("2026-01-01", periods=n, freq="1h")
    df = pd.DataFrame({"open": [100.0] * n, "high": [100.0] * n, "low": [100.0] * n,
                       "close": [100.0] * n, "volume": [100.0] * n,
                       "funding": [0.001] * n}, index=idx)
    r = DexBacktester(DexBacktestConfig(warmup=0, funding_interval_bars=8)).backtest(_BuyHold(), df)
    assert r.total_funding > 0              # longs paid positive funding across events
