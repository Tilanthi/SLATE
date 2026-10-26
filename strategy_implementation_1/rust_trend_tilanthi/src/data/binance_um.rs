use ::zip::ZipArchive;
use anyhow::{Context, Result, anyhow, bail};
use chrono::{Datelike, NaiveDate, TimeZone, Utc};
use polars::prelude::*;
use rayon::prelude::*;
use reqwest::StatusCode;
use reqwest::blocking::Client;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::fs::{self, File, OpenOptions};
use std::io::{Cursor, Read, Write};
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::Duration as StdDuration;

pub const TOP7_2025_USDT_FUTURES: [&str; 7] = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT", "SUIUSDT",
];

pub const SCHEMA_VERSION: u32 = 1;
pub const SOURCE_ARCHIVE: u8 = 0;
pub const SOURCE_API_BACKFILL: u8 = 1;
pub const SOURCE_SYNTHETIC_FLAT: u8 = 2;
pub const MS_PER_MINUTE: i64 = 60_000;
pub const DEFAULT_STORE_ROOT: &str = "data/binance_um_1m/v1";
pub const ENV_STORE_ROOT: &str = "RUST_TREND_BINANCE_UM_1M_ROOT";

const ARCHIVE_BASE_URL: &str = "https://data.binance.vision";
const API_BASE_URL: &str = "https://fapi.binance.com";
const MAX_API_LIMIT: usize = 1500;

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Candle1m {
    pub open_time_ms: i64,
    pub open: f64,
    pub high: f64,
    pub low: f64,
    pub close: f64,
    pub volume_base: f64,
    pub quote_volume: f64,
    pub trade_count: u32,
    pub taker_buy_volume_base: f64,
    pub taker_buy_quote_volume: f64,
    pub source: u8,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MonthTask {
    pub symbol: String,
    pub month: NaiveDate,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ManifestEntry {
    pub symbol: String,
    pub month: String,
    pub status: String,
    pub rows: usize,
    pub archive_rows: usize,
    pub api_rows: usize,
    pub synthetic_rows: usize,
    pub started_at: String,
    pub finished_at: String,
    pub path: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CoverageSymbol {
    pub symbol: String,
    pub rows: usize,
    pub archive_rows: usize,
    pub api_rows: usize,
    pub synthetic_rows: usize,
    pub expected_rows: usize,
    pub start: String,
    pub end: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CoverageSummary {
    pub schema_version: u32,
    pub symbols: Vec<CoverageSymbol>,
}

#[derive(Debug, Clone, Default)]
pub struct SyncReport {
    pub synced_months: usize,
    pub skipped_months: usize,
    pub rows_written: usize,
    pub synthetic_rows: usize,
}

#[derive(Debug, Clone)]
pub struct KlineStore {
    root: PathBuf,
    client: Client,
}

impl KlineStore {
    pub fn new(root: impl Into<PathBuf>) -> Result<Self> {
        let client = Client::builder()
            .timeout(StdDuration::from_secs(60))
            .user_agent("rust_trend/0.1 binance-um-1m-store")
            .build()
            .context("build HTTP client")?;
        Ok(Self {
            root: root.into(),
            client,
        })
    }

    pub fn from_env() -> Result<Self> {
        let root = std::env::var(ENV_STORE_ROOT)
            .map(PathBuf::from)
            .unwrap_or_else(|_| PathBuf::from(DEFAULT_STORE_ROOT));
        Self::new(root)
    }

    pub fn root(&self) -> &Path {
        &self.root
    }

    pub fn sync_range(
        &self,
        symbols: &[String],
        start: NaiveDate,
        end: NaiveDate,
        force: bool,
    ) -> Result<SyncReport> {
        validate_date_range(start, end)?;
        self.ensure_meta()?;

        let tasks = month_tasks(symbols, start, end)?;
        let manifest_lock = Mutex::new(());
        let results: Vec<Result<MonthSyncOutcome>> = tasks
            .par_iter()
            .map(|task| self.sync_month(task, force, &manifest_lock))
            .collect();

        let mut report = SyncReport::default();
        for result in results {
            let outcome = result?;
            if outcome.skipped {
                report.skipped_months += 1;
            } else {
                report.synced_months += 1;
                report.rows_written += outcome.rows;
                report.synthetic_rows += outcome.synthetic_rows;
            }
        }

        Ok(report)
    }

    pub fn verify_range(
        &self,
        symbols: &[String],
        start: NaiveDate,
        end: NaiveDate,
    ) -> Result<CoverageSummary> {
        validate_date_range(start, end)?;
        let start_ms = date_to_ms(start)?;
        let end_ms = date_to_ms(end)?;
        let expected_rows = expected_minute_count(start_ms, end_ms)?;
        let mut coverage = Vec::with_capacity(symbols.len());

        for symbol in symbols {
            validate_symbol(symbol)?;
            let rows = self.load_range(symbol, start, end)?;
            verify_rows_exact(&rows, start_ms, end_ms)
                .with_context(|| format!("verify {symbol}"))?;
            let counts = source_counts(&rows);
            coverage.push(CoverageSymbol {
                symbol: symbol.to_string(),
                rows: rows.len(),
                archive_rows: counts.archive,
                api_rows: counts.api,
                synthetic_rows: counts.synthetic,
                expected_rows,
                start: start.to_string(),
                end: end.to_string(),
            });
        }

        let summary = CoverageSummary {
            schema_version: SCHEMA_VERSION,
            symbols: coverage,
        };
        self.write_coverage(&summary)?;
        Ok(summary)
    }

    pub fn load_range(
        &self,
        symbol: &str,
        start: NaiveDate,
        end: NaiveDate,
    ) -> Result<Vec<Candle1m>> {
        validate_symbol(symbol)?;
        validate_date_range(start, end)?;
        let start_ms = date_to_ms(start)?;
        let end_ms = date_to_ms(end)?;
        let tasks = month_tasks(&[symbol.to_string()], start, end)?;
        let mut rows = Vec::new();
        for task in tasks {
            let path = self.month_path(symbol, task.month);
            let mut month_rows =
                read_parquet(&path).with_context(|| format!("read {}", path.display()))?;
            rows.append(&mut month_rows);
        }
        rows.retain(|row| row.open_time_ms >= start_ms && row.open_time_ms < end_ms);
        rows.sort_by_key(|row| row.open_time_ms);
        Ok(rows)
    }

    fn sync_month(
        &self,
        task: &MonthTask,
        force: bool,
        manifest_lock: &Mutex<()>,
    ) -> Result<MonthSyncOutcome> {
        validate_symbol(&task.symbol)?;
        let (month_start_ms, month_end_ms) = month_bounds_ms(task.month)?;
        let path = self.month_path(&task.symbol, task.month);

        if !force && path.exists() {
            let rows = read_parquet(&path)?;
            if verify_rows_exact(&rows, month_start_ms, month_end_ms).is_ok() {
                return Ok(MonthSyncOutcome {
                    skipped: true,
                    rows: rows.len(),
                    synthetic_rows: source_counts(&rows).synthetic,
                });
            }
        }

        let started_at = Utc::now().to_rfc3339();
        let archive = self.download_archive(&task.symbol, task.month)?;
        let mut rows = parse_archive_zip(&archive, SOURCE_ARCHIVE)
            .with_context(|| format!("parse {} {}", task.symbol, task.month.format("%Y-%m")))?;
        rows.retain(|row| row.open_time_ms >= month_start_ms && row.open_time_ms < month_end_ms);

        let archive_rows = rows.len();
        rows = self.repair_rows(&task.symbol, rows, month_start_ms, month_end_ms)?;
        verify_rows_exact(&rows, month_start_ms, month_end_ms)?;
        write_parquet_atomic(&path, &rows)?;

        let counts = source_counts(&rows);
        let entry = ManifestEntry {
            symbol: task.symbol.clone(),
            month: task.month.format("%Y-%m").to_string(),
            status: "ok".to_string(),
            rows: rows.len(),
            archive_rows,
            api_rows: counts.api,
            synthetic_rows: counts.synthetic,
            started_at,
            finished_at: Utc::now().to_rfc3339(),
            path: path.display().to_string(),
        };
        self.append_manifest(&entry, manifest_lock)?;

        Ok(MonthSyncOutcome {
            skipped: false,
            rows: rows.len(),
            synthetic_rows: counts.synthetic,
        })
    }

    fn repair_rows(
        &self,
        symbol: &str,
        rows: Vec<Candle1m>,
        start_ms: i64,
        end_ms: i64,
    ) -> Result<Vec<Candle1m>> {
        let mut by_ts = rows_to_map(rows);
        let gaps = missing_ranges(&by_ts, start_ms, end_ms);

        for (gap_start, gap_end) in gaps {
            let api_rows = self.fetch_api_range(symbol, gap_start, gap_end)?;
            for row in api_rows {
                if row.open_time_ms >= gap_start && row.open_time_ms < gap_end {
                    by_ts.entry(row.open_time_ms).or_insert(row);
                }
            }
        }

        let mut prior_close_cache: Option<f64> = None;
        let mut ts = start_ms;
        while ts < end_ms {
            if !by_ts.contains_key(&ts) {
                let close = match previous_close(&by_ts, ts) {
                    Some(close) => close,
                    None => match prior_close_cache {
                        Some(close) => close,
                        None => {
                            let close = self.fetch_prior_close(symbol, ts)?;
                            prior_close_cache = Some(close);
                            close
                        }
                    },
                };
                by_ts.insert(ts, synthetic_row(ts, close));
            }
            ts += MS_PER_MINUTE;
        }

        Ok(by_ts.into_values().collect())
    }

    fn download_archive(&self, symbol: &str, month: NaiveDate) -> Result<Vec<u8>> {
        let zip_url = archive_url(symbol, month, false);
        let checksum_url = archive_url(symbol, month, true);
        let checksum_text = get_text(&self.client, &checksum_url)?;
        let expected_sha = checksum_text
            .split_whitespace()
            .next()
            .ok_or_else(|| anyhow!("empty checksum response for {checksum_url}"))?;
        let bytes = get_bytes(&self.client, &zip_url)?;
        let actual_sha = hex::encode(Sha256::digest(&bytes));
        if actual_sha != expected_sha {
            bail!("checksum mismatch for {zip_url}: expected {expected_sha}, got {actual_sha}");
        }
        Ok(bytes)
    }

    fn fetch_api_range(&self, symbol: &str, start_ms: i64, end_ms: i64) -> Result<Vec<Candle1m>> {
        let mut out = Vec::new();
        let mut cursor = start_ms;
        while cursor < end_ms {
            let chunk_end = (cursor + (MAX_API_LIMIT as i64 * MS_PER_MINUTE)).min(end_ms);
            let rows =
                self.fetch_api_klines(symbol, Some(cursor), Some(chunk_end - 1), MAX_API_LIMIT)?;
            let next_cursor = rows
                .last()
                .map(|row| row.open_time_ms + MS_PER_MINUTE)
                .unwrap_or(chunk_end);
            out.extend(rows);
            cursor = next_cursor.max(chunk_end);
            std::thread::sleep(StdDuration::from_millis(75));
        }
        Ok(out)
    }

    fn fetch_prior_close(&self, symbol: &str, before_ms: i64) -> Result<f64> {
        let start_ms = before_ms - 7 * 24 * 60 * MS_PER_MINUTE;
        let rows =
            self.fetch_api_klines(symbol, Some(start_ms), Some(before_ms - 1), MAX_API_LIMIT)?;
        rows.last()
            .map(|row| row.close)
            .ok_or_else(|| anyhow!("no prior close available for {symbol} before {before_ms}"))
    }

    fn fetch_api_klines(
        &self,
        symbol: &str,
        start_ms: Option<i64>,
        end_ms: Option<i64>,
        limit: usize,
    ) -> Result<Vec<Candle1m>> {
        let mut request = self
            .client
            .get(format!("{API_BASE_URL}/fapi/v1/klines"))
            .query(&[
                ("symbol", symbol.to_string()),
                ("interval", "1m".to_string()),
                ("limit", limit.to_string()),
            ]);
        if let Some(start_ms) = start_ms {
            request = request.query(&[("startTime", start_ms.to_string())]);
        }
        if let Some(end_ms) = end_ms {
            request = request.query(&[("endTime", end_ms.to_string())]);
        }

        let response = request.send().context("send Binance fapi klines request")?;
        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().unwrap_or_default();
            bail!("Binance fapi klines error {status}: {body}");
        }
        let values: Vec<Vec<serde_json::Value>> =
            response.json().context("parse fapi klines JSON")?;
        values
            .into_iter()
            .map(|row| parse_api_row(&row))
            .collect::<Result<Vec<_>>>()
    }

    fn ensure_meta(&self) -> Result<()> {
        fs::create_dir_all(self.root.join("_meta"))?;
        fs::write(
            self.root.join("_meta/schema_version.txt"),
            format!("{SCHEMA_VERSION}\n"),
        )?;
        Ok(())
    }

    fn append_manifest(&self, entry: &ManifestEntry, lock: &Mutex<()>) -> Result<()> {
        let _guard = lock.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
        fs::create_dir_all(self.root.join("_meta"))?;
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(self.root.join("_meta/manifest.jsonl"))?;
        serde_json::to_writer(&mut file, entry)?;
        writeln!(file)?;
        file.sync_all()?;
        Ok(())
    }

    fn write_coverage(&self, summary: &CoverageSummary) -> Result<()> {
        fs::create_dir_all(self.root.join("_meta"))?;
        let path = self.root.join("_meta/coverage.json");
        let tmp = path.with_extension("json.tmp");
        let mut file = File::create(&tmp)?;
        serde_json::to_writer_pretty(&mut file, summary)?;
        writeln!(file)?;
        file.sync_all()?;
        fs::rename(tmp, path)?;
        Ok(())
    }

    fn month_path(&self, symbol: &str, month: NaiveDate) -> PathBuf {
        self.root
            .join("klines")
            .join(symbol)
            .join(format!("{:04}", month.year()))
            .join(format!("{}.parquet", month.format("%Y-%m")))
    }
}

#[derive(Debug, Clone, Copy, Default)]
struct SourceCounts {
    archive: usize,
    api: usize,
    synthetic: usize,
}

#[derive(Debug, Clone, Copy)]
struct MonthSyncOutcome {
    skipped: bool,
    rows: usize,
    synthetic_rows: usize,
}

pub fn preset_symbols(name: &str) -> Result<Vec<String>> {
    match name {
        "binance-um-top7-2025" => Ok(TOP7_2025_USDT_FUTURES
            .iter()
            .map(|s| s.to_string())
            .collect()),
        other => bail!("unknown preset {other}; supported: binance-um-top7-2025"),
    }
}

pub fn parse_date(value: &str) -> Result<NaiveDate> {
    NaiveDate::parse_from_str(value, "%Y-%m-%d")
        .with_context(|| format!("parse date {value}; expected YYYY-MM-DD"))
}

fn validate_symbol(symbol: &str) -> Result<()> {
    if symbol.is_empty()
        || !symbol
            .bytes()
            .all(|b| b.is_ascii_uppercase() || b.is_ascii_digit())
    {
        bail!("invalid Binance USD-M symbol: {symbol}");
    }
    Ok(())
}

fn validate_date_range(start: NaiveDate, end: NaiveDate) -> Result<()> {
    if start >= end {
        bail!("start date must be before end date: {start} >= {end}");
    }
    Ok(())
}

fn date_to_ms(date: NaiveDate) -> Result<i64> {
    Ok(Utc
        .from_utc_datetime(
            &date
                .and_hms_opt(0, 0, 0)
                .ok_or_else(|| anyhow!("invalid midnight for {date}"))?,
        )
        .timestamp_millis())
}

fn month_start(year: i32, month: u32) -> Result<NaiveDate> {
    NaiveDate::from_ymd_opt(year, month, 1).ok_or_else(|| anyhow!("invalid month {year}-{month}"))
}

fn next_month(date: NaiveDate) -> Result<NaiveDate> {
    if date.month() == 12 {
        month_start(date.year() + 1, 1)
    } else {
        month_start(date.year(), date.month() + 1)
    }
}

fn floor_month(date: NaiveDate) -> Result<NaiveDate> {
    month_start(date.year(), date.month())
}

fn month_bounds_ms(month: NaiveDate) -> Result<(i64, i64)> {
    Ok((date_to_ms(month)?, date_to_ms(next_month(month)?)?))
}

fn month_tasks(symbols: &[String], start: NaiveDate, end: NaiveDate) -> Result<Vec<MonthTask>> {
    let mut months = Vec::new();
    let mut month = floor_month(start)?;
    while month < end {
        months.push(month);
        month = next_month(month)?;
    }

    let mut tasks = Vec::with_capacity(symbols.len() * months.len());
    for symbol in symbols {
        validate_symbol(symbol)?;
        for month in &months {
            tasks.push(MonthTask {
                symbol: symbol.clone(),
                month: *month,
            });
        }
    }
    Ok(tasks)
}

fn expected_minute_count(start_ms: i64, end_ms: i64) -> Result<usize> {
    if start_ms >= end_ms || start_ms % MS_PER_MINUTE != 0 || end_ms % MS_PER_MINUTE != 0 {
        bail!("invalid minute-aligned range {start_ms}..{end_ms}");
    }
    Ok(((end_ms - start_ms) / MS_PER_MINUTE) as usize)
}

fn archive_url(symbol: &str, month: NaiveDate, checksum: bool) -> String {
    let file = format!("{symbol}-1m-{}.zip", month.format("%Y-%m"));
    let suffix = if checksum { ".CHECKSUM" } else { "" };
    format!("{ARCHIVE_BASE_URL}/data/futures/um/monthly/klines/{symbol}/1m/{file}{suffix}")
}

fn get_text(client: &Client, url: &str) -> Result<String> {
    let response = client
        .get(url)
        .send()
        .with_context(|| format!("GET {url}"))?;
    if response.status() == StatusCode::NOT_FOUND {
        bail!("not found: {url}");
    }
    if !response.status().is_success() {
        bail!("GET {url} failed with {}", response.status());
    }
    response
        .text()
        .with_context(|| format!("read response {url}"))
}

fn get_bytes(client: &Client, url: &str) -> Result<Vec<u8>> {
    let response = client
        .get(url)
        .send()
        .with_context(|| format!("GET {url}"))?;
    if response.status() == StatusCode::NOT_FOUND {
        bail!("not found: {url}");
    }
    if !response.status().is_success() {
        bail!("GET {url} failed with {}", response.status());
    }
    Ok(response.bytes()?.to_vec())
}

fn parse_archive_zip(bytes: &[u8], source: u8) -> Result<Vec<Candle1m>> {
    let reader = Cursor::new(bytes);
    let mut archive = ZipArchive::new(reader).context("open zip archive")?;
    let mut csv_index = None;
    for i in 0..archive.len() {
        let name = archive.by_index(i)?.name().to_string();
        if name.ends_with(".csv") {
            csv_index = Some(i);
            break;
        }
    }
    let csv_index = csv_index.ok_or_else(|| anyhow!("zip archive did not contain a CSV file"))?;
    let mut file = archive.by_index(csv_index)?;
    let mut text = String::new();
    file.read_to_string(&mut text)?;

    let mut reader = csv::ReaderBuilder::new()
        .has_headers(false)
        .from_reader(text.as_bytes());
    let mut rows = Vec::new();
    for record in reader.records() {
        let record = record?;
        if record.get(0) == Some("open_time") {
            continue;
        }
        rows.push(parse_csv_row(&record, source)?);
    }
    Ok(rows)
}

fn parse_csv_row(record: &csv::StringRecord, source: u8) -> Result<Candle1m> {
    if record.len() < 11 {
        bail!("expected at least 11 kline columns, got {}", record.len());
    }
    Ok(Candle1m {
        open_time_ms: parse_field(record, 0, "open_time")?,
        open: parse_field(record, 1, "open")?,
        high: parse_field(record, 2, "high")?,
        low: parse_field(record, 3, "low")?,
        close: parse_field(record, 4, "close")?,
        volume_base: parse_field(record, 5, "volume")?,
        quote_volume: parse_field(record, 7, "quote_volume")?,
        trade_count: parse_field::<u32>(record, 8, "trade_count")?,
        taker_buy_volume_base: parse_field(record, 9, "taker_buy_volume")?,
        taker_buy_quote_volume: parse_field(record, 10, "taker_buy_quote_volume")?,
        source,
    })
}

fn parse_field<T: std::str::FromStr>(
    record: &csv::StringRecord,
    idx: usize,
    name: &str,
) -> Result<T>
where
    T::Err: std::error::Error + Send + Sync + 'static,
{
    record
        .get(idx)
        .ok_or_else(|| anyhow!("missing {name} at column {idx}"))?
        .parse::<T>()
        .with_context(|| format!("parse {name} at column {idx}"))
}

fn parse_api_row(row: &[serde_json::Value]) -> Result<Candle1m> {
    if row.len() < 11 {
        bail!(
            "expected at least 11 kline values from API, got {}",
            row.len()
        );
    }
    Ok(Candle1m {
        open_time_ms: json_i64(&row[0], "open_time")?,
        open: json_f64(&row[1], "open")?,
        high: json_f64(&row[2], "high")?,
        low: json_f64(&row[3], "low")?,
        close: json_f64(&row[4], "close")?,
        volume_base: json_f64(&row[5], "volume")?,
        quote_volume: json_f64(&row[7], "quote_volume")?,
        trade_count: json_u32(&row[8], "trade_count")?,
        taker_buy_volume_base: json_f64(&row[9], "taker_buy_volume")?,
        taker_buy_quote_volume: json_f64(&row[10], "taker_buy_quote_volume")?,
        source: SOURCE_API_BACKFILL,
    })
}

fn json_i64(value: &serde_json::Value, name: &str) -> Result<i64> {
    value
        .as_i64()
        .or_else(|| value.as_str().and_then(|s| s.parse().ok()))
        .ok_or_else(|| anyhow!("parse API {name} as i64"))
}

fn json_u32(value: &serde_json::Value, name: &str) -> Result<u32> {
    value
        .as_u64()
        .and_then(|v| u32::try_from(v).ok())
        .or_else(|| value.as_str().and_then(|s| s.parse().ok()))
        .ok_or_else(|| anyhow!("parse API {name} as u32"))
}

fn json_f64(value: &serde_json::Value, name: &str) -> Result<f64> {
    value
        .as_f64()
        .or_else(|| value.as_str().and_then(|s| s.parse().ok()))
        .ok_or_else(|| anyhow!("parse API {name} as f64"))
}

fn rows_to_map(rows: Vec<Candle1m>) -> BTreeMap<i64, Candle1m> {
    let mut out = BTreeMap::new();
    for row in rows {
        out.entry(row.open_time_ms).or_insert(row);
    }
    out
}

fn missing_ranges(rows: &BTreeMap<i64, Candle1m>, start_ms: i64, end_ms: i64) -> Vec<(i64, i64)> {
    let mut ranges = Vec::new();
    let mut current_start = None;
    let mut ts = start_ms;
    while ts < end_ms {
        if rows.contains_key(&ts) {
            if let Some(start) = current_start.take() {
                ranges.push((start, ts));
            }
        } else if current_start.is_none() {
            current_start = Some(ts);
        }
        ts += MS_PER_MINUTE;
    }
    if let Some(start) = current_start {
        ranges.push((start, end_ms));
    }
    ranges
}

fn previous_close(rows: &BTreeMap<i64, Candle1m>, ts: i64) -> Option<f64> {
    rows.range(..ts).next_back().map(|(_, row)| row.close)
}

fn synthetic_row(open_time_ms: i64, close: f64) -> Candle1m {
    Candle1m {
        open_time_ms,
        open: close,
        high: close,
        low: close,
        close,
        volume_base: 0.0,
        quote_volume: 0.0,
        trade_count: 0,
        taker_buy_volume_base: 0.0,
        taker_buy_quote_volume: 0.0,
        source: SOURCE_SYNTHETIC_FLAT,
    }
}

fn verify_rows_exact(rows: &[Candle1m], start_ms: i64, end_ms: i64) -> Result<()> {
    let expected = expected_minute_count(start_ms, end_ms)?;
    if rows.len() != expected {
        bail!("expected {expected} rows, got {}", rows.len());
    }
    let mut seen = BTreeSet::new();
    let mut expected_ts = start_ms;
    for row in rows {
        if row.open_time_ms != expected_ts {
            bail!(
                "timestamp mismatch: expected {}, got {}",
                expected_ts,
                row.open_time_ms
            );
        }
        if !seen.insert(row.open_time_ms) {
            bail!("duplicate timestamp {}", row.open_time_ms);
        }
        expected_ts += MS_PER_MINUTE;
    }
    Ok(())
}

fn source_counts(rows: &[Candle1m]) -> SourceCounts {
    let mut counts = SourceCounts::default();
    for row in rows {
        match row.source {
            SOURCE_ARCHIVE => counts.archive += 1,
            SOURCE_API_BACKFILL => counts.api += 1,
            SOURCE_SYNTHETIC_FLAT => counts.synthetic += 1,
            _ => {}
        }
    }
    counts
}

fn write_parquet_atomic(path: &Path, rows: &[Candle1m]) -> Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let tmp = path.with_extension("parquet.tmp");
    let file = File::create(&tmp)?;
    let mut df = rows_to_dataframe(rows)?;
    ParquetWriter::new(file)
        .with_compression(ParquetCompression::Zstd(None))
        .with_row_group_size(Some(rows.len()))
        .finish(&mut df)?;
    fs::rename(&tmp, path)?;
    Ok(())
}

fn rows_to_dataframe(rows: &[Candle1m]) -> Result<DataFrame> {
    let open_time_ms: Vec<i64> = rows.iter().map(|r| r.open_time_ms).collect();
    let open: Vec<f64> = rows.iter().map(|r| r.open).collect();
    let high: Vec<f64> = rows.iter().map(|r| r.high).collect();
    let low: Vec<f64> = rows.iter().map(|r| r.low).collect();
    let close: Vec<f64> = rows.iter().map(|r| r.close).collect();
    let volume_base: Vec<f64> = rows.iter().map(|r| r.volume_base).collect();
    let quote_volume: Vec<f64> = rows.iter().map(|r| r.quote_volume).collect();
    let trade_count: Vec<u32> = rows.iter().map(|r| r.trade_count).collect();
    let taker_buy_volume_base: Vec<f64> = rows.iter().map(|r| r.taker_buy_volume_base).collect();
    let taker_buy_quote_volume: Vec<f64> = rows.iter().map(|r| r.taker_buy_quote_volume).collect();
    let source: Vec<u8> = rows.iter().map(|r| r.source).collect();

    Ok(DataFrame::new(vec![
        Series::new("open_time_ms".into(), open_time_ms).into(),
        Series::new("open".into(), open).into(),
        Series::new("high".into(), high).into(),
        Series::new("low".into(), low).into(),
        Series::new("close".into(), close).into(),
        Series::new("volume_base".into(), volume_base).into(),
        Series::new("quote_volume".into(), quote_volume).into(),
        Series::new("trade_count".into(), trade_count).into(),
        Series::new("taker_buy_volume_base".into(), taker_buy_volume_base).into(),
        Series::new("taker_buy_quote_volume".into(), taker_buy_quote_volume).into(),
        Series::new("source".into(), source).into(),
    ])?)
}

fn read_parquet(path: &Path) -> Result<Vec<Candle1m>> {
    let file = File::open(path)?;
    let df = ParquetReader::new(file).finish()?;
    dataframe_to_rows(&df)
}

fn dataframe_to_rows(df: &DataFrame) -> Result<Vec<Candle1m>> {
    let open_time_ms = df.column("open_time_ms")?.i64()?;
    let open = df.column("open")?.f64()?;
    let high = df.column("high")?.f64()?;
    let low = df.column("low")?.f64()?;
    let close = df.column("close")?.f64()?;
    let volume_base = df.column("volume_base")?.f64()?;
    let quote_volume = df.column("quote_volume")?.f64()?;
    let trade_count = df.column("trade_count")?.u32()?;
    let taker_buy_volume_base = df.column("taker_buy_volume_base")?.f64()?;
    let taker_buy_quote_volume = df.column("taker_buy_quote_volume")?.f64()?;
    let source = df.column("source")?.u8()?;

    let mut rows = Vec::with_capacity(df.height());
    for i in 0..df.height() {
        rows.push(Candle1m {
            open_time_ms: open_time_ms.get(i).unwrap_or_default(),
            open: open.get(i).unwrap_or_default(),
            high: high.get(i).unwrap_or_default(),
            low: low.get(i).unwrap_or_default(),
            close: close.get(i).unwrap_or_default(),
            volume_base: volume_base.get(i).unwrap_or_default(),
            quote_volume: quote_volume.get(i).unwrap_or_default(),
            trade_count: trade_count.get(i).unwrap_or_default(),
            taker_buy_volume_base: taker_buy_volume_base.get(i).unwrap_or_default(),
            taker_buy_quote_volume: taker_buy_quote_volume.get(i).unwrap_or_default(),
            source: source.get(i).unwrap_or_default(),
        });
    }
    rows.sort_by_key(|row| row.open_time_ms);
    Ok(rows)
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[test]
    fn month_task_generation_excludes_end_boundary_month() {
        let symbols = vec!["BTCUSDT".to_string(), "ETHUSDT".to_string()];
        let tasks = month_tasks(
            &symbols,
            NaiveDate::from_ymd_opt(2025, 1, 1).unwrap(),
            NaiveDate::from_ymd_opt(2025, 3, 1).unwrap(),
        )
        .unwrap();

        assert_eq!(tasks.len(), 4);
        assert_eq!(tasks[0].month, NaiveDate::from_ymd_opt(2025, 1, 1).unwrap());
        assert_eq!(tasks[1].month, NaiveDate::from_ymd_opt(2025, 2, 1).unwrap());
    }

    #[test]
    fn expected_2025_row_count_is_full_non_leap_year() {
        let start = date_to_ms(NaiveDate::from_ymd_opt(2025, 1, 1).unwrap()).unwrap();
        let end = date_to_ms(NaiveDate::from_ymd_opt(2026, 1, 1).unwrap()).unwrap();

        assert_eq!(expected_minute_count(start, end).unwrap(), 525_600);
    }

    #[test]
    fn gap_detection_groups_contiguous_missing_minutes() {
        let mut rows = BTreeMap::new();
        rows.insert(0, synthetic_row(0, 100.0));
        rows.insert(180_000, synthetic_row(180_000, 101.0));
        rows.insert(300_000, synthetic_row(300_000, 102.0));

        assert_eq!(
            missing_ranges(&rows, 0, 360_000),
            vec![(60_000, 180_000), (240_000, 300_000)]
        );
    }

    #[test]
    fn exact_verifier_rejects_duplicate_or_missing_rows() {
        let ok = vec![synthetic_row(0, 1.0), synthetic_row(60_000, 1.0)];
        assert!(verify_rows_exact(&ok, 0, 120_000).is_ok());

        let missing = vec![synthetic_row(0, 1.0), synthetic_row(120_000, 1.0)];
        assert!(verify_rows_exact(&missing, 0, 180_000).is_err());
    }

    #[test]
    fn parquet_roundtrip_preserves_rows() {
        let td = TempDir::new().unwrap();
        let path = td.path().join("sample.parquet");
        let rows = vec![
            Candle1m {
                open_time_ms: 0,
                open: 100.0,
                high: 101.0,
                low: 99.0,
                close: 100.5,
                volume_base: 10.0,
                quote_volume: 1_005.0,
                trade_count: 7,
                taker_buy_volume_base: 5.0,
                taker_buy_quote_volume: 502.5,
                source: SOURCE_ARCHIVE,
            },
            synthetic_row(60_000, 100.5),
        ];

        write_parquet_atomic(&path, &rows).unwrap();
        let loaded = read_parquet(&path).unwrap();

        assert_eq!(loaded, rows);
    }

    #[test]
    fn csv_parser_skips_archive_header() {
        let csv = "open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,taker_buy_quote_volume,ignore\n\
                   1735689600000,100,101,99,100.5,2,1735689659999,201,3,1,100.5,0\n";
        let mut reader = csv::ReaderBuilder::new()
            .has_headers(false)
            .from_reader(csv.as_bytes());
        let mut rows = Vec::new();
        for record in reader.records() {
            let record = record.unwrap();
            if record.get(0) == Some("open_time") {
                continue;
            }
            rows.push(parse_csv_row(&record, SOURCE_ARCHIVE).unwrap());
        }

        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0].open_time_ms, 1_735_689_600_000);
        assert_eq!(rows[0].trade_count, 3);
    }
}
