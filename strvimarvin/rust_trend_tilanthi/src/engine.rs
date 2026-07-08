use crate::indicators::{OhlcvBar, SignalPoint};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct ExecutionConfig {
    pub fixed_notional: f64,
    pub entry_mode: EntryMode,
    pub entry_fill_model: EntryFillModel,
    pub entry_atr_multiple: f64,
    pub stop_atr_multiple: f64,
    pub target_atr_multiple: f64,
    pub time_stop_bars: Option<usize>,
    pub entry_order_valid_bars: usize,
    pub fee_rate: f64,
    pub breach_ticks: u32,
    pub symbol_rules: SymbolExecutionRules,
}

impl Default for ExecutionConfig {
    fn default() -> Self {
        Self {
            fixed_notional: 1_000.0,
            entry_mode: EntryMode::Pullback,
            entry_fill_model: EntryFillModel::ImmediateOhlcTouch,
            entry_atr_multiple: 0.5,
            stop_atr_multiple: 2.0,
            target_atr_multiple: 3.0,
            time_stop_bars: Some(24),
            entry_order_valid_bars: 1,
            fee_rate: 0.0,
            breach_ticks: 1,
            symbol_rules: SymbolExecutionRules::synthetic(),
        }
    }
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
pub enum EntryMode {
    #[default]
    Pullback,
    Breakout,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
pub enum EntryFillModel {
    #[default]
    ImmediateOhlcTouch,
    TriggerThenRetrace,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct SymbolExecutionRules {
    pub tick_size: f64,
    pub step_size: f64,
    pub min_qty: f64,
    pub min_notional: f64,
    pub price_precision: u32,
    pub quantity_precision: u32,
}

impl SymbolExecutionRules {
    pub const fn new(
        tick_size: f64,
        step_size: f64,
        min_qty: f64,
        min_notional: f64,
        price_precision: u32,
        quantity_precision: u32,
    ) -> Self {
        Self {
            tick_size,
            step_size,
            min_qty,
            min_notional,
            price_precision,
            quantity_precision,
        }
    }

    pub const fn synthetic() -> Self {
        Self::new(0.00000001, 0.00000001, 0.0, 0.0, 8, 8)
    }

    pub fn for_symbol(symbol: &str) -> Option<Self> {
        match symbol.trim().to_uppercase().as_str() {
            "BTCUSDT" => Some(Self::new(0.10, 0.001, 0.001, 50.0, 2, 3)),
            "ETHUSDT" => Some(Self::new(0.01, 0.001, 0.001, 20.0, 2, 3)),
            "SOLUSDT" => Some(Self::new(0.0100, 0.01, 0.01, 5.0, 4, 2)),
            "XRPUSDT" => Some(Self::new(0.0001, 0.1, 0.1, 5.0, 4, 1)),
            "DOGEUSDT" => Some(Self::new(0.000010, 1.0, 1.0, 5.0, 6, 0)),
            "BNBUSDT" => Some(Self::new(0.010, 0.01, 0.01, 5.0, 3, 2)),
            "SUIUSDT" => Some(Self::new(0.000100, 0.1, 0.1, 5.0, 6, 1)),
            "SYNTHUSDT" => Some(Self::synthetic()),
            _ => None,
        }
    }

    pub fn round_price_floor(self, price: f64) -> f64 {
        round_to_step(
            price,
            self.tick_size,
            self.price_precision,
            RoundMode::Floor,
        )
    }

    pub fn round_price_ceil(self, price: f64) -> f64 {
        round_to_step(price, self.tick_size, self.price_precision, RoundMode::Ceil)
    }

    pub fn round_price_nearest(self, price: f64) -> f64 {
        round_to_step(
            price,
            self.tick_size,
            self.price_precision,
            RoundMode::Nearest,
        )
    }

    pub fn round_quantity_floor(self, quantity: f64) -> f64 {
        round_to_step(
            quantity,
            self.step_size,
            self.quantity_precision,
            RoundMode::Floor,
        )
    }

    pub fn permits_order(self, price: f64, quantity: f64) -> bool {
        price.is_finite()
            && quantity.is_finite()
            && price > 0.0
            && quantity >= self.min_qty
            && price * quantity >= self.min_notional
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum RoundMode {
    Floor,
    Ceil,
    Nearest,
}

fn round_to_step(value: f64, step: f64, precision: u32, mode: RoundMode) -> f64 {
    if !value.is_finite() || !step.is_finite() || step <= 0.0 {
        return value;
    }
    let units = value / step;
    let snapped_units = match mode {
        RoundMode::Floor => units.floor(),
        RoundMode::Ceil => units.ceil(),
        RoundMode::Nearest => units.round(),
    };
    round_decimal(snapped_units * step, precision)
}

fn round_decimal(value: f64, precision: u32) -> f64 {
    let factor = 10_f64.powi(precision.min(12) as i32);
    (value * factor).round() / factor
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TradeSide {
    Long,
    Short,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Trade {
    pub symbol: String,
    pub entry_time_ms: i64,
    pub exit_time_ms: i64,
    pub side: TradeSide,
    pub entry_price: f64,
    pub exit_price: f64,
    pub quantity: f64,
    pub pnl: f64,
    pub return_pct: f64,
    pub exit_reason: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EquitySample {
    pub timestamp_ms: i64,
    pub equity: f64,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct EntryAttempt {
    pub timestamp_ms: i64,
    pub side: TradeSide,
    pub limit_price: f64,
    pub breached: bool,
    pub accepted: bool,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct ExecutionDiagnostics {
    pub entry_attempts: Vec<EntryAttempt>,
}

#[derive(Debug, Clone)]
struct Position {
    side: TradeSide,
    entry_time_ms: i64,
    entry_index: usize,
    entry_price: f64,
    quantity: f64,
    stop: f64,
    target: f64,
}

#[derive(Debug, Clone, Copy)]
struct PendingEntry {
    side: TradeSide,
    created_index: usize,
    limit_price: f64,
    stop: f64,
    target: f64,
    entry_mode: EntryMode,
    trigger_price: f64,
}

pub fn simulate_limit_momentum(
    symbol: &str,
    bars: &[OhlcvBar],
    signals: &[SignalPoint],
    config: ExecutionConfig,
) -> (Vec<Trade>, Vec<EquitySample>) {
    let (trades, equity, _) = simulate_limit_momentum_inner(symbol, bars, signals, config, true);
    (trades, equity)
}

pub fn simulate_limit_momentum_with_diagnostics(
    symbol: &str,
    bars: &[OhlcvBar],
    signals: &[SignalPoint],
    config: ExecutionConfig,
) -> (Vec<Trade>, Vec<EquitySample>, ExecutionDiagnostics) {
    simulate_limit_momentum_inner(symbol, bars, signals, config, true)
}

pub fn simulate_limit_momentum_trades_with_diagnostics(
    symbol: &str,
    bars: &[OhlcvBar],
    signals: &[SignalPoint],
    config: ExecutionConfig,
) -> (Vec<Trade>, ExecutionDiagnostics) {
    let (trades, _, diagnostics) =
        simulate_limit_momentum_inner(symbol, bars, signals, config, false);
    (trades, diagnostics)
}

fn simulate_limit_momentum_inner(
    symbol: &str,
    bars: &[OhlcvBar],
    signals: &[SignalPoint],
    config: ExecutionConfig,
    record_equity: bool,
) -> (Vec<Trade>, Vec<EquitySample>, ExecutionDiagnostics) {
    let len = bars.len().min(signals.len());
    let rules = config.symbol_rules;
    let mut position: Option<Position> = None;
    let mut pending: Option<PendingEntry> = None;
    let mut trades = Vec::new();
    let mut realized = 0.0;
    let mut equity = if record_equity {
        Vec::with_capacity(len)
    } else {
        Vec::new()
    };
    let mut diagnostics = ExecutionDiagnostics::default();

    for i in 1..len {
        let bar = bars[i];
        if let Some(open) = position.take() {
            let (exit_price, reason) = exit_for_bar(
                &open,
                bar,
                i,
                config.time_stop_bars,
                config.breach_ticks,
                rules,
            );
            if let Some((exit_price, reason)) = exit_price.zip(reason) {
                let pnl = pnl(open.side, open.entry_price, exit_price, open.quantity)
                    - (open.entry_price + exit_price) * open.quantity * config.fee_rate;
                realized += pnl;
                trades.push(Trade {
                    symbol: symbol.to_string(),
                    entry_time_ms: open.entry_time_ms,
                    exit_time_ms: bar.open_time_ms,
                    side: open.side,
                    entry_price: open.entry_price,
                    exit_price,
                    quantity: open.quantity,
                    pnl,
                    return_pct: pnl / config.fixed_notional * 100.0,
                    exit_reason: reason.to_string(),
                });
            } else {
                position = Some(open);
            }
        }

        if position.is_none() {
            match config.entry_fill_model {
                EntryFillModel::ImmediateOhlcTouch => {
                    if pending.is_some_and(|order| {
                        i.saturating_sub(order.created_index)
                            >= config.entry_order_valid_bars.max(1)
                    }) {
                        pending = None;
                    }

                    let signal = signals[i - 1];
                    if signal.direction != 0 {
                        let side = if signal.direction > 0 {
                            TradeSide::Long
                        } else {
                            TradeSide::Short
                        };
                        let reference = signal.entry_reference.unwrap_or(bars[i - 1].close);
                        let atr = signal.atr.max(reference * 0.0001);
                        let entry_limit = rounded_trigger_price(
                            config.entry_mode,
                            side,
                            reference,
                            atr,
                            config.entry_atr_multiple,
                            rules,
                        );
                        let (stop, target) = stop_target_for_entry(
                            side,
                            entry_limit,
                            atr,
                            config.stop_atr_multiple,
                            config.target_atr_multiple,
                            rules,
                        );
                        let desired = PendingEntry {
                            side,
                            created_index: i,
                            limit_price: entry_limit,
                            stop,
                            target,
                            entry_mode: config.entry_mode,
                            trigger_price: entry_limit,
                        };
                        if entry_order_price_valid(
                            config.entry_mode,
                            side,
                            entry_limit,
                            bar.open,
                            rules,
                        ) && pending
                            .as_ref()
                            .is_none_or(|existing| !pending_entry_matches(*existing, desired))
                        {
                            pending = Some(desired);
                        }
                    }

                    if let Some(order) = pending {
                        let filled = entry_trigger_hit(
                            config.entry_mode,
                            order.side,
                            bar,
                            order.limit_price,
                            config.breach_ticks,
                            rules,
                        );
                        let mut attempt = EntryAttempt {
                            timestamp_ms: bar.open_time_ms,
                            side: order.side,
                            limit_price: order.limit_price,
                            breached: filled,
                            accepted: false,
                        };
                        if filled {
                            let quantity =
                                rules.round_quantity_floor(config.fixed_notional / order.limit_price);
                            if !rules.permits_order(order.limit_price, quantity) {
                                diagnostics.entry_attempts.push(attempt);
                                continue;
                            }
                            attempt.accepted = true;
                            position = Some(Position {
                                side: order.side,
                                entry_time_ms: bar.open_time_ms,
                                entry_index: i,
                                entry_price: order.limit_price,
                                quantity,
                                stop: order.stop,
                                target: order.target,
                            });
                            pending = None;
                        }
                        diagnostics.entry_attempts.push(attempt);
                    }
                }
                EntryFillModel::TriggerThenRetrace => {
                    if let Some(order) = pending {
                        let age = i.saturating_sub(order.created_index);
                        if age > config.entry_order_valid_bars.max(1) {
                            pending = None;
                        } else if age > 0 {
                            let filled = trigger_retrace_fill_hit(
                                order.entry_mode,
                                order.side,
                                bar,
                                order.limit_price,
                                config.breach_ticks,
                                rules,
                            );
                            let mut attempt = EntryAttempt {
                                timestamp_ms: bar.open_time_ms,
                                side: order.side,
                                limit_price: order.limit_price,
                                breached: filled,
                                accepted: false,
                            };
                            if filled {
                                let quantity = rules
                                    .round_quantity_floor(config.fixed_notional / order.limit_price);
                                if !rules.permits_order(order.limit_price, quantity) {
                                    diagnostics.entry_attempts.push(attempt);
                                    continue;
                                }
                                attempt.accepted = true;
                                position = Some(Position {
                                    side: order.side,
                                    entry_time_ms: bar.open_time_ms,
                                    entry_index: i,
                                    entry_price: order.limit_price,
                                    quantity,
                                    stop: order.stop,
                                    target: order.target,
                                });
                                pending = None;
                            }
                            diagnostics.entry_attempts.push(attempt);
                        }
                    }

                    if position.is_none() && pending.is_none() {
                        let signal = signals[i - 1];
                        if signal.direction != 0 {
                            let side = if signal.direction > 0 {
                                TradeSide::Long
                            } else {
                                TradeSide::Short
                            };
                            let reference = signal.entry_reference.unwrap_or(bars[i - 1].close);
                            let atr = signal.atr.max(reference * 0.0001);
                            let trigger_price = rounded_trigger_price(
                                config.entry_mode,
                                side,
                                reference,
                                atr,
                                config.entry_atr_multiple,
                                rules,
                            );
                            let triggered = entry_order_price_valid(
                                config.entry_mode,
                                side,
                                trigger_price,
                                bar.open,
                                rules,
                            ) && entry_trigger_hit(
                                config.entry_mode,
                                side,
                                bar,
                                trigger_price,
                                config.breach_ticks,
                                rules,
                            );
                            if triggered {
                                let limit_price =
                                    trigger_retrace_limit_price(side, trigger_price, rules);
                                let (stop, target) = stop_target_for_entry(
                                    side,
                                    limit_price,
                                    atr,
                                    config.stop_atr_multiple,
                                    config.target_atr_multiple,
                                    rules,
                                );
                                pending = Some(PendingEntry {
                                    side,
                                    created_index: i,
                                    limit_price,
                                    stop,
                                    target,
                                    entry_mode: config.entry_mode,
                                    trigger_price,
                                });
                            }
                        }
                    }
                }
            }
        }

        if record_equity {
            let mark = position
                .as_ref()
                .map(|p| {
                    pnl(
                        p.side,
                        p.entry_price,
                        rules.round_price_nearest(bar.close),
                        p.quantity,
                    )
                })
                .unwrap_or(0.0);
            equity.push(EquitySample {
                timestamp_ms: bar.open_time_ms,
                equity: realized + mark,
            });
        }
    }
    (trades, equity, diagnostics)
}

fn pending_entry_matches(left: PendingEntry, right: PendingEntry) -> bool {
    left.side == right.side
        && left.limit_price == right.limit_price
        && left.stop == right.stop
        && left.target == right.target
        && left.entry_mode == right.entry_mode
        && left.trigger_price == right.trigger_price
}

fn rounded_trigger_price(
    entry_mode: EntryMode,
    side: TradeSide,
    reference: f64,
    atr: f64,
    entry_atr_multiple: f64,
    rules: SymbolExecutionRules,
) -> f64 {
    let raw_entry_limit = match (entry_mode, side) {
        (EntryMode::Pullback, TradeSide::Long) => reference - entry_atr_multiple * atr,
        (EntryMode::Pullback, TradeSide::Short) => reference + entry_atr_multiple * atr,
        (EntryMode::Breakout, TradeSide::Long) => reference + entry_atr_multiple * atr,
        (EntryMode::Breakout, TradeSide::Short) => reference - entry_atr_multiple * atr,
    };
    match (entry_mode, side) {
        (EntryMode::Pullback, TradeSide::Long) | (EntryMode::Breakout, TradeSide::Short) => {
            rules.round_price_floor(raw_entry_limit)
        }
        (EntryMode::Pullback, TradeSide::Short) | (EntryMode::Breakout, TradeSide::Long) => {
            rules.round_price_ceil(raw_entry_limit)
        }
    }
}

fn trigger_retrace_limit_price(
    side: TradeSide,
    trigger_price: f64,
    rules: SymbolExecutionRules,
) -> f64 {
    match side {
        TradeSide::Long => rules.round_price_ceil(trigger_price + rules.tick_size),
        TradeSide::Short => rules.round_price_floor(trigger_price - rules.tick_size),
    }
}

fn stop_target_for_entry(
    side: TradeSide,
    entry_limit: f64,
    atr: f64,
    stop_atr_multiple: f64,
    target_atr_multiple: f64,
    rules: SymbolExecutionRules,
) -> (f64, f64) {
    let raw_stop = match side {
        TradeSide::Long => entry_limit - stop_atr_multiple * atr,
        TradeSide::Short => entry_limit + stop_atr_multiple * atr,
    };
    let stop = match side {
        TradeSide::Long => rules.round_price_floor(raw_stop),
        TradeSide::Short => rules.round_price_ceil(raw_stop),
    };
    let raw_target = match side {
        TradeSide::Long => entry_limit + target_atr_multiple * atr,
        TradeSide::Short => entry_limit - target_atr_multiple * atr,
    };
    let target = match side {
        TradeSide::Long => rules.round_price_ceil(raw_target),
        TradeSide::Short => rules.round_price_floor(raw_target),
    };
    (stop, target)
}

fn entry_trigger_hit(
    entry_mode: EntryMode,
    side: TradeSide,
    bar: OhlcvBar,
    trigger_price: f64,
    breach_ticks: u32,
    rules: SymbolExecutionRules,
) -> bool {
    match (entry_mode, side) {
        (EntryMode::Pullback, TradeSide::Long) | (EntryMode::Breakout, TradeSide::Short) => {
            breached_below(bar.low, trigger_price, breach_ticks, rules)
        }
        (EntryMode::Pullback, TradeSide::Short) | (EntryMode::Breakout, TradeSide::Long) => {
            breached_above(bar.high, trigger_price, breach_ticks, rules)
        }
    }
}

fn trigger_retrace_fill_hit(
    entry_mode: EntryMode,
    side: TradeSide,
    bar: OhlcvBar,
    fill_price: f64,
    breach_ticks: u32,
    rules: SymbolExecutionRules,
) -> bool {
    match (entry_mode, side) {
        (EntryMode::Breakout, TradeSide::Long) | (EntryMode::Pullback, TradeSide::Short) => {
            breached_below(bar.low, fill_price, breach_ticks, rules)
        }
        (EntryMode::Breakout, TradeSide::Short) | (EntryMode::Pullback, TradeSide::Long) => {
            breached_above(bar.high, fill_price, breach_ticks, rules)
        }
    }
}

fn entry_order_price_valid(
    entry_mode: EntryMode,
    side: TradeSide,
    order_price: f64,
    market_price: f64,
    rules: SymbolExecutionRules,
) -> bool {
    let order_price = rules.round_price_nearest(order_price);
    let market_price = rules.round_price_nearest(market_price);
    match (entry_mode, side) {
        (EntryMode::Pullback, TradeSide::Long) => order_price <= market_price,
        (EntryMode::Pullback, TradeSide::Short) => order_price >= market_price,
        (EntryMode::Breakout, TradeSide::Long) => order_price >= market_price,
        (EntryMode::Breakout, TradeSide::Short) => order_price <= market_price,
    }
}

fn exit_for_bar(
    position: &Position,
    bar: OhlcvBar,
    index: usize,
    time_stop_bars: Option<usize>,
    breach_ticks: u32,
    rules: SymbolExecutionRules,
) -> (Option<f64>, Option<&'static str>) {
    let stop_hit = match position.side {
        TradeSide::Long => breached_below(bar.low, position.stop, breach_ticks, rules),
        TradeSide::Short => breached_above(bar.high, position.stop, breach_ticks, rules),
    };
    let target_hit = match position.side {
        TradeSide::Long => breached_above(bar.high, position.target, breach_ticks, rules),
        TradeSide::Short => breached_below(bar.low, position.target, breach_ticks, rules),
    };
    if stop_hit {
        return (Some(position.stop), Some("stop"));
    }
    if target_hit {
        return (Some(position.target), Some("target"));
    }
    if time_stop_bars.is_some_and(|bars| index.saturating_sub(position.entry_index) >= bars) {
        return (Some(rules.round_price_nearest(bar.close)), Some("time"));
    }
    (None, None)
}

fn breached_below(
    observed_low: f64,
    order_price: f64,
    breach_ticks: u32,
    rules: SymbolExecutionRules,
) -> bool {
    let ticks = f64::from(breach_ticks.max(1));
    observed_low <= rules.round_price_nearest(order_price - rules.tick_size * ticks)
}

fn breached_above(
    observed_high: f64,
    order_price: f64,
    breach_ticks: u32,
    rules: SymbolExecutionRules,
) -> bool {
    let ticks = f64::from(breach_ticks.max(1));
    observed_high >= rules.round_price_nearest(order_price + rules.tick_size * ticks)
}

pub fn pnl(side: TradeSide, entry: f64, exit: f64, quantity: f64) -> f64 {
    match side {
        TradeSide::Long => (exit - entry) * quantity,
        TradeSide::Short => (entry - exit) * quantity,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn bar(i: i64, open: f64, high: f64, low: f64, close: f64) -> OhlcvBar {
        OhlcvBar {
            open_time_ms: i * 60_000,
            open,
            high,
            low,
            close,
            volume: 1.0,
        }
    }

    fn one_decimal_rules() -> SymbolExecutionRules {
        SymbolExecutionRules::new(0.1, 0.1, 0.1, 1.0, 1, 1)
    }

    fn long_signal(timestamp_ms: i64) -> SignalPoint {
        SignalPoint {
            timestamp_ms,
            direction: 1,
            strength: 1.0,
            atr: 1.0,
            entry_reference: None,
        }
    }

    fn flat_signal(timestamp_ms: i64) -> SignalPoint {
        SignalPoint {
            timestamp_ms,
            direction: 0,
            strength: 0.0,
            atr: 1.0,
            entry_reference: None,
        }
    }

    #[test]
    fn entry_touch_does_not_fill_without_one_tick_breach() {
        let bars = vec![
            bar(0, 100.0, 100.0, 100.0, 100.0),
            bar(1, 100.0, 100.4, 100.0, 100.2),
            bar(2, 100.2, 100.4, 100.0, 100.1),
        ];
        let signals = vec![long_signal(0), flat_signal(60_000), flat_signal(120_000)];

        let (trades, _) = simulate_limit_momentum(
            "TESTUSDT",
            &bars,
            &signals,
            ExecutionConfig {
                entry_atr_multiple: 0.0,
                time_stop_bars: Some(1),
                symbol_rules: one_decimal_rules(),
                ..ExecutionConfig::default()
            },
        );

        assert!(trades.is_empty());
    }

    #[test]
    fn entry_one_tick_breach_fills_at_order_price() {
        let bars = vec![
            bar(0, 100.0, 100.0, 100.0, 100.0),
            bar(1, 100.0, 100.4, 99.9, 100.2),
            bar(2, 100.2, 100.4, 100.0, 100.1),
        ];
        let signals = vec![long_signal(0), flat_signal(60_000), flat_signal(120_000)];

        let (trades, _) = simulate_limit_momentum(
            "TESTUSDT",
            &bars,
            &signals,
            ExecutionConfig {
                entry_atr_multiple: 0.0,
                time_stop_bars: Some(1),
                symbol_rules: one_decimal_rules(),
                ..ExecutionConfig::default()
            },
        );

        assert_eq!(trades.len(), 1);
        assert_eq!(trades[0].entry_price, 100.0);
        assert_eq!(trades[0].quantity, 10.0);
    }

    #[test]
    fn breakout_entry_waits_for_one_tick_breach_above_order() {
        let bars = vec![
            bar(0, 100.0, 100.0, 100.0, 100.0),
            bar(1, 100.0, 100.5, 99.8, 100.0),
            bar(2, 100.0, 100.6, 99.9, 100.2),
            bar(3, 100.2, 100.4, 100.0, 100.2),
        ];
        let signals = vec![
            long_signal(0),
            long_signal(60_000),
            flat_signal(120_000),
            flat_signal(180_000),
        ];

        let (trades, _) = simulate_limit_momentum(
            "TESTUSDT",
            &bars,
            &signals,
            ExecutionConfig {
                entry_mode: EntryMode::Breakout,
                entry_atr_multiple: 0.5,
                time_stop_bars: Some(1),
                symbol_rules: one_decimal_rules(),
                ..ExecutionConfig::default()
            },
        );

        assert_eq!(trades.len(), 1);
        assert_eq!(trades[0].entry_time_ms, 120_000);
        assert_eq!(trades[0].entry_price, 100.5);
    }

    #[test]
    fn trigger_then_retrace_breakout_requires_later_reverse_fill() {
        let bars = vec![
            bar(0, 100.0, 100.0, 100.0, 100.0),
            bar(1, 100.0, 100.7, 100.4, 100.6),
            bar(2, 100.6, 100.7, 100.5, 100.6),
            bar(3, 100.6, 102.0, 100.5, 101.0),
        ];
        let signals = vec![
            long_signal(0),
            flat_signal(60_000),
            flat_signal(120_000),
            flat_signal(180_000),
        ];

        let (trades, _) = simulate_limit_momentum(
            "TESTUSDT",
            &bars,
            &signals,
            ExecutionConfig {
                entry_mode: EntryMode::Breakout,
                entry_fill_model: EntryFillModel::TriggerThenRetrace,
                entry_atr_multiple: 0.5,
                target_atr_multiple: 1.0,
                time_stop_bars: None,
                entry_order_valid_bars: 2,
                symbol_rules: one_decimal_rules(),
                ..ExecutionConfig::default()
            },
        );

        assert_eq!(trades.len(), 1);
        assert_eq!(trades[0].entry_time_ms, 120_000);
        assert_eq!(trades[0].entry_price, 100.6);
    }

    #[test]
    fn target_touch_waits_for_one_tick_breach() {
        let bars = vec![
            bar(0, 100.0, 100.0, 100.0, 100.0),
            bar(1, 100.0, 100.1, 99.9, 100.0),
            bar(2, 100.0, 101.0, 99.8, 100.5),
            bar(3, 100.5, 101.1, 100.4, 101.0),
        ];
        let signals = vec![
            long_signal(0),
            flat_signal(60_000),
            flat_signal(120_000),
            flat_signal(180_000),
        ];

        let (trades, _) = simulate_limit_momentum(
            "TESTUSDT",
            &bars,
            &signals,
            ExecutionConfig {
                entry_atr_multiple: 0.0,
                stop_atr_multiple: 10.0,
                target_atr_multiple: 1.0,
                time_stop_bars: None,
                symbol_rules: one_decimal_rules(),
                ..ExecutionConfig::default()
            },
        );

        assert_eq!(trades.len(), 1);
        assert_eq!(trades[0].exit_time_ms, 180_000);
        assert_eq!(trades[0].exit_price, 101.0);
        assert_eq!(trades[0].exit_reason, "target");
    }

    #[test]
    fn stop_touch_waits_for_one_tick_breach() {
        let bars = vec![
            bar(0, 100.0, 100.0, 100.0, 100.0),
            bar(1, 100.0, 100.1, 99.9, 100.0),
            bar(2, 100.0, 100.2, 99.0, 99.5),
            bar(3, 99.5, 99.6, 98.9, 99.0),
        ];
        let signals = vec![
            long_signal(0),
            flat_signal(60_000),
            flat_signal(120_000),
            flat_signal(180_000),
        ];

        let (trades, _) = simulate_limit_momentum(
            "TESTUSDT",
            &bars,
            &signals,
            ExecutionConfig {
                entry_atr_multiple: 0.0,
                stop_atr_multiple: 1.0,
                target_atr_multiple: 10.0,
                time_stop_bars: None,
                symbol_rules: one_decimal_rules(),
                ..ExecutionConfig::default()
            },
        );

        assert_eq!(trades.len(), 1);
        assert_eq!(trades[0].exit_time_ms, 180_000);
        assert_eq!(trades[0].exit_price, 99.0);
        assert_eq!(trades[0].exit_reason, "stop");
    }

    #[test]
    fn one_bar_entry_order_expires_and_replaces() {
        let bars = vec![
            bar(0, 100.0, 100.0, 100.0, 100.0),
            bar(1, 101.0, 101.0, 100.6, 100.8),
            bar(2, 100.8, 100.9, 100.2, 100.4),
            bar(3, 100.4, 103.0, 99.0, 102.0),
        ];
        let signals = vec![
            SignalPoint {
                timestamp_ms: 0,
                direction: 1,
                strength: 1.0,
                atr: 1.0,
                entry_reference: None,
            },
            SignalPoint {
                timestamp_ms: 60_000,
                direction: 1,
                strength: 1.0,
                atr: 1.0,
                entry_reference: None,
            },
            SignalPoint {
                timestamp_ms: 120_000,
                direction: 0,
                strength: 0.0,
                atr: 1.0,
                entry_reference: None,
            },
            SignalPoint {
                timestamp_ms: 180_000,
                direction: 0,
                strength: 0.0,
                atr: 1.0,
                entry_reference: None,
            },
        ];
        let (trades, _) = simulate_limit_momentum(
            "BTCUSDT",
            &bars,
            &signals,
            ExecutionConfig {
                entry_atr_multiple: 0.5,
                stop_atr_multiple: 1.0,
                target_atr_multiple: 1.0,
                time_stop_bars: Some(1),
                ..ExecutionConfig::default()
            },
        );

        assert_eq!(trades.len(), 1);
        assert_eq!(trades[0].entry_time_ms, 120_000);
    }

    #[test]
    fn multi_bar_pending_entry_can_fill_after_first_bar() {
        let bars = vec![
            bar(0, 100.0, 100.0, 100.0, 100.0),
            bar(1, 100.0, 100.2, 99.8, 100.1),
            bar(2, 100.1, 100.2, 99.4, 99.8),
            bar(3, 99.8, 100.0, 99.7, 99.9),
        ];
        let signals = vec![
            SignalPoint {
                timestamp_ms: 0,
                direction: 1,
                strength: 1.0,
                atr: 1.0,
                entry_reference: None,
            },
            SignalPoint {
                timestamp_ms: 60_000,
                direction: 0,
                strength: 0.0,
                atr: 1.0,
                entry_reference: None,
            },
            SignalPoint {
                timestamp_ms: 120_000,
                direction: 0,
                strength: 0.0,
                atr: 1.0,
                entry_reference: None,
            },
            SignalPoint {
                timestamp_ms: 180_000,
                direction: 0,
                strength: 0.0,
                atr: 1.0,
                entry_reference: None,
            },
        ];
        let (trades, _) = simulate_limit_momentum(
            "BTCUSDT",
            &bars,
            &signals,
            ExecutionConfig {
                entry_atr_multiple: 0.5,
                stop_atr_multiple: 1.0,
                target_atr_multiple: 1.0,
                time_stop_bars: Some(1),
                entry_order_valid_bars: 3,
                ..ExecutionConfig::default()
            },
        );

        assert_eq!(trades.len(), 1);
        assert_eq!(trades[0].entry_time_ms, 120_000);
    }

    #[test]
    fn signal_entry_reference_overrides_close_for_limit_price() {
        let bars = vec![
            bar(0, 100.0, 100.0, 100.0, 100.0),
            bar(1, 100.0, 100.1, 98.8, 99.5),
            bar(2, 99.5, 99.8, 99.2, 99.4),
        ];
        let mut signal = long_signal(0);
        signal.entry_reference = Some(99.0);
        let signals = vec![signal, flat_signal(60_000), flat_signal(120_000)];

        let (trades, _) = simulate_limit_momentum(
            "TESTUSDT",
            &bars,
            &signals,
            ExecutionConfig {
                entry_atr_multiple: 0.0,
                time_stop_bars: Some(1),
                symbol_rules: one_decimal_rules(),
                ..ExecutionConfig::default()
            },
        );

        assert_eq!(trades.len(), 1);
        assert_eq!(trades[0].entry_price, 99.0);
    }

    #[test]
    fn invalid_pullback_limit_on_wrong_side_of_market_is_not_placed() {
        let bars = vec![
            bar(0, 100.0, 100.0, 100.0, 100.0),
            bar(1, 100.0, 102.0, 99.0, 101.0),
            bar(2, 101.0, 102.0, 99.0, 100.0),
        ];
        let mut invalid_buy_limit = long_signal(0);
        invalid_buy_limit.entry_reference = Some(101.0);
        let signals = vec![invalid_buy_limit, flat_signal(60_000), flat_signal(120_000)];

        let (trades, _) = simulate_limit_momentum(
            "TESTUSDT",
            &bars,
            &signals,
            ExecutionConfig {
                entry_atr_multiple: 0.0,
                symbol_rules: one_decimal_rules(),
                ..ExecutionConfig::default()
            },
        );

        assert!(trades.is_empty());
    }

    #[test]
    fn repeated_same_signal_does_not_refresh_pending_order_age() {
        let bars = vec![
            bar(0, 100.0, 100.0, 100.0, 100.0),
            bar(1, 100.0, 100.1, 99.0, 99.5),
            bar(2, 99.5, 99.7, 99.0, 99.4),
            bar(3, 99.4, 99.6, 98.8, 99.0),
        ];
        let mut active = long_signal(0);
        active.entry_reference = Some(99.0);
        let mut repeated = long_signal(60_000);
        repeated.entry_reference = Some(99.0);
        let signals = vec![active, repeated, flat_signal(120_000), flat_signal(180_000)];

        let (trades, _) = simulate_limit_momentum(
            "TESTUSDT",
            &bars,
            &signals,
            ExecutionConfig {
                entry_atr_multiple: 0.0,
                entry_order_valid_bars: 2,
                symbol_rules: one_decimal_rules(),
                ..ExecutionConfig::default()
            },
        );

        assert!(trades.is_empty());
    }

    #[test]
    fn stop_wins_same_bar_collision() {
        let bars = vec![
            bar(0, 100.0, 100.0, 100.0, 100.0),
            bar(1, 100.0, 100.0, 99.49, 99.8),
            bar(2, 99.8, 103.0, 98.0, 102.0),
        ];
        let signals = vec![
            SignalPoint {
                timestamp_ms: 0,
                direction: 1,
                strength: 1.0,
                atr: 1.0,
                entry_reference: None,
            },
            SignalPoint {
                timestamp_ms: 60_000,
                direction: 0,
                strength: 0.0,
                atr: 1.0,
                entry_reference: None,
            },
            SignalPoint {
                timestamp_ms: 120_000,
                direction: 0,
                strength: 0.0,
                atr: 1.0,
                entry_reference: None,
            },
        ];
        let (trades, _) = simulate_limit_momentum(
            "BTCUSDT",
            &bars,
            &signals,
            ExecutionConfig {
                entry_atr_multiple: 0.5,
                stop_atr_multiple: 1.0,
                target_atr_multiple: 1.0,
                time_stop_bars: None,
                ..ExecutionConfig::default()
            },
        );

        assert_eq!(trades[0].exit_reason, "stop");
        assert!(trades[0].pnl < 0.0);
    }

    #[test]
    fn fixed_notional_long_and_short_pnl() {
        assert_eq!(pnl(TradeSide::Long, 100.0, 110.0, 10.0), 100.0);
        assert_eq!(pnl(TradeSide::Short, 100.0, 90.0, 10.0), 100.0);
    }

    #[test]
    fn btc_orders_round_price_and_quantity_to_exchange_filters() {
        let bars = vec![
            bar(0, 65_000.0, 65_001.0, 64_999.0, 65_000.07),
            bar(1, 65_000.0, 65_010.0, 64_994.0, 64_999.0),
            bar(2, 64_999.0, 65_004.0, 64_998.0, 65_002.04),
        ];
        let signals = vec![
            SignalPoint {
                timestamp_ms: 0,
                direction: 1,
                strength: 1.0,
                atr: 10.07,
                entry_reference: None,
            },
            SignalPoint {
                timestamp_ms: 60_000,
                direction: 0,
                strength: 0.0,
                atr: 10.07,
                entry_reference: None,
            },
            SignalPoint {
                timestamp_ms: 120_000,
                direction: 0,
                strength: 0.0,
                atr: 10.07,
                entry_reference: None,
            },
        ];

        let (trades, _) = simulate_limit_momentum(
            "BTCUSDT",
            &bars,
            &signals,
            ExecutionConfig {
                entry_atr_multiple: 0.5,
                stop_atr_multiple: 2.0,
                target_atr_multiple: 3.0,
                time_stop_bars: Some(1),
                symbol_rules: SymbolExecutionRules::for_symbol("BTCUSDT").unwrap(),
                ..ExecutionConfig::default()
            },
        );

        assert_eq!(trades.len(), 1);
        assert_eq!(trades[0].entry_price, 64_995.0);
        assert_eq!(trades[0].quantity, 0.015);
        assert_eq!(trades[0].exit_price, 65_002.0);
    }

    #[test]
    fn doge_orders_round_to_integer_quantity_and_price_tick() {
        let bars = vec![
            bar(0, 0.12345, 0.12350, 0.12340, 0.123456),
            bar(1, 0.12345, 0.12360, 0.12343, 0.12350),
            bar(2, 0.12350, 0.12352, 0.12340, 0.123499),
        ];
        let signals = vec![
            SignalPoint {
                timestamp_ms: 0,
                direction: 1,
                strength: 1.0,
                atr: 0.000031,
                entry_reference: None,
            },
            SignalPoint {
                timestamp_ms: 60_000,
                direction: 0,
                strength: 0.0,
                atr: 0.000031,
                entry_reference: None,
            },
            SignalPoint {
                timestamp_ms: 120_000,
                direction: 0,
                strength: 0.0,
                atr: 0.000031,
                entry_reference: None,
            },
        ];

        let (trades, _) = simulate_limit_momentum(
            "DOGEUSDT",
            &bars,
            &signals,
            ExecutionConfig {
                entry_atr_multiple: 0.5,
                stop_atr_multiple: 2.0,
                target_atr_multiple: 3.0,
                time_stop_bars: Some(1),
                symbol_rules: SymbolExecutionRules::for_symbol("DOGEUSDT").unwrap(),
                ..ExecutionConfig::default()
            },
        );

        assert_eq!(trades.len(), 1);
        assert_eq!(trades[0].entry_price, 0.12344);
        assert_eq!(trades[0].quantity, 8101.0);
        assert_eq!(trades[0].exit_price, 0.12350);
    }

    #[test]
    fn min_notional_filter_skips_too_small_rounded_orders() {
        let bars = vec![
            bar(0, 0.12345, 0.12350, 0.12340, 0.123456),
            bar(1, 0.12345, 0.12360, 0.12343, 0.12350),
        ];
        let signals = vec![
            SignalPoint {
                timestamp_ms: 0,
                direction: 1,
                strength: 1.0,
                atr: 0.000031,
                entry_reference: None,
            },
            SignalPoint {
                timestamp_ms: 60_000,
                direction: 0,
                strength: 0.0,
                atr: 0.000031,
                entry_reference: None,
            },
        ];

        let (trades, _) = simulate_limit_momentum(
            "DOGEUSDT",
            &bars,
            &signals,
            ExecutionConfig {
                fixed_notional: 4.0,
                entry_atr_multiple: 0.5,
                symbol_rules: SymbolExecutionRules::for_symbol("DOGEUSDT").unwrap(),
                ..ExecutionConfig::default()
            },
        );

        assert!(trades.is_empty());
    }
}
