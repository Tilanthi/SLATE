use crate::data::binance_um::{Candle1m, MS_PER_MINUTE};
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Timeframe {
    M1,
    M3,
    M5,
    M15,
    M30,
    H1,
}

impl Timeframe {
    pub const ALL: [Self; 6] = [Self::M1, Self::M3, Self::M5, Self::M15, Self::M30, Self::H1];

    pub fn minutes(self) -> i64 {
        match self {
            Self::M1 => 1,
            Self::M3 => 3,
            Self::M5 => 5,
            Self::M15 => 15,
            Self::M30 => 30,
            Self::H1 => 60,
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::M1 => "1m",
            Self::M3 => "3m",
            Self::M5 => "5m",
            Self::M15 => "15m",
            Self::M30 => "30m",
            Self::H1 => "1h",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum IndicatorKind {
    EhlersDecycler,
    SuperSmoother,
    EhlersRoofing,
    CyberCycle,
    CenterOfGravity,
    EvenBetterSineWave,
    InverseFisherTransform,
    ElegantOscillator,
    TrendFlex,
    Reflex,
    MamaFama,
    Alma,
    Kama,
    Frama,
    TillsonT3,
    ZeroLagHaTema,
    Vidya,
    McGinleyDynamic,
    ConnorsRsi,
    LaguerreRsi,
    SchaffTrendCycle,
    RelativeVigorIndex,
    Vortex,
    StochasticMomentumIndex,
    Roc,
    Cmo,
    DonchianBreakout,
    VolatilityAdjustedMomentum,
    Strategy336KamaTpo,
    Strategy3635KamaTpo,
    Strategy3938KamaTpo,
    Strategy4448KamaKer,
    HurstGate,
    ShannonGate,
    Vpin,
    KalmanSpread,
    Emd,
    AlphaRnn,
    NotApplicableV1,
}

impl IndicatorKind {
    pub const IMPLEMENTED_DIRECT_OHLC: [Self; 32] = [
        Self::EhlersDecycler,
        Self::SuperSmoother,
        Self::EhlersRoofing,
        Self::CyberCycle,
        Self::CenterOfGravity,
        Self::EvenBetterSineWave,
        Self::InverseFisherTransform,
        Self::ElegantOscillator,
        Self::TrendFlex,
        Self::Reflex,
        Self::MamaFama,
        Self::Alma,
        Self::Kama,
        Self::Frama,
        Self::TillsonT3,
        Self::ZeroLagHaTema,
        Self::Vidya,
        Self::McGinleyDynamic,
        Self::ConnorsRsi,
        Self::LaguerreRsi,
        Self::SchaffTrendCycle,
        Self::RelativeVigorIndex,
        Self::Vortex,
        Self::StochasticMomentumIndex,
        Self::Roc,
        Self::Cmo,
        Self::DonchianBreakout,
        Self::VolatilityAdjustedMomentum,
        Self::Strategy336KamaTpo,
        Self::Strategy3635KamaTpo,
        Self::Strategy3938KamaTpo,
        Self::Strategy4448KamaKer,
    ];

    pub const CATALOG: [Self; 38] = [
        Self::EhlersDecycler,
        Self::SuperSmoother,
        Self::EhlersRoofing,
        Self::CyberCycle,
        Self::CenterOfGravity,
        Self::EvenBetterSineWave,
        Self::InverseFisherTransform,
        Self::ElegantOscillator,
        Self::TrendFlex,
        Self::Reflex,
        Self::MamaFama,
        Self::Alma,
        Self::Kama,
        Self::Frama,
        Self::TillsonT3,
        Self::ZeroLagHaTema,
        Self::Vidya,
        Self::McGinleyDynamic,
        Self::ConnorsRsi,
        Self::LaguerreRsi,
        Self::SchaffTrendCycle,
        Self::RelativeVigorIndex,
        Self::Vortex,
        Self::StochasticMomentumIndex,
        Self::Roc,
        Self::Cmo,
        Self::DonchianBreakout,
        Self::VolatilityAdjustedMomentum,
        Self::Strategy336KamaTpo,
        Self::Strategy3635KamaTpo,
        Self::Strategy3938KamaTpo,
        Self::Strategy4448KamaKer,
        Self::HurstGate,
        Self::ShannonGate,
        Self::Vpin,
        Self::KalmanSpread,
        Self::Emd,
        Self::AlphaRnn,
    ];

    pub const REGIME_GATES: [Self; 2] = [Self::HurstGate, Self::ShannonGate];
    pub const NOT_APPLICABLE_V1: [Self; 4] =
        [Self::Vpin, Self::KalmanSpread, Self::Emd, Self::AlphaRnn];

    pub fn as_str(self) -> &'static str {
        match self {
            Self::EhlersDecycler => "ehlers_decycler",
            Self::SuperSmoother => "super_smoother",
            Self::EhlersRoofing => "ehlers_roofing",
            Self::CyberCycle => "cyber_cycle",
            Self::CenterOfGravity => "center_of_gravity",
            Self::EvenBetterSineWave => "even_better_sinewave",
            Self::InverseFisherTransform => "inverse_fisher_transform",
            Self::ElegantOscillator => "elegant_oscillator",
            Self::TrendFlex => "trendflex",
            Self::Reflex => "reflex",
            Self::MamaFama => "mama_fama",
            Self::Alma => "alma",
            Self::Kama => "kama",
            Self::Frama => "frama",
            Self::TillsonT3 => "tillson_t3",
            Self::ZeroLagHaTema => "zero_lag_ha_tema",
            Self::Vidya => "vidya",
            Self::McGinleyDynamic => "mcginley_dynamic",
            Self::ConnorsRsi => "connors_rsi",
            Self::LaguerreRsi => "laguerre_rsi",
            Self::SchaffTrendCycle => "schaff_trend_cycle",
            Self::RelativeVigorIndex => "relative_vigor_index",
            Self::Vortex => "vortex",
            Self::StochasticMomentumIndex => "stochastic_momentum_index",
            Self::Roc => "roc",
            Self::Cmo => "cmo",
            Self::DonchianBreakout => "donchian_breakout",
            Self::VolatilityAdjustedMomentum => "volatility_adjusted_momentum",
            Self::Strategy336KamaTpo => "strategy_336_kama_tpo",
            Self::Strategy3635KamaTpo => "strategy_3635_kama_tpo",
            Self::Strategy3938KamaTpo => "strategy_3938_kama_tpo",
            Self::Strategy4448KamaKer => "strategy_4448_kama_ker",
            Self::HurstGate => "hurst_gate",
            Self::ShannonGate => "shannon_gate",
            Self::Vpin => "vpin",
            Self::KalmanSpread => "kalman_spread",
            Self::Emd => "emd",
            Self::AlphaRnn => "alpha_rnn",
            Self::NotApplicableV1 => "not_applicable_v1",
        }
    }

    pub fn family(self) -> &'static str {
        match self {
            Self::EhlersDecycler
            | Self::SuperSmoother
            | Self::EhlersRoofing
            | Self::CyberCycle
            | Self::CenterOfGravity
            | Self::EvenBetterSineWave
            | Self::InverseFisherTransform
            | Self::ElegantOscillator
            | Self::TrendFlex
            | Self::Reflex
            | Self::MamaFama => "ehlers_dsp",
            Self::Alma
            | Self::Kama
            | Self::Frama
            | Self::TillsonT3
            | Self::ZeroLagHaTema
            | Self::Vidya
            | Self::McGinleyDynamic => "adaptive_ma",
            Self::ConnorsRsi
            | Self::LaguerreRsi
            | Self::SchaffTrendCycle
            | Self::RelativeVigorIndex
            | Self::Vortex
            | Self::StochasticMomentumIndex
            | Self::Roc
            | Self::Cmo
            | Self::DonchianBreakout
            | Self::VolatilityAdjustedMomentum => "momentum",
            Self::Strategy336KamaTpo
            | Self::Strategy3635KamaTpo
            | Self::Strategy3938KamaTpo
            | Self::Strategy4448KamaKer => "strategy_quant_pattern",
            Self::HurstGate | Self::ShannonGate => "regime_gate",
            Self::Vpin
            | Self::KalmanSpread
            | Self::Emd
            | Self::AlphaRnn
            | Self::NotApplicableV1 => "not_applicable_v1",
        }
    }

    pub fn implementation_status(self) -> &'static str {
        if Self::IMPLEMENTED_DIRECT_OHLC.contains(&self) {
            "implemented"
        } else if Self::REGIME_GATES.contains(&self) {
            "regime_gate"
        } else {
            "not_applicable_v1"
        }
    }

    pub fn implementation_note(self) -> &'static str {
        match self {
            Self::HurstGate => "sweepable R/S persistence gate; not scored as standalone entry",
            Self::ShannonGate => {
                "sweepable normalized return-entropy gate; not scored as standalone entry"
            }
            Self::Vpin => "deferred: needs signed flow or tick/volume-bucket data",
            Self::KalmanSpread => "deferred: pair/spread strategy module is not in v1",
            Self::Emd => "deferred: feature pipeline decomposition is not in v1",
            Self::AlphaRnn => "deferred: ML benchmark harness is not in v1",
            Self::Strategy336KamaTpo => {
                "Strategy 3.3.36-style KAMA cross with previous-day TPO value-area and PSAR filter"
            }
            Self::Strategy3635KamaTpo => {
                "Strategy 3.6.35-style KAMA cross with previous-day TPO value-area and PSAR filter"
            }
            Self::Strategy3938KamaTpo => {
                "Strategy 3.9.38-style weighted-price KAMA cross with previous-day TPO value-area and PSAR filter"
            }
            Self::Strategy4448KamaKer => {
                "Strategy 4.4.48-style KAMA stretch plus Kaufman ER slope with KAMA limit entry"
            }
            _ => "direct OHLC long/short directional momentum signal",
        }
    }

    pub fn is_runnable_strategy(self) -> bool {
        Self::IMPLEMENTED_DIRECT_OHLC.contains(&self)
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct OhlcvBar {
    pub open_time_ms: i64,
    pub open: f64,
    pub high: f64,
    pub low: f64,
    pub close: f64,
    pub volume: f64,
}

impl From<&Candle1m> for OhlcvBar {
    fn from(value: &Candle1m) -> Self {
        Self {
            open_time_ms: value.open_time_ms,
            open: value.open,
            high: value.high,
            low: value.low,
            close: value.close,
            volume: value.volume_base,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct SignalPoint {
    pub timestamp_ms: i64,
    pub direction: i8,
    pub strength: f64,
    pub atr: f64,
    pub entry_reference: Option<f64>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Strategy4448KamaKerParams {
    pub kama1_er: usize,
    pub kama1_short: usize,
    pub kama1_long: usize,
    pub ker_period: usize,
    pub kama2_er: usize,
    pub kama2_short: usize,
    pub kama2_long: usize,
    pub count_bars: usize,
    pub atr_period: usize,
}

impl Default for Strategy4448KamaKerParams {
    fn default() -> Self {
        Self {
            kama1_er: 30,
            kama1_short: 45,
            kama1_long: 19,
            ker_period: 47,
            kama2_er: 37,
            kama2_short: 46,
            kama2_long: 15,
            count_bars: 9,
            atr_period: 80,
        }
    }
}

pub fn resample_ohlcv(rows: &[OhlcvBar], timeframe: Timeframe) -> Vec<OhlcvBar> {
    let bucket_ms = timeframe.minutes() * MS_PER_MINUTE;
    if bucket_ms == MS_PER_MINUTE {
        return rows.to_vec();
    }
    let mut out = Vec::new();
    let mut current: Option<OhlcvBar> = None;
    let mut current_bucket = 0;
    for row in rows {
        let bucket = row.open_time_ms.div_euclid(bucket_ms) * bucket_ms;
        match current.as_mut() {
            Some(bar) if bucket == current_bucket => {
                bar.high = bar.high.max(row.high);
                bar.low = bar.low.min(row.low);
                bar.close = row.close;
                bar.volume += row.volume;
            }
            Some(_) => {
                out.push(current.take().expect("current bar"));
                current_bucket = bucket;
                current = Some(*row);
                current.as_mut().expect("new bar").open_time_ms = bucket;
            }
            None => {
                current_bucket = bucket;
                current = Some(*row);
                current.as_mut().expect("new bar").open_time_ms = bucket;
            }
        }
    }
    if let Some(bar) = current {
        out.push(bar);
    }
    out
}

pub fn atr(rows: &[OhlcvBar], period: usize) -> Vec<f64> {
    let mut out = vec![0.0; rows.len()];
    let mut sum = 0.0;
    for i in 0..rows.len() {
        let prev_close = i
            .checked_sub(1)
            .map(|idx| rows[idx].close)
            .unwrap_or(rows[i].open);
        let tr = (rows[i].high - rows[i].low)
            .max((rows[i].high - prev_close).abs())
            .max((rows[i].low - prev_close).abs());
        sum += tr;
        if i >= period {
            let old_prev_close = if i == period {
                rows[0].open
            } else {
                rows[i - period - 1].close
            };
            let old = (rows[i - period].high - rows[i - period].low)
                .max((rows[i - period].high - old_prev_close).abs())
                .max((rows[i - period].low - old_prev_close).abs());
            sum -= old;
        }
        out[i] = sum / period.min(i + 1) as f64;
    }
    out
}

pub fn momentum_signals(
    rows: &[OhlcvBar],
    kind: IndicatorKind,
    lookback: usize,
    atr_period: usize,
) -> Vec<SignalPoint> {
    let lookback = lookback.max(2);
    if matches!(
        kind,
        IndicatorKind::Strategy336KamaTpo
            | IndicatorKind::Strategy3635KamaTpo
            | IndicatorKind::Strategy3938KamaTpo
    ) {
        return strategy_kama_tpo_signals(rows, kind, lookback, atr_period);
    }
    if kind == IndicatorKind::Strategy4448KamaKer {
        let params = Strategy4448KamaKerParams {
            ker_period: lookback,
            atr_period,
            ..Strategy4448KamaKerParams::default()
        };
        return strategy_4448_kama_ker_signals(rows, params);
    }
    let atr_values = atr(rows, atr_period.max(1));
    let deltas = indicator_delta_series(rows, kind, lookback, &atr_values);
    rows.iter()
        .enumerate()
        .map(|(i, row)| {
            let delta = deltas.get(i).copied().unwrap_or(0.0);
            let threshold =
                direction_threshold(kind, row.close, atr_values[i], &deltas, i, lookback);
            let direction = if i < lookback || !delta.is_finite() {
                0
            } else if delta > threshold {
                1
            } else if delta < -threshold {
                -1
            } else {
                0
            };
            SignalPoint {
                timestamp_ms: row.open_time_ms,
                direction,
                strength: normalized_strength(delta, row.close, atr_values[i]),
                atr: atr_values[i],
                entry_reference: None,
            }
        })
        .collect()
}

fn direction_threshold(
    kind: IndicatorKind,
    price: f64,
    atr: f64,
    deltas: &[f64],
    index: usize,
    lookback: usize,
) -> f64 {
    if atr.abs() <= price.abs().max(1.0) * 1e-12 {
        return f64::INFINITY;
    }
    let price_threshold = atr.abs().max(price.abs() * 0.0001) * 0.05;
    match kind {
        IndicatorKind::Roc
        | IndicatorKind::Cmo
        | IndicatorKind::VolatilityAdjustedMomentum
        | IndicatorKind::ConnorsRsi
        | IndicatorKind::LaguerreRsi
        | IndicatorKind::SchaffTrendCycle
        | IndicatorKind::StochasticMomentumIndex
        | IndicatorKind::RelativeVigorIndex
        | IndicatorKind::Vortex
        | IndicatorKind::CenterOfGravity
        | IndicatorKind::EvenBetterSineWave
        | IndicatorKind::InverseFisherTransform
        | IndicatorKind::ElegantOscillator
        | IndicatorKind::TrendFlex
        | IndicatorKind::Reflex => {
            let sigma = rolling_delta_sigma(deltas, index, lookback);
            if !sigma.is_finite() {
                sigma
            } else {
                sigma * normalized_threshold_multiplier(kind)
            }
        }
        IndicatorKind::DonchianBreakout => 0.0,
        IndicatorKind::EhlersRoofing | IndicatorKind::CyberCycle => price_threshold,
        IndicatorKind::EhlersDecycler
        | IndicatorKind::SuperSmoother
        | IndicatorKind::MamaFama
        | IndicatorKind::Alma
        | IndicatorKind::Kama
        | IndicatorKind::Frama
        | IndicatorKind::TillsonT3
        | IndicatorKind::ZeroLagHaTema
        | IndicatorKind::Vidya
        | IndicatorKind::McGinleyDynamic => price_threshold,
        IndicatorKind::HurstGate
        | IndicatorKind::ShannonGate
        | IndicatorKind::Vpin
        | IndicatorKind::KalmanSpread
        | IndicatorKind::Emd
        | IndicatorKind::AlphaRnn
        | IndicatorKind::Strategy4448KamaKer
        | IndicatorKind::NotApplicableV1 => f64::INFINITY,
        IndicatorKind::Strategy336KamaTpo
        | IndicatorKind::Strategy3635KamaTpo
        | IndicatorKind::Strategy3938KamaTpo => 0.0,
    }
}

fn rolling_delta_sigma(deltas: &[f64], index: usize, lookback: usize) -> f64 {
    if index == 0 {
        return f64::INFINITY;
    }
    let start = index.saturating_sub(lookback.max(2));
    let window = &deltas[start..index];
    let valid = window
        .iter()
        .copied()
        .filter(|value| value.is_finite())
        .collect::<Vec<_>>();
    if valid.len() < 2 {
        return f64::INFINITY;
    }
    let mean = valid.iter().sum::<f64>() / valid.len() as f64;
    let variance = valid
        .iter()
        .map(|value| {
            let diff = value - mean;
            diff * diff
        })
        .sum::<f64>()
        / valid.len() as f64;
    variance.sqrt().max(1e-8)
}

fn normalized_threshold_multiplier(kind: IndicatorKind) -> f64 {
    match kind {
        IndicatorKind::Roc => 0.20,
        IndicatorKind::Cmo => 2.00,
        IndicatorKind::VolatilityAdjustedMomentum => 2.00,
        IndicatorKind::ConnorsRsi
        | IndicatorKind::LaguerreRsi
        | IndicatorKind::SchaffTrendCycle
        | IndicatorKind::StochasticMomentumIndex => 0.35,
        IndicatorKind::RelativeVigorIndex => 0.02,
        IndicatorKind::Vortex => 0.10,
        IndicatorKind::CenterOfGravity
        | IndicatorKind::EvenBetterSineWave
        | IndicatorKind::InverseFisherTransform
        | IndicatorKind::ElegantOscillator
        | IndicatorKind::TrendFlex
        | IndicatorKind::Reflex => 0.25,
        _ => 0.25,
    }
}

pub fn hurst_proxy(rows: &[OhlcvBar], lookback: usize) -> Vec<f64> {
    hurst_exponent(rows, lookback)
}

pub fn shannon_entropy_proxy(rows: &[OhlcvBar], lookback: usize) -> Vec<f64> {
    shannon_entropy(rows, lookback)
}

pub fn hurst_exponent(rows: &[OhlcvBar], lookback: usize) -> Vec<f64> {
    let lookback = lookback.max(8);
    let mut out = vec![0.5; rows.len()];
    for (i, slot) in out.iter_mut().enumerate().skip(lookback) {
        let start = i + 1 - lookback;
        let returns = (start + 1..=i)
            .map(|idx| rows[idx].close - rows[idx - 1].close)
            .collect::<Vec<_>>();
        if returns.is_empty() {
            continue;
        }
        let mean = returns.iter().sum::<f64>() / returns.len() as f64;
        let variance = returns
            .iter()
            .map(|value| (value - mean).powi(2))
            .sum::<f64>()
            / returns.len() as f64;
        if variance <= 1e-18 {
            *slot = if mean.abs() > 1e-12 { 1.0 } else { 0.5 };
            continue;
        }
        let std = variance.sqrt();
        let mut cumulative = 0.0;
        let mut min_cumulative = 0.0;
        let mut max_cumulative = 0.0;
        for value in returns {
            cumulative += value - mean;
            min_cumulative = f64::min(min_cumulative, cumulative);
            max_cumulative = f64::max(max_cumulative, cumulative);
        }
        let range = max_cumulative - min_cumulative;
        let rs = (range / std).max(1e-12);
        *slot = (rs.ln() / (lookback as f64).ln()).clamp(0.0, 1.0);
    }
    out
}

pub fn shannon_entropy(rows: &[OhlcvBar], lookback: usize) -> Vec<f64> {
    let lookback = lookback.max(8);
    let mut out = vec![0.0; rows.len()];
    for (i, slot) in out.iter_mut().enumerate().skip(lookback) {
        let start = i + 1 - lookback;
        let returns = (start + 1..=i)
            .map(|idx| rows[idx].close - rows[idx - 1].close)
            .collect::<Vec<_>>();
        if returns.is_empty() {
            continue;
        }
        let mean = returns.iter().sum::<f64>() / returns.len() as f64;
        let variance = returns
            .iter()
            .map(|value| (value - mean).powi(2))
            .sum::<f64>()
            / returns.len() as f64;
        let scale = variance.sqrt().max(1e-12);
        let mut bins = [0usize; 5];
        for value in returns {
            let z = (value - mean) / scale;
            let idx = if z < -1.0 {
                0
            } else if z < -0.25 {
                1
            } else if z <= 0.25 {
                2
            } else if z <= 1.0 {
                3
            } else {
                4
            };
            bins[idx] += 1;
        }
        let total = bins.iter().sum::<usize>() as f64;
        let entropy = bins
            .iter()
            .filter(|count| **count > 0)
            .map(|count| {
                let p = *count as f64 / total;
                -p * p.ln()
            })
            .sum::<f64>();
        *slot = (entropy / (bins.len() as f64).ln()).clamp(0.0, 1.0);
    }
    out
}

fn indicator_delta_series(
    rows: &[OhlcvBar],
    kind: IndicatorKind,
    lookback: usize,
    atr_values: &[f64],
) -> Vec<f64> {
    let close = rows.iter().map(|row| row.close).collect::<Vec<_>>();
    let median = rows
        .iter()
        .map(|row| (row.high + row.low) * 0.5)
        .collect::<Vec<_>>();
    match kind {
        IndicatorKind::EhlersDecycler => {
            let high_passed = high_pass(&median, lookback);
            let decycler = subtract(&median, &high_passed);
            slope(&decycler)
        }
        IndicatorKind::SuperSmoother => slope(&super_smoother(&close, lookback)),
        IndicatorKind::EhlersRoofing => super_smoother(&high_pass(&median, lookback * 3), lookback),
        IndicatorKind::CyberCycle => cyber_cycle(&median, lookback),
        IndicatorKind::CenterOfGravity => center_of_gravity(&close, lookback),
        IndicatorKind::EvenBetterSineWave => {
            let roofed = super_smoother(&high_pass(&median, lookback * 3), lookback);
            rms_normalize(&roofed, lookback)
        }
        IndicatorKind::InverseFisherTransform => {
            let cmo = cmo_series(&close, lookback);
            cmo.into_iter()
                .map(|value| inverse_fisher(value.clamp(-0.999, 0.999)))
                .collect()
        }
        IndicatorKind::ElegantOscillator => {
            let raw = normalized_momentum(&close, lookback);
            raw.into_iter()
                .map(|value| inverse_fisher(value.clamp(-0.999, 0.999)))
                .collect()
        }
        IndicatorKind::TrendFlex => trendflex(&close, lookback),
        IndicatorKind::Reflex => reflex(&close, lookback),
        IndicatorKind::MamaFama => {
            let (mama, fama) = mama_fama(&close, lookback);
            subtract(&mama, &fama)
        }
        IndicatorKind::Alma => subtract(&close, &alma(&close, lookback)),
        IndicatorKind::Kama => subtract(&close, &kama(&close, lookback)),
        IndicatorKind::Frama => subtract(&close, &frama(rows, lookback)),
        IndicatorKind::TillsonT3 => slope(&tillson_t3(&close, lookback)),
        IndicatorKind::ZeroLagHaTema => {
            let ha_close = rows
                .iter()
                .map(|row| (row.open + row.high + row.low + row.close) * 0.25)
                .collect::<Vec<_>>();
            slope(&zero_lag(&tema(&ha_close, lookback), lookback / 2))
        }
        IndicatorKind::Vidya => subtract(&close, &vidya(&close, lookback)),
        IndicatorKind::McGinleyDynamic => subtract(&close, &mcginley_dynamic(&close, lookback)),
        IndicatorKind::ConnorsRsi => connors_rsi(&close, lookback)
            .into_iter()
            .map(|value| (value - 50.0) / 50.0)
            .collect(),
        IndicatorKind::LaguerreRsi => laguerre_rsi(&close, lookback)
            .into_iter()
            .map(|value| (value - 0.5) * 2.0)
            .collect(),
        IndicatorKind::SchaffTrendCycle => schaff_trend_cycle(&close, lookback)
            .into_iter()
            .map(|value| (value - 50.0) / 50.0)
            .collect(),
        IndicatorKind::RelativeVigorIndex => relative_vigor_index(rows, lookback),
        IndicatorKind::Vortex => vortex(rows, lookback),
        IndicatorKind::StochasticMomentumIndex => stochastic_momentum_index(rows, lookback),
        IndicatorKind::Roc => roc(&close, lookback),
        IndicatorKind::Cmo => cmo_series(&close, lookback),
        IndicatorKind::DonchianBreakout => donchian_breakout(rows, lookback),
        IndicatorKind::VolatilityAdjustedMomentum => close
            .iter()
            .enumerate()
            .map(|(i, value)| {
                if i < lookback {
                    0.0
                } else {
                    (value - close[i - lookback]) / atr_values[i].max(1e-9)
                }
            })
            .collect(),
        IndicatorKind::Strategy336KamaTpo
        | IndicatorKind::Strategy3635KamaTpo
        | IndicatorKind::Strategy3938KamaTpo
        | IndicatorKind::Strategy4448KamaKer => {
            vec![0.0; rows.len()]
        }
        IndicatorKind::HurstGate
        | IndicatorKind::ShannonGate
        | IndicatorKind::Vpin
        | IndicatorKind::KalmanSpread
        | IndicatorKind::Emd
        | IndicatorKind::AlphaRnn
        | IndicatorKind::NotApplicableV1 => vec![0.0; rows.len()],
    }
}

fn strategy_kama_tpo_signals(
    rows: &[OhlcvBar],
    kind: IndicatorKind,
    lookback: usize,
    atr_period: usize,
) -> Vec<SignalPoint> {
    if rows.is_empty() {
        return Vec::new();
    }
    let period = lookback.max(3);
    let close = rows.iter().map(|row| row.close).collect::<Vec<_>>();
    let weighted = rows
        .iter()
        .map(|row| (row.high + row.low + 2.0 * row.close) * 0.25)
        .collect::<Vec<_>>();
    let context_price = if kind == IndicatorKind::Strategy3938KamaTpo {
        &weighted
    } else {
        &close
    };
    let atr_values = atr(rows, atr_period.max(1));
    let context_ema_ratio = if kind == IndicatorKind::Strategy3938KamaTpo {
        37.0 / 40.0
    } else {
        45.0 / 40.0
    };
    let lowest_context = rolling_extreme(context_price, period, RollingExtreme::Min);
    let highest_context = rolling_extreme(context_price, period, RollingExtreme::Max);
    let lowest_context_ema = ema(
        &lowest_context,
        ((period as f64) * context_ema_ratio).round() as usize,
    );
    let highest_context_ema = ema(
        &highest_context,
        ((period as f64) * context_ema_ratio).round() as usize,
    );
    let (er_ratio, short_ratio, long_ratio) = match kind {
        IndicatorKind::Strategy3635KamaTpo | IndicatorKind::Strategy3938KamaTpo => {
            (23.0 / 40.0, 45.0 / 40.0, 11.0 / 40.0)
        }
        _ => (13.0 / 40.0, 44.0 / 40.0, 11.0 / 40.0),
    };
    let kama_line = kama_with_periods(
        &close,
        ((period as f64) * er_ratio).round().max(2.0) as usize,
        ((period as f64) * short_ratio).round().max(2.0) as usize,
        ((period as f64) * long_ratio).round().max(3.0) as usize,
    );
    let psar_step = if kind == IndicatorKind::Strategy3938KamaTpo {
        0.020
    } else {
        0.327
    };
    let psar = parabolic_sar(rows, psar_step, 0.85);
    let previous_day_val = previous_day_tpo_value_area_low(rows, 70, 0.70);
    let warmup = period
        .max(atr_period)
        .max(((period as f64) * 1.125).round() as usize)
        .max(3);

    rows.iter()
        .enumerate()
        .map(|(i, row)| {
            let mut direction = 0;
            if i >= warmup
                && close[i].is_finite()
                && kama_line[i].is_finite()
                && psar[i].is_finite()
            {
                let tpo_filter_available = previous_day_val[i].is_finite();
                let tpo_allows_long = !tpo_filter_available || previous_day_val[i] <= psar[i];
                let tpo_allows_short = !tpo_filter_available || previous_day_val[i] >= psar[i];
                let crosses_above_kama =
                    close[i - 1] <= kama_line[i - 1] && close[i] > kama_line[i];
                let crosses_below_kama =
                    close[i - 1] >= kama_line[i - 1] && close[i] < kama_line[i];
                let long_signal = lowest_context[i] < lowest_context_ema[i]
                    && tpo_allows_long
                    && crosses_above_kama;
                let short_signal = highest_context[i] > highest_context_ema[i]
                    && tpo_allows_short
                    && crosses_below_kama;
                direction = if long_signal {
                    1
                } else if short_signal {
                    -1
                } else {
                    0
                };
            }
            let scale = atr_values[i].abs().max(row.close.abs() * 0.0001).max(1e-9);
            SignalPoint {
                timestamp_ms: row.open_time_ms,
                direction,
                strength: ((close[i] - kama_line[i]).abs() / scale).min(1.0),
                atr: atr_values[i],
                entry_reference: None,
            }
        })
        .collect()
}

pub fn strategy_4448_kama_ker_signals(
    rows: &[OhlcvBar],
    params: Strategy4448KamaKerParams,
) -> Vec<SignalPoint> {
    if rows.is_empty() {
        return Vec::new();
    }
    let kama1_er = params.kama1_er.max(2);
    let kama1_short = params.kama1_short.max(1);
    let kama1_long = params.kama1_long.max(1);
    let ker_period = params.ker_period.max(2);
    let kama2_er = params.kama2_er.max(2);
    let kama2_short = params.kama2_short.max(1);
    let kama2_long = params.kama2_long.max(1);
    let count_bars = params.count_bars.max(1);
    let atr_period = params.atr_period.max(1);

    let close = rows.iter().map(|row| row.close).collect::<Vec<_>>();
    let kama_1 = kama_with_periods(&close, kama1_er, kama1_short, kama1_long);
    let kama_2 = kama_with_periods(&close, kama2_er, kama2_short, kama2_long);
    let er = efficiency_ratio(&close, ker_period);
    let atr_values = atr(rows, atr_period);
    let warmup = atr_period.max(ker_period).max(kama2_er).max(count_bars + 2);

    rows.iter()
        .enumerate()
        .map(|(i, row)| {
            let mut direction = 0;
            let mut strength = 0.0;
            if i >= warmup && i > count_bars {
                // The generated MQ5 wraps "Low[1]"/"KAMA[1]" in a helper that adds one
                // more shift, so the count tests use shifts 2..10 at the bar-open decision.
                // The generated helper also normalizes price comparisons to a fixed 5
                // decimals; we intentionally keep native precision here so the imported
                // strategy remains cross-market scale invariant for BTC through DOGE.
                let count_anchor = i - 1;
                let long_count = (0..count_bars).all(|offset| {
                    let idx = count_anchor - offset;
                    rows[idx].low < kama_1[idx]
                });
                let short_count = (0..count_bars).all(|offset| {
                    let idx = count_anchor - offset;
                    rows[idx].high > kama_1[idx]
                });
                let er_now = normalize_mq5_6(er[count_anchor] + 0.0000000001);
                let er_prev = normalize_mq5_6(er[count_anchor - 1] + 0.0000000001);
                let er_falling = er_now < er_prev && !mq5_doubles_equal(er_now, er_prev);
                let er_rising = er_now > er_prev && !mq5_doubles_equal(er_now, er_prev);
                let long_signal = long_count && er_falling;
                let short_signal = short_count && er_rising;
                direction = if long_signal {
                    1
                } else if short_signal {
                    -1
                } else {
                    0
                };
                let scale = atr_values[i].abs().max(row.close.abs() * 0.0001).max(1e-9);
                strength = ((row.close - kama_1[i]).abs() / scale).min(1.0);
            }
            SignalPoint {
                timestamp_ms: row.open_time_ms,
                direction,
                strength,
                atr: atr_values[i],
                entry_reference: kama_2.get(i).copied().filter(|value| value.is_finite()),
            }
        })
        .collect()
}

fn normalize_mq5_6(value: f64) -> f64 {
    (value * 1_000_000.0).round() / 1_000_000.0
}

fn mq5_doubles_equal(left: f64, right: f64) -> bool {
    (left - right).abs() < 0.00000001
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum RollingExtreme {
    Min,
    Max,
}

fn rolling_extreme(values: &[f64], period: usize, extreme: RollingExtreme) -> Vec<f64> {
    let period = period.max(1);
    let mut out = vec![0.0; values.len()];
    let mut deque: VecDeque<usize> = VecDeque::new();
    for i in 0..values.len() {
        while deque.front().is_some_and(|front| *front + period <= i) {
            deque.pop_front();
        }
        while deque.back().is_some_and(|back| match extreme {
            RollingExtreme::Min => values[*back] >= values[i],
            RollingExtreme::Max => values[*back] <= values[i],
        }) {
            deque.pop_back();
        }
        deque.push_back(i);
        out[i] = deque
            .front()
            .map(|front| values[*front])
            .unwrap_or(values[i]);
    }
    out
}

fn kama_with_periods(
    values: &[f64],
    er_period: usize,
    short_period: usize,
    long_period: usize,
) -> Vec<f64> {
    if values.is_empty() {
        return Vec::new();
    }
    let er = efficiency_ratio(values, er_period.max(2));
    let short = 2.0 / (short_period.max(1) as f64 + 1.0);
    let long = 2.0 / (long_period.max(1) as f64 + 1.0);
    let mut out = vec![values[0]; values.len()];
    for i in 1..values.len() {
        let smoothing = (er[i] * (short - long) + long).powi(2);
        out[i] = out[i - 1] + smoothing * (values[i] - out[i - 1]);
    }
    out
}

fn parabolic_sar(rows: &[OhlcvBar], step: f64, max_step: f64) -> Vec<f64> {
    if rows.is_empty() {
        return Vec::new();
    }
    let step = step.clamp(0.001, max_step.max(0.001));
    let max_step = max_step.max(step);
    let mut out = vec![rows[0].low; rows.len()];
    if rows.len() == 1 {
        return out;
    }
    let mut rising = rows[1].close >= rows[0].close;
    let mut sar = if rising { rows[0].low } else { rows[0].high };
    let mut ep = if rising { rows[0].high } else { rows[0].low };
    let mut af = step;
    for i in 1..rows.len() {
        sar += af * (ep - sar);
        if rising {
            sar = sar.min(rows[i - 1].low);
            if i >= 2 {
                sar = sar.min(rows[i - 2].low);
            }
            if rows[i].low < sar {
                rising = false;
                sar = ep;
                ep = rows[i].low;
                af = step;
            } else if rows[i].high > ep {
                ep = rows[i].high;
                af = (af + step).min(max_step);
            }
        } else {
            sar = sar.max(rows[i - 1].high);
            if i >= 2 {
                sar = sar.max(rows[i - 2].high);
            }
            if rows[i].high > sar {
                rising = true;
                sar = ep;
                ep = rows[i].high;
                af = step;
            } else if rows[i].low < ep {
                ep = rows[i].low;
                af = (af + step).min(max_step);
            }
        }
        out[i] = sar;
    }
    out
}

fn previous_day_tpo_value_area_low(
    rows: &[OhlcvBar],
    bins: usize,
    value_area_fraction: f64,
) -> Vec<f64> {
    const DAY_MS: i64 = 24 * 60 * MS_PER_MINUTE;
    let mut out = vec![f64::NAN; rows.len()];
    if rows.is_empty() {
        return out;
    }
    let mut day_start = 0usize;
    let mut current_day = rows[0].open_time_ms.div_euclid(DAY_MS);
    let mut previous_val = f64::NAN;
    for i in 0..=rows.len() {
        let day_changed = i == rows.len() || rows[i].open_time_ms.div_euclid(DAY_MS) != current_day;
        if !day_changed {
            continue;
        }
        for slot in &mut out[day_start..i] {
            *slot = previous_val;
        }
        previous_val = tpo_value_area_low(&rows[day_start..i], bins, value_area_fraction);
        if i < rows.len() {
            day_start = i;
            current_day = rows[i].open_time_ms.div_euclid(DAY_MS);
        }
    }
    out
}

fn tpo_value_area_low(rows: &[OhlcvBar], bins: usize, value_area_fraction: f64) -> f64 {
    let bins = bins.clamp(8, 512);
    if rows.is_empty() {
        return f64::NAN;
    }
    let low = rows.iter().map(|row| row.low).fold(f64::INFINITY, f64::min);
    let high = rows
        .iter()
        .map(|row| row.high)
        .fold(f64::NEG_INFINITY, f64::max);
    if !low.is_finite() || !high.is_finite() || high <= low {
        return rows.last().map(|row| row.close).unwrap_or(f64::NAN);
    }
    let step = (high - low) / bins as f64;
    let mut counts = vec![0usize; bins];
    for row in rows {
        let typical_price = (row.high + row.low + row.close) / 3.0;
        let idx =
            (((typical_price - low) / step).floor() as isize).clamp(0, bins as isize - 1) as usize;
        counts[idx] += 1;
    }
    let total = counts.iter().sum::<usize>();
    if total == 0 {
        return rows.last().map(|row| row.close).unwrap_or(f64::NAN);
    }
    let poc = counts
        .iter()
        .enumerate()
        .max_by_key(|(_, count)| **count)
        .map(|(idx, _)| idx)
        .unwrap_or(0);
    let target = ((total as f64) * value_area_fraction.clamp(0.1, 1.0)).ceil() as usize;
    let mut lower = poc;
    let mut upper = poc;
    let mut covered = counts[poc];
    while covered < target && (lower > 0 || upper + 1 < counts.len()) {
        let left = lower.checked_sub(1).map(|idx| counts[idx]).unwrap_or(0);
        let right = counts.get(upper + 1).copied().unwrap_or(0);
        if right >= left && upper + 1 < counts.len() {
            upper += 1;
            covered += counts[upper];
        } else if lower > 0 {
            lower -= 1;
            covered += counts[lower];
        } else {
            upper += 1;
            covered += counts[upper];
        }
    }
    low + lower as f64 * step
}

fn normalized_strength(delta: f64, price: f64, atr: f64) -> f64 {
    if !delta.is_finite() {
        return 0.0;
    }
    let scale = atr.abs().max(price.abs() * 0.0001).max(1e-9);
    (delta.abs() / scale).min(1.0)
}

fn subtract(left: &[f64], right: &[f64]) -> Vec<f64> {
    left.iter()
        .zip(right.iter())
        .map(|(left, right)| left - right)
        .collect()
}

fn slope(values: &[f64]) -> Vec<f64> {
    let mut out = vec![0.0; values.len()];
    for i in 1..values.len() {
        out[i] = values[i] - values[i - 1];
    }
    out
}

fn ema(values: &[f64], period: usize) -> Vec<f64> {
    if values.is_empty() {
        return Vec::new();
    }
    let alpha = 2.0 / (period.max(1) as f64 + 1.0);
    let mut out = vec![values[0]; values.len()];
    for i in 1..values.len() {
        out[i] = alpha * values[i] + (1.0 - alpha) * out[i - 1];
    }
    out
}

fn super_smoother(values: &[f64], period: usize) -> Vec<f64> {
    if values.len() < 3 {
        return values.to_vec();
    }
    let period = period.max(3) as f64;
    let a1 = (-std::f64::consts::SQRT_2 * std::f64::consts::PI / period).exp();
    let b1 = 2.0 * a1 * (std::f64::consts::SQRT_2 * std::f64::consts::PI / period).cos();
    let c2 = b1;
    let c3 = -a1 * a1;
    let c1 = 1.0 - c2 - c3;
    let mut out = vec![values[0]; values.len()];
    out[1] = values[1];
    for i in 2..values.len() {
        out[i] = c1 * (values[i] + values[i - 1]) * 0.5 + c2 * out[i - 1] + c3 * out[i - 2];
    }
    out
}

fn high_pass(values: &[f64], period: usize) -> Vec<f64> {
    if values.len() < 3 {
        return vec![0.0; values.len()];
    }
    let period = period.max(3) as f64;
    let alpha = (std::f64::consts::SQRT_2 * std::f64::consts::PI / period).cos()
        + (std::f64::consts::SQRT_2 * std::f64::consts::PI / period).sin()
        - 1.0;
    let mut out = vec![0.0; values.len()];
    for i in 2..values.len() {
        out[i] = (1.0 - alpha / 2.0).powi(2) * (values[i] - 2.0 * values[i - 1] + values[i - 2])
            + 2.0 * (1.0 - alpha) * out[i - 1]
            - (1.0 - alpha).powi(2) * out[i - 2];
    }
    out
}

fn cyber_cycle(values: &[f64], period: usize) -> Vec<f64> {
    if values.len() < 3 {
        return vec![0.0; values.len()];
    }
    let alpha = 2.0 / (period.max(3) as f64 + 1.0);
    let mut out = vec![0.0; values.len()];
    for i in 2..values.len() {
        out[i] = (1.0 - 0.5 * alpha).powi(2) * (values[i] - 2.0 * values[i - 1] + values[i - 2])
            + 2.0 * (1.0 - alpha) * out[i - 1]
            - (1.0 - alpha).powi(2) * out[i - 2];
    }
    out
}

fn center_of_gravity(values: &[f64], period: usize) -> Vec<f64> {
    let period = period.max(2);
    let midpoint = (period as f64 + 1.0) * 0.5;
    let mut out = vec![0.0; values.len()];
    for i in period..values.len() {
        let mut weighted = 0.0;
        let mut total = 0.0;
        for offset in 0..period {
            let value = values[i - offset].max(1e-12);
            weighted += (offset + 1) as f64 * value;
            total += value;
        }
        if total > 0.0 {
            out[i] = midpoint - weighted / total;
        }
    }
    out
}

fn rms_normalize(values: &[f64], period: usize) -> Vec<f64> {
    let period = period.max(2);
    let mut out = vec![0.0; values.len()];
    for i in period..values.len() {
        let rms = (i + 1 - period..=i)
            .map(|idx| values[idx].powi(2))
            .sum::<f64>()
            / period as f64;
        let rms = rms.sqrt();
        out[i] = values[i] / rms.max(1e-9);
    }
    out
}

fn normalized_momentum(values: &[f64], period: usize) -> Vec<f64> {
    let period = period.max(2);
    let mut out = vec![0.0; values.len()];
    for i in period..values.len() {
        let momentum = values[i] - values[i - period];
        let rms = (i + 1 - period..=i)
            .map(|idx| (values[idx] - values[idx - 1]).powi(2))
            .sum::<f64>()
            / period as f64;
        out[i] = momentum / rms.sqrt().max(1e-9);
    }
    out
}

fn inverse_fisher(value: f64) -> f64 {
    let scaled = 2.0 * value;
    (scaled.exp() - 1.0) / (scaled.exp() + 1.0)
}

fn trendflex(values: &[f64], period: usize) -> Vec<f64> {
    let smooth = super_smoother(values, period);
    normalized_momentum(&smooth, period)
}

fn reflex(values: &[f64], period: usize) -> Vec<f64> {
    let smooth = super_smoother(values, period);
    let deviation = subtract(values, &smooth);
    rms_normalize(&deviation, period)
}

fn mama_fama(values: &[f64], period: usize) -> (Vec<f64>, Vec<f64>) {
    if values.is_empty() {
        return (Vec::new(), Vec::new());
    }
    let er = efficiency_ratio(values, period);
    let mut mama = vec![values[0]; values.len()];
    let mut fama = vec![values[0]; values.len()];
    for i in 1..values.len() {
        let alpha = (0.05 + 0.45 * er[i]).clamp(0.05, 0.5);
        mama[i] = alpha * values[i] + (1.0 - alpha) * mama[i - 1];
        fama[i] = 0.5 * alpha * mama[i] + (1.0 - 0.5 * alpha) * fama[i - 1];
    }
    (mama, fama)
}

fn alma(values: &[f64], period: usize) -> Vec<f64> {
    let period = period.max(2);
    let offset = 0.85;
    let sigma = 6.0;
    let m = offset * (period - 1) as f64;
    let s = period as f64 / sigma;
    let weights = (0..period)
        .map(|idx| (-((idx as f64 - m).powi(2)) / (2.0 * s.powi(2))).exp())
        .collect::<Vec<_>>();
    let weight_sum = weights.iter().sum::<f64>().max(1e-12);
    let mut out = values.to_vec();
    for i in period - 1..values.len() {
        out[i] = (0..period)
            .map(|offset| values[i + 1 - period + offset] * weights[offset])
            .sum::<f64>()
            / weight_sum;
    }
    out
}

fn kama(values: &[f64], period: usize) -> Vec<f64> {
    if values.is_empty() {
        return Vec::new();
    }
    let er = efficiency_ratio(values, period);
    let fast = 2.0 / (2.0 + 1.0);
    let slow = 2.0 / (30.0 + 1.0);
    let mut out = vec![values[0]; values.len()];
    for i in 1..values.len() {
        let smoothing = (er[i] * (fast - slow) + slow).powi(2);
        out[i] = out[i - 1] + smoothing * (values[i] - out[i - 1]);
    }
    out
}

fn efficiency_ratio(values: &[f64], period: usize) -> Vec<f64> {
    let period = period.max(2);
    let mut out = vec![0.0; values.len()];
    for i in period..values.len() {
        let change = (values[i] - values[i - period]).abs();
        let volatility = (i + 1 - period..=i)
            .map(|idx| (values[idx] - values[idx - 1]).abs())
            .sum::<f64>();
        out[i] = if volatility > 0.0 {
            change / volatility
        } else {
            0.0
        };
    }
    out
}

fn frama(rows: &[OhlcvBar], period: usize) -> Vec<f64> {
    if rows.is_empty() {
        return Vec::new();
    }
    let period = period.max(4);
    let half = period / 2;
    let mut out = vec![rows[0].close; rows.len()];
    for i in 1..rows.len() {
        if i < period {
            out[i] = rows[i].close;
            continue;
        }
        let range = |start: usize, end: usize| -> f64 {
            let high = rows[start..=end]
                .iter()
                .map(|row| row.high)
                .fold(f64::NEG_INFINITY, f64::max);
            let low = rows[start..=end]
                .iter()
                .map(|row| row.low)
                .fold(f64::INFINITY, f64::min);
            (high - low).max(1e-12)
        };
        let n1 = range(i + 1 - period, i - half) / half as f64;
        let n2 = range(i + 1 - half, i) / half as f64;
        let n3 = range(i + 1 - period, i) / period as f64;
        let dimension = ((n1 + n2) / n3).max(1e-12).ln() / 2.0_f64.ln();
        let alpha = (-4.6 * (dimension - 1.0)).exp().clamp(0.01, 1.0);
        out[i] = alpha * rows[i].close + (1.0 - alpha) * out[i - 1];
    }
    out
}

fn tillson_t3(values: &[f64], period: usize) -> Vec<f64> {
    let e1 = ema(values, period);
    let e2 = ema(&e1, period);
    let e3 = ema(&e2, period);
    let e4 = ema(&e3, period);
    let e5 = ema(&e4, period);
    let e6 = ema(&e5, period);
    let v = 0.7;
    let c1 = -v * v * v;
    let c2 = 3.0 * v * v + 3.0 * v * v * v;
    let c3 = -6.0 * v * v - 3.0 * v - 3.0 * v * v * v;
    let c4 = 1.0 + 3.0 * v + v * v * v + 3.0 * v * v;
    (0..values.len())
        .map(|i| c1 * e6[i] + c2 * e5[i] + c3 * e4[i] + c4 * e3[i])
        .collect()
}

fn tema(values: &[f64], period: usize) -> Vec<f64> {
    let e1 = ema(values, period);
    let e2 = ema(&e1, period);
    let e3 = ema(&e2, period);
    (0..values.len())
        .map(|i| 3.0 * e1[i] - 3.0 * e2[i] + e3[i])
        .collect()
}

fn zero_lag(values: &[f64], lag: usize) -> Vec<f64> {
    let lag = lag.max(1);
    let mut out = values.to_vec();
    for i in lag..values.len() {
        out[i] = values[i] + (values[i] - values[i - lag]);
    }
    out
}

fn vidya(values: &[f64], period: usize) -> Vec<f64> {
    if values.is_empty() {
        return Vec::new();
    }
    let cmo = cmo_series(values, period);
    let base_alpha = 2.0 / (period.max(1) as f64 + 1.0);
    let mut out = vec![values[0]; values.len()];
    for i in 1..values.len() {
        let alpha = base_alpha * cmo[i].abs().clamp(0.0, 1.0);
        out[i] = alpha * values[i] + (1.0 - alpha) * out[i - 1];
    }
    out
}

fn mcginley_dynamic(values: &[f64], period: usize) -> Vec<f64> {
    if values.is_empty() {
        return Vec::new();
    }
    let mut out = vec![values[0]; values.len()];
    for i in 1..values.len() {
        let ratio = (values[i] / out[i - 1].max(1e-12)).clamp(0.2, 5.0);
        out[i] = out[i - 1] + (values[i] - out[i - 1]) / (period.max(1) as f64 * ratio.powi(4));
    }
    out
}

fn connors_rsi(values: &[f64], period: usize) -> Vec<f64> {
    let rsi_price = rsi(values, 3);
    let mut streak = vec![0.0_f64; values.len()];
    for i in 1..values.len() {
        streak[i] = if values[i] > values[i - 1] {
            streak[i - 1].max(0.0) + 1.0
        } else if values[i] < values[i - 1] {
            streak[i - 1].min(0.0) - 1.0
        } else {
            0.0
        };
    }
    let rsi_streak = rsi(&streak, 2);
    let rank = percent_rank_return(values, period.max(5));
    (0..values.len())
        .map(|i| (rsi_price[i] + rsi_streak[i] + rank[i]) / 3.0)
        .collect()
}

fn rsi(values: &[f64], period: usize) -> Vec<f64> {
    let period = period.max(1);
    let mut out = vec![50.0; values.len()];
    for (i, slot) in out.iter_mut().enumerate().skip(period) {
        let mut gains = 0.0;
        let mut losses = 0.0;
        for idx in i + 1 - period..=i {
            let change = values[idx] - values[idx - 1];
            if change >= 0.0 {
                gains += change;
            } else {
                losses -= change;
            }
        }
        *slot = if gains + losses == 0.0 {
            50.0
        } else {
            100.0 * gains / (gains + losses)
        };
    }
    out
}

fn percent_rank_return(values: &[f64], period: usize) -> Vec<f64> {
    let period = period.max(2);
    let mut out = vec![50.0; values.len()];
    for i in period..values.len() {
        let current = values[i] - values[i - 1];
        let mut min_change = f64::INFINITY;
        let mut max_change = f64::NEG_INFINITY;
        for idx in i + 1 - period..=i {
            let change = values[idx] - values[idx - 1];
            min_change = f64::min(min_change, change);
            max_change = f64::max(max_change, change);
        }
        if max_change - min_change <= 1e-12 {
            out[i] = 50.0;
            continue;
        }
        let below = (i + 1 - period..=i)
            .filter(|idx| values[*idx] - values[*idx - 1] <= current)
            .count();
        out[i] = 100.0 * below as f64 / period as f64;
    }
    out
}

fn laguerre_rsi(values: &[f64], period: usize) -> Vec<f64> {
    let gamma = (1.0 - 2.0 / (period.max(4) as f64 + 1.0)).clamp(0.2, 0.9);
    let mut out = vec![0.5; values.len()];
    let first = values.first().copied().unwrap_or(0.0);
    let mut l0 = first;
    let mut l1 = first;
    let mut l2 = first;
    let mut l3 = first;
    for (i, value) in values.iter().enumerate() {
        let old_l0 = l0;
        let old_l1 = l1;
        let old_l2 = l2;
        l0 = (1.0 - gamma) * value + gamma * old_l0;
        l1 = -gamma * l0 + old_l0 + gamma * old_l1;
        l2 = -gamma * l1 + old_l1 + gamma * old_l2;
        l3 = -gamma * l2 + old_l2 + gamma * l3;
        let pairs = [(l0, l1), (l1, l2), (l2, l3)];
        let cu = pairs
            .iter()
            .filter(|(a, b)| a >= b)
            .map(|(a, b)| a - b)
            .sum::<f64>();
        let cd = pairs
            .iter()
            .filter(|(a, b)| a < b)
            .map(|(a, b)| b - a)
            .sum::<f64>();
        out[i] = if cu + cd > 0.0 { cu / (cu + cd) } else { 0.5 };
    }
    out
}

fn schaff_trend_cycle(values: &[f64], period: usize) -> Vec<f64> {
    let fast = ema(values, (period / 2).max(3));
    let slow = ema(values, period.max(6));
    let macd = subtract(&fast, &slow);
    let stochastic = rolling_stochastic(&macd, period);
    ema(&ema(&stochastic, 3), 3)
}

fn rolling_stochastic(values: &[f64], period: usize) -> Vec<f64> {
    let period = period.max(2);
    let mut out = vec![50.0; values.len()];
    for i in period..values.len() {
        let window = &values[i + 1 - period..=i];
        let min = window.iter().copied().fold(f64::INFINITY, f64::min);
        let max = window.iter().copied().fold(f64::NEG_INFINITY, f64::max);
        out[i] = if max > min {
            100.0 * (values[i] - min) / (max - min)
        } else {
            50.0
        };
    }
    out
}

fn relative_vigor_index(rows: &[OhlcvBar], period: usize) -> Vec<f64> {
    let period = period.max(2);
    let mut raw = vec![0.0; rows.len()];
    for (i, row) in rows.iter().enumerate() {
        raw[i] = (row.close - row.open) / (row.high - row.low).abs().max(1e-9);
    }
    ema(&raw, period)
}

fn vortex(rows: &[OhlcvBar], period: usize) -> Vec<f64> {
    let period = period.max(2);
    let mut out = vec![0.0; rows.len()];
    for (i, slot) in out.iter_mut().enumerate().skip(period) {
        let mut plus = 0.0;
        let mut minus = 0.0;
        let mut tr = 0.0;
        for idx in i + 1 - period..=i {
            let prev = rows[idx - 1];
            let row = rows[idx];
            plus += (row.high - prev.low).abs();
            minus += (row.low - prev.high).abs();
            tr += (row.high - row.low)
                .max((row.high - prev.close).abs())
                .max((row.low - prev.close).abs());
        }
        *slot = (plus - minus) / tr.max(1e-9);
    }
    out
}

fn stochastic_momentum_index(rows: &[OhlcvBar], period: usize) -> Vec<f64> {
    let period = period.max(2);
    let mut raw = vec![0.0; rows.len()];
    for i in period..rows.len() {
        let window = &rows[i + 1 - period..=i];
        let high = window
            .iter()
            .map(|row| row.high)
            .fold(f64::NEG_INFINITY, f64::max);
        let low = window
            .iter()
            .map(|row| row.low)
            .fold(f64::INFINITY, f64::min);
        let midpoint = (high + low) * 0.5;
        raw[i] = (rows[i].close - midpoint) / ((high - low) * 0.5).max(1e-9);
    }
    ema(&ema(&raw, 3), 3)
}

fn roc(values: &[f64], period: usize) -> Vec<f64> {
    let period = period.max(1);
    let mut out = vec![0.0; values.len()];
    for (i, slot) in out.iter_mut().enumerate().skip(period) {
        *slot = (values[i] / values[i - period].max(1e-12)) - 1.0;
    }
    out
}

fn cmo_series(values: &[f64], period: usize) -> Vec<f64> {
    let period = period.max(1);
    let mut out = vec![0.0; values.len()];
    for (i, slot) in out.iter_mut().enumerate().skip(period) {
        let mut up = 0.0;
        let mut down = 0.0;
        for j in i + 1 - period..=i {
            let change = values[j] - values[j - 1];
            if change >= 0.0 {
                up += change;
            } else {
                down -= change;
            }
        }
        *slot = if up + down == 0.0 {
            0.0
        } else {
            (up - down) / (up + down)
        };
    }
    out
}

fn donchian_breakout(rows: &[OhlcvBar], period: usize) -> Vec<f64> {
    let period = period.max(2);
    let mut out = vec![0.0; rows.len()];
    for i in period..rows.len() {
        let window = &rows[i - period..i];
        let high = window
            .iter()
            .map(|row| row.high)
            .fold(f64::NEG_INFINITY, f64::max);
        let low = window
            .iter()
            .map(|row| row.low)
            .fold(f64::INFINITY, f64::min);
        out[i] = if rows[i].close > high {
            rows[i].close - high
        } else if rows[i].close < low {
            rows[i].close - low
        } else {
            0.0
        };
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn bar(i: i64, close: f64) -> OhlcvBar {
        OhlcvBar {
            open_time_ms: i * MS_PER_MINUTE,
            open: close - 0.1,
            high: close + 0.5,
            low: close - 0.5,
            close,
            volume: 1.0,
        }
    }

    fn scale_rows(rows: &[OhlcvBar], scale: f64) -> Vec<OhlcvBar> {
        rows.iter()
            .map(|row| OhlcvBar {
                open_time_ms: row.open_time_ms,
                open: row.open * scale,
                high: row.high * scale,
                low: row.low * scale,
                close: row.close * scale,
                volume: row.volume,
            })
            .collect()
    }

    #[test]
    fn resamples_to_three_minute_ohlcv() {
        let rows: Vec<_> = (0..4)
            .map(|i| OhlcvBar {
                open_time_ms: i * MS_PER_MINUTE,
                open: 10.0 + i as f64,
                high: 11.0 + i as f64,
                low: 9.0 + i as f64,
                close: 10.5 + i as f64,
                volume: 1.0,
            })
            .collect();

        let out = resample_ohlcv(&rows, Timeframe::M3);

        assert_eq!(out.len(), 2);
        assert_eq!(out[0].open, 10.0);
        assert_eq!(out[0].high, 13.0);
        assert_eq!(out[0].low, 9.0);
        assert_eq!(out[0].close, 12.5);
        assert_eq!(out[0].volume, 3.0);
    }

    #[test]
    fn every_runnable_indicator_emits_distinct_real_signal_path() {
        let rows = (0..240)
            .map(|i| {
                let t = i as f64;
                bar(i, 100.0 + t * 0.05 + (t / 4.0).sin() * 3.5)
            })
            .collect::<Vec<_>>();

        for kind in IndicatorKind::IMPLEMENTED_DIRECT_OHLC {
            let signals = momentum_signals(&rows, kind, 12, 14);
            assert_eq!(signals.len(), rows.len());
            assert!(
                signals.iter().any(|signal| signal.direction != 0),
                "{} produced no directional signals",
                kind.as_str()
            );
        }
    }

    #[test]
    fn raw_ehlers_filters_are_price_scale_invariant() {
        let rows = (0..160)
            .map(|i| {
                let base = 100.0 + i as f64 * 0.05 + (i as f64 / 3.0).sin() * 1.6;
                bar(i, base)
            })
            .collect::<Vec<_>>();
        let scaled = scale_rows(&rows, 0.001);

        for kind in [IndicatorKind::EhlersRoofing, IndicatorKind::CyberCycle] {
            let normal = momentum_signals(&rows, kind, 12, 14)
                .into_iter()
                .map(|signal| signal.direction)
                .collect::<Vec<_>>();
            let low_decimal = momentum_signals(&scaled, kind, 12, 14)
                .into_iter()
                .map(|signal| signal.direction)
                .collect::<Vec<_>>();

            assert_eq!(
                normal,
                low_decimal,
                "{} changed signals when only price decimals changed",
                kind.as_str()
            );
            assert!(
                low_decimal.iter().any(|direction| *direction != 0),
                "{} produced no low-decimal signals",
                kind.as_str()
            );
        }
    }

    #[test]
    fn every_runnable_indicator_is_price_scale_invariant() {
        let rows = (0..180)
            .map(|i| {
                let t = i as f64;
                let close = 42_000.0 + t * 2.5 + (t / 3.0).sin() * 85.0 + (t / 11.0).cos() * 120.0;
                OhlcvBar {
                    open_time_ms: i * MS_PER_MINUTE,
                    open: close - (t / 5.0).sin() * 16.0,
                    high: close + 95.0 + (t % 7.0),
                    low: close - 95.0 - (t % 5.0),
                    close,
                    volume: 1.0,
                }
            })
            .collect::<Vec<_>>();
        let doge_like = scale_rows(&rows, 0.000003);

        for kind in IndicatorKind::IMPLEMENTED_DIRECT_OHLC {
            let btc_directions = momentum_signals(&rows, kind, 12, 14)
                .into_iter()
                .map(|signal| signal.direction)
                .collect::<Vec<_>>();
            let doge_directions = momentum_signals(&doge_like, kind, 12, 14)
                .into_iter()
                .map(|signal| signal.direction)
                .collect::<Vec<_>>();

            assert_eq!(
                btc_directions,
                doge_directions,
                "{} changed directions when only price scale changed",
                kind.as_str()
            );
        }
    }

    #[test]
    fn flat_market_signals_stay_finite_and_inactive_after_warmup() {
        let rows = (0..220)
            .map(|i| OhlcvBar {
                open_time_ms: i * MS_PER_MINUTE,
                open: 100.0,
                high: 100.0,
                low: 100.0,
                close: 100.0,
                volume: 1.0,
            })
            .collect::<Vec<_>>();

        for kind in IndicatorKind::IMPLEMENTED_DIRECT_OHLC {
            let signals = momentum_signals(&rows, kind, 12, 14);
            assert!(
                signals
                    .iter()
                    .all(|signal| signal.strength.is_finite() && signal.atr.is_finite()),
                "{} produced non-finite signal fields",
                kind.as_str()
            );
            let active_tail = signals
                .iter()
                .skip(120)
                .filter(|signal| signal.direction != 0)
                .count();
            assert_eq!(
                active_tail,
                0,
                "{} produced flat-market directions after warmup",
                kind.as_str()
            );
        }
    }

    #[test]
    fn roc_cmo_and_volatility_adjusted_momentum_do_not_collapse_to_identical_directions() {
        let rows = (0..120)
            .map(|i| {
                let drift = i as f64 * 0.03;
                let cycle = match i % 6 {
                    0 => -0.50,
                    1 => 0.10,
                    2 => 0.35,
                    3 => -0.15,
                    4 => 0.25,
                    _ => -0.05,
                };
                OhlcvBar {
                    open_time_ms: i * MS_PER_MINUTE,
                    open: 100.0 + drift + cycle,
                    high: 102.0 + drift + cycle,
                    low: 98.0 + drift + cycle,
                    close: 100.0 + drift + cycle,
                    volume: 1.0,
                }
            })
            .collect::<Vec<_>>();
        let roc = momentum_signals(&rows, IndicatorKind::Roc, 12, 14)
            .into_iter()
            .map(|signal| signal.direction)
            .collect::<Vec<_>>();
        let cmo = momentum_signals(&rows, IndicatorKind::Cmo, 12, 14)
            .into_iter()
            .map(|signal| signal.direction)
            .collect::<Vec<_>>();
        let vol = momentum_signals(&rows, IndicatorKind::VolatilityAdjustedMomentum, 12, 14)
            .into_iter()
            .map(|signal| signal.direction)
            .collect::<Vec<_>>();

        assert_ne!(roc, vol);
        assert_ne!(roc, cmo);
    }

    #[test]
    fn entropy_is_low_for_ordered_returns_and_higher_for_noisy_returns() {
        let ordered = (0..80)
            .map(|i| bar(i, 100.0 + i as f64 * 0.2))
            .collect::<Vec<_>>();
        let noisy = (0..80)
            .map(|i| {
                let jump = match i % 5 {
                    0 => -1.2,
                    1 => 0.4,
                    2 => 1.6,
                    3 => -0.3,
                    _ => 0.9,
                };
                bar(i, 100.0 + jump + (i as f64 * 0.03))
            })
            .collect::<Vec<_>>();

        let ordered_entropy = shannon_entropy(&ordered, 24)[79];
        let noisy_entropy = shannon_entropy(&noisy, 24)[79];

        assert!(ordered_entropy < noisy_entropy);
        assert!(ordered_entropy < 0.2);
    }

    #[test]
    fn hurst_gate_marks_persistent_series_above_chop() {
        let persistent = (0..100)
            .map(|i| bar(i, 100.0 + i as f64 * 0.2))
            .collect::<Vec<_>>();
        let choppy = (0..100)
            .map(|i| bar(i, 100.0 + if i % 2 == 0 { 1.0 } else { -1.0 }))
            .collect::<Vec<_>>();

        let persistent_hurst = hurst_exponent(&persistent, 32)[99];
        let choppy_hurst = hurst_exponent(&choppy, 32)[99];

        assert!(persistent_hurst > choppy_hurst);
        assert!(persistent_hurst > 0.7);
    }
}
