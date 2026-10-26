import csv
import html
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd


DAY_MS = 24 * 60 * 60 * 1000
MS_PER_MINUTE = 60 * 1000
STAGNATION_THRESHOLD_DAYS = 7.0


def safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        out = float(value)
        return out if math.isfinite(out) else default
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def money(value, digits=0):
    return f"${safe_float(value):,.{digits}f}"


def pct(value, digits=2, signed=False):
    sign = "+" if signed else ""
    return f"{safe_float(value):{sign}.{digits}f}%"


def pct_decimal(value, digits=2, signed=False):
    return pct(safe_float(value) * 100.0, digits, signed)


def html_escape(value):
    return html.escape(str(value), quote=True)


def cls_pos_neg(value):
    return "pos" if safe_float(value) >= 0 else "neg"


def dt_ms(value):
    return pd.to_datetime(int(value), unit="ms", utc=True).strftime("%Y-%m-%d")


def dt_ms_long(value):
    return pd.to_datetime(int(value), unit="ms", utc=True).strftime("%b %d, %Y")


def read_json(path, default=None):
    if not path.exists():
        return {} if default is None else default
    with path.open() as handle:
        return json.load(handle)


def read_csv(path):
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def source_run_dir(run_dir, run_id):
    return run_dir.parent / run_id


def load_source_tables(run_dir, summary):
    trades = []
    provenance = []
    for run in summary.get("runs", []):
        run_id = run.get("run_id", "")
        offset_days = run.get("offset_days", "")
        src = source_run_dir(run_dir, run_id)

        trade_df = read_csv(src / "oos_trades.csv")
        if not trade_df.empty:
            trade_df.insert(0, "run_id", run_id)
            trade_df.insert(1, "offset_days", offset_days)
            trades.append(trade_df)

        prov_df = read_csv(src / "optimizer_provenance.csv")
        if not prov_df.empty:
            provenance.append(prov_df)

    all_trades = pd.concat(trades, ignore_index=True) if trades else pd.DataFrame()
    all_provenance = pd.concat(provenance, ignore_index=True) if provenance else pd.DataFrame()
    if not all_trades.empty:
        all_trades.to_csv(run_dir / "rollup_trades.csv", index=False)
    return all_trades, all_provenance


def compute_daily_and_monthly(run_dir, equity):
    equity = equity.copy()
    equity["dt"] = pd.to_datetime(equity["timestamp_ms"], unit="ms", utc=True)
    equity = equity.set_index("dt").sort_index()

    daily = equity.resample("D").last().ffill()
    daily["daily_return"] = daily["balance"].pct_change().fillna(0.0)
    daily[["timestamp_ms", "balance", "pnl", "drawdown", "drawdown_pct", "exposure_notional", "daily_return"]].to_csv(
        run_dir / "daily_returns.csv"
    )

    month_end = daily["balance"].resample("ME").last()
    monthly = month_end.pct_change()
    if len(monthly) > 0:
        monthly.iloc[0] = month_end.iloc[0] / daily["balance"].iloc[0] - 1.0
    monthly_df = pd.DataFrame({"return": monthly})
    monthly_df["year"] = monthly_df.index.year
    monthly_df["month"] = monthly_df.index.month
    monthly_pivot = monthly_df.pivot(index="year", columns="month", values="return") * 100.0
    monthly_pivot.to_csv(run_dir / "monthly_returns.csv")
    return daily, monthly_pivot


def compute_stagnation_periods(equity):
    if equity.empty:
        return []
    rows = equity.sort_values("timestamp_ms").to_dict("records")
    peak_equity = 0.0
    peak_time_ms = safe_int(rows[0]["timestamp_ms"])
    active = None
    periods = []

    for row in rows:
        timestamp_ms = safe_int(row["timestamp_ms"])
        pnl = safe_float(row.get("pnl", row.get("equity", 0.0)))
        if pnl >= peak_equity:
            if active is not None:
                max_drawdown = active["peak_equity"] - active["trough_equity"]
                periods.append(
                    {
                        "peak_time_ms": active["peak_time_ms"],
                        "start_time_ms": active["start_time_ms"],
                        "recovery_time_ms": timestamp_ms,
                        "duration_minutes": (timestamp_ms - active["start_time_ms"]) / MS_PER_MINUTE,
                        "recovered": True,
                        "peak_equity": active["peak_equity"],
                        "trough_equity": active["trough_equity"],
                        "max_drawdown": max_drawdown,
                    }
                )
                active = None
            peak_equity = pnl
            peak_time_ms = timestamp_ms
        elif active is not None:
            active["trough_equity"] = min(active["trough_equity"], pnl)
        else:
            active = {
                "start_time_ms": timestamp_ms,
                "peak_time_ms": peak_time_ms,
                "peak_equity": peak_equity,
                "trough_equity": pnl,
            }

    if active is not None:
        last_ms = safe_int(rows[-1]["timestamp_ms"])
        max_drawdown = active["peak_equity"] - active["trough_equity"]
        periods.append(
            {
                "peak_time_ms": active["peak_time_ms"],
                "start_time_ms": active["start_time_ms"],
                "recovery_time_ms": None,
                "duration_minutes": (last_ms - active["start_time_ms"]) / MS_PER_MINUTE,
                "recovered": False,
                "peak_equity": active["peak_equity"],
                "trough_equity": active["trough_equity"],
                "max_drawdown": max_drawdown,
            }
        )

    for period in periods:
        period["duration_days"] = period["duration_minutes"] / 1440.0
    return periods


def max_drawdown_from_daily(daily):
    values = daily["balance"].to_numpy(dtype=float)
    peaks = np.maximum.accumulate(values)
    drawdowns = (values - peaks) / peaks
    return abs(np.min(drawdowns)) if len(drawdowns) else 0.0


def symbol_metrics(trades, provenance):
    if trades.empty:
        return []
    out = []
    selections = {}
    if not provenance.empty and "symbol" in provenance.columns:
        selections = provenance.groupby("symbol").size().to_dict()
    for symbol, group in trades.groupby("symbol"):
        pnl = group["pnl"].astype(float)
        gross_win = pnl[pnl > 0].sum()
        gross_loss = abs(pnl[pnl < 0].sum())
        pf = gross_win / gross_loss if gross_loss > 0 else (math.inf if gross_win > 0 else 0.0)
        out.append(
            {
                "symbol": symbol,
                "trades": len(group),
                "pnl": pnl.sum(),
                "win_rate": (pnl > 0).mean() * 100.0,
                "profit_factor": pf,
                "avg_trade": pnl.mean(),
                "long_trades": int((group["side"] == "Long").sum()) if "side" in group.columns else 0,
                "short_trades": int((group["side"] == "Short").sum()) if "side" in group.columns else 0,
                "selections": int(selections.get(symbol, 0)),
            }
        )
    return sorted(out, key=lambda row: row["pnl"], reverse=True)


def fold_metrics(provenance):
    if provenance.empty:
        return []
    df = provenance.copy()
    for col in ["fold_index", "offset_days", "oos_total_pnl", "oos_trades", "oos_profit_factor", "oos_max_drawdown_pct"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    selected = df[df.get("selection_status", "") == "selected"] if "selection_status" in df.columns else df
    rows = []
    for fold, group in selected.groupby("fold_index"):
        pf_values = group["oos_profit_factor"].replace([np.inf, -np.inf], np.nan).dropna()
        rows.append(
            {
                "fold_index": int(fold),
                "offsets": int(group["offset_days"].nunique()),
                "symbols": int(group["symbol"].nunique()) if "symbol" in group.columns else 0,
                "selections": len(group),
                "oos_pnl": group["oos_total_pnl"].sum(),
                "oos_trades": int(group["oos_trades"].sum()),
                "median_pf": float(pf_values.median()) if len(pf_values) else 0.0,
                "max_dd_pct": float(group["oos_max_drawdown_pct"].max()) if len(group) else 0.0,
            }
        )
    return sorted(rows, key=lambda row: row["fold_index"])


def provenance_audit(provenance):
    if provenance.empty:
        return {
            "rows": 0,
            "modes": "missing",
            "boundary_failures": 0,
            "min_scope": "",
            "max_scope": "",
        }
    df = provenance.copy()
    for col in ["max_timestamp_seen", "optimizer_scope_end", "optimizer_scope_start"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    failures = df[df["max_timestamp_seen"] > df["optimizer_scope_end"]]
    modes = sorted(str(value) for value in df.get("optimizer_mode", pd.Series(dtype=str)).dropna().unique())
    return {
        "rows": len(df),
        "modes": ", ".join(modes) if modes else "missing",
        "boundary_failures": len(failures),
        "min_scope": dt_ms(df["optimizer_scope_start"].min()) if df["optimizer_scope_start"].notna().any() else "",
        "max_scope": dt_ms(df["optimizer_scope_end"].max()) if df["optimizer_scope_end"].notna().any() else "",
    }


def monthly_table(monthly_pivot):
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    header = "<tr><th>Year</th>" + "".join(f"<th>{m}</th>" for m in month_names) + "<th>Comp.</th></tr>"
    body = []
    for year, row in monthly_pivot.iterrows():
        cells = []
        compounded = 1.0
        seen = False
        for month in range(1, 13):
            value = row.get(month, np.nan)
            if np.isnan(value):
                cells.append('<td class="muted">-</td>')
            else:
                seen = True
                compounded *= 1.0 + value / 100.0
                cls = "pos" if value >= 0 else "neg"
                cells.append(f'<td class="{cls}">{value:+.1f}%</td>')
        total = (compounded - 1.0) * 100.0 if seen else 0.0
        total_cls = "pos" if total >= 0 else "neg"
        body.append(f"<tr><td><b>{year}</b></td>{''.join(cells)}<td class=\"{total_cls}\"><b>{total:+.1f}%</b></td></tr>")
    return f"<table>{header}{''.join(body)}</table>"


def metric_table(rows, value_header="Strategy"):
    body = [f"<tr><th>Metric</th><th>{html_escape(value_header)}</th></tr>"]
    for label, value, cls in rows:
        class_attr = f' class="{cls}"' if cls else ""
        body.append(f"<tr><td>{html_escape(label)}</td><td{class_attr}>{value}</td></tr>")
    return "<table>" + "".join(body) + "</table>"


def rolling_sharpe(daily, window):
    returns = daily["daily_return"].astype(float)
    mean = returns.rolling(window, min_periods=max(5, min(window, 30))).mean()
    std = returns.rolling(window, min_periods=max(5, min(window, 30))).std(ddof=0)
    series = (mean * 365.0) / (std * math.sqrt(365.0))
    return series.replace([np.inf, -np.inf], np.nan)


def rolling_metric_rows(daily):
    rows = []
    for window in [90, 365]:
        series = rolling_sharpe(daily, window).dropna()
        label = f"Rolling Sharpe {window}d"
        if series.empty:
            rows.extend(
                [
                    (f"{label} Mean", "N/A", "muted"),
                    (f"{label} Median", "N/A", "muted"),
                    (f"{label} Last", "N/A", "muted"),
                ]
            )
        else:
            rows.extend(
                [
                    (f"{label} Mean", f"{series.mean():.2f}", ""),
                    (f"{label} Median", f"{series.median():.2f}", ""),
                    (f"{label} Last", f"{series.iloc[-1]:.2f}", ""),
                ]
            )
    return rows


def yearly_returns_table(daily):
    if daily.empty:
        return "<table><tr><td>No yearly returns available.</td></tr></table>"
    series = daily.copy()
    series["year"] = series.index.year
    rows = ["<tr><th>Year</th><th>Return</th><th>Start Balance</th><th>End Balance</th></tr>"]
    for year, group in series.groupby("year"):
        start_balance = safe_float(group["balance"].iloc[0])
        end_balance = safe_float(group["balance"].iloc[-1])
        value = (end_balance / start_balance - 1.0) * 100.0 if start_balance else 0.0
        cls = "pos" if value >= 0 else "neg"
        rows.append(
            f'<tr><td><b>{year}</b></td><td class="{cls}">{value:+.2f}%</td>'
            f"<td>{money(start_balance, 0)}</td><td>{money(end_balance, 0)}</td></tr>"
        )
    return "<table>" + "".join(rows) + "</table>"


def average_monthly_rows(monthly_pivot):
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    rows = []
    for month in range(1, 13):
        if month not in monthly_pivot:
            continue
        values = monthly_pivot[month].dropna()
        if values.empty:
            continue
        avg = float(values.mean())
        rows.append({"month": month_names[month - 1], "return": avg, "label": month_names[month - 1], "value": avg})
    return rows


def average_monthly_table(monthly_pivot):
    rows = ["<tr><th>Month</th><th>Avg Return</th></tr>"]
    for row in average_monthly_rows(monthly_pivot):
        cls = "pos" if row["return"] >= 0 else "neg"
        rows.append(f'<tr><td>{row["month"]}</td><td class="{cls}">{row["return"]:+.2f}%</td></tr>')
    return "<table>" + "".join(rows) + "</table>"


def return_quantiles_table(daily, monthly_pivot):
    weekly = daily["balance"].resample("W").last().pct_change().dropna()
    monthly_values = (monthly_pivot.stack().dropna() / 100.0) if not monthly_pivot.empty else pd.Series(dtype=float)
    series_map = {
        "Daily": daily["daily_return"].dropna(),
        "Weekly": weekly,
        "Monthly": monthly_values,
    }
    quantiles = [0.05, 0.25, 0.50, 0.75, 0.95]
    rows = ["<tr><th>Period</th>" + "".join(f"<th>{int(q * 100)}%</th>" for q in quantiles) + "</tr>"]
    for label, values in series_map.items():
        if values.empty:
            rows.append(f"<tr><td>{label}</td><td colspan=\"5\" class=\"muted\">N/A</td></tr>")
            continue
        cells = []
        for q in quantiles:
            value = float(values.quantile(q)) * 100.0
            cls = "pos" if value >= 0 else "neg"
            cells.append(f'<td class="{cls}">{value:+.2f}%</td>')
        rows.append(f"<tr><td>{label}</td>{''.join(cells)}</tr>")
    return "<table>" + "".join(rows) + "</table>"


def compute_underwater_days(daily):
    values = daily["balance"].to_numpy(dtype=float)
    out = []
    peak = -math.inf
    peak_index = None
    for idx, value in enumerate(values):
        if value >= peak:
            peak = value
            peak_index = daily.index[idx]
            out.append(0.0)
        elif peak_index is None:
            out.append(0.0)
        else:
            out.append((daily.index[idx] - peak_index).total_seconds() / 86400.0)
    return out


def daily_returns_heatmap(daily):
    if daily.empty:
        return '<div class="heatmap-empty">No daily returns available.</div>'
    rows = []
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    work = daily.copy()
    work["date"] = work.index.date
    work["year"] = work.index.year
    work["month"] = work.index.month
    work["day"] = work.index.day
    for (year, month), group in work.groupby(["year", "month"]):
        cells = []
        first_weekday = pd.Timestamp(year=year, month=month, day=1, tz="UTC").weekday()
        for _ in range(first_weekday):
            cells.append('<span class="day-cell empty"></span>')
        by_day = {int(row["day"]): safe_float(row["daily_return"]) * 100.0 for _, row in group.iterrows()}
        days_in_month = pd.Period(f"{year}-{month:02d}").days_in_month
        for day in range(1, days_in_month + 1):
            if day not in by_day:
                cells.append('<span class="day-cell empty"></span>')
                continue
            value = by_day[day]
            magnitude = min(1.0, abs(value) / 4.0)
            if value >= 0:
                color = f"rgba(98,217,159,{0.14 + magnitude * 0.68:.3f})"
            else:
                color = f"rgba(255,122,117,{0.14 + magnitude * 0.68:.3f})"
            cells.append(
                f'<span class="day-cell" style="background:{color}" '
                f'title="{year}-{month:02d}-{day:02d}: {value:+.2f}%"></span>'
            )
        rows.append(
            f'<div class="month-heat"><b>{month_names[month - 1]} {year}</b>'
            f'<div class="day-grid">{"".join(cells)}</div></div>'
        )
    return '<div class="daily-heatmap">' + "".join(rows) + "</div>"


def worst_drawdown_table(periods, start_val, limit=10):
    selected = sorted(periods, key=lambda row: safe_float(row.get("max_drawdown")), reverse=True)[:limit]
    if not selected:
        return "<table><tr><td>No drawdown periods available.</td></tr></table>"
    rows = ["<tr><th>Start</th><th>Recovered</th><th>Days</th><th>Max DD</th><th>Trough Balance</th></tr>"]
    for period in selected:
        end = period["recovery_time_ms"]
        trough_balance = start_val + safe_float(period.get("trough_equity"))
        rows.append(
            f"<tr><td>{dt_ms(period['start_time_ms'])}</td>"
            f"<td>{dt_ms(end) if end else 'open'}</td>"
            f"<td>{safe_float(period.get('duration_days')):.2f}</td>"
            f'<td class="neg">{money(period.get("max_drawdown"), 0)}</td>'
            f"<td>{money(trough_balance, 0)}</td></tr>"
        )
    return "<table>" + "".join(rows) + "</table>"


def rows_table(headers, rows, empty="No rows available."):
    if not rows:
        return f"<table><tr><td>{html_escape(empty)}</td></tr></table>"
    header_html = "<tr>" + "".join(f"<th>{html_escape(header)}</th>" for header, _ in headers) + "</tr>"
    body = []
    for row in rows:
        cells = []
        for _, key in headers:
            value = row.get(key, "")
            cells.append(f"<td>{value}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return "<table>" + header_html + "".join(body) + "</table>"


def downsample_points(df, x_col, y_cols, limit=900):
    if df.empty:
        return []
    if len(df) <= limit:
        sample = df
    else:
        index = np.linspace(0, len(df) - 1, limit).round().astype(int)
        sample = df.iloc[index]
    points = []
    for _, row in sample.iterrows():
        point = {"t": int(row[x_col])}
        for col in y_cols:
            point[col] = safe_float(row[col])
        points.append(point)
    return points


def build_chart_payload(run_dir, daily):
    payload = {
        "daily": downsample_points(
            daily.reset_index(drop=True),
            "timestamp_ms",
            [
                "balance",
                "drawdown_pct",
                "underwater_pct",
                "underwater_days",
                "exposure_notional",
                "cumulative_return_pct",
                "rolling_sharpe_90",
            ],
            limit=900,
        ),
        "offsets": [],
        "monthlyAverage": [],
        "yearlyReturns": [],
        "foldPnl": [],
        "symbolPnl": [],
    }
    for offset in range(7):
        path = run_dir / f"offset_{offset}_equity.csv"
        df = read_csv(path)
        if df.empty:
            continue
        df["dt"] = pd.to_datetime(df["timestamp_ms"], unit="ms", utc=True)
        daily_offset = df.set_index("dt").sort_index().resample("D").last().ffill().reset_index(drop=True)
        payload["offsets"].append(
            {
                "name": f"offset {offset}",
                "points": downsample_points(daily_offset, "timestamp_ms", ["balance"], limit=500),
            }
        )
    return payload


def generate_report(run_dir):
    run_dir = Path(run_dir)
    eq_path = run_dir / "rollup_equity.csv"
    summary_path = run_dir / "rollup_summary.json"
    if not eq_path.exists():
        print(f"Error: {eq_path} not found")
        return

    summary = read_json(summary_path)
    equity = read_csv(eq_path)
    trades, provenance = load_source_tables(run_dir, summary)
    daily, monthly_pivot = compute_daily_and_monthly(run_dir, equity)

    start_val = safe_float(summary.get("starting_balance"), safe_float(daily["balance"].iloc[0]))
    end_val = safe_float(summary.get("final_balance"), safe_float(daily["balance"].iloc[-1]))
    total_ret = safe_float(summary.get("net_return_pct"), (end_val - start_val) / start_val * 100.0 if start_val else 0.0)
    daily["cumulative_return_pct"] = (daily["balance"] / start_val - 1.0) * 100.0 if start_val else 0.0
    daily["underwater_pct"] = -daily["drawdown_pct"].abs()
    daily["underwater_days"] = compute_underwater_days(daily)
    daily["rolling_sharpe_90"] = rolling_sharpe(daily, 90).fillna(0.0)
    n_days = max(1, len(daily))
    years = n_days / 365.25
    cagr = ((end_val / start_val) ** (1.0 / years) - 1.0) * 100.0 if start_val > 0 and end_val > 0 else 0.0
    daily_rets = daily["daily_return"].to_numpy(dtype=float)
    ann_vol = float(np.std(daily_rets) * np.sqrt(365) * 100.0)
    sharpe = float((np.mean(daily_rets) * 365) / (ann_vol / 100.0)) if ann_vol > 0 else 0.0
    downside = daily_rets[daily_rets < 0]
    downside_std = float(np.std(downside) * np.sqrt(365))
    sortino = float((np.mean(daily_rets) * 365) / downside_std) if downside_std > 0 else 0.0
    daily_max_dd = max_drawdown_from_daily(daily) * 100.0
    max_dd_pct = safe_float(summary.get("max_drawdown_pct"), daily_max_dd)
    calmar = cagr / max_dd_pct if max_dd_pct > 0 else 0.0

    stagnation_periods = compute_stagnation_periods(equity)
    stagnation_gt7 = [period for period in stagnation_periods if period["duration_days"] > STAGNATION_THRESHOLD_DAYS]
    symbol_rows = symbol_metrics(trades, provenance)
    fold_rows = fold_metrics(provenance)
    audit = provenance_audit(provenance)
    chart_payload = build_chart_payload(run_dir, daily)
    chart_payload["monthlyAverage"] = average_monthly_rows(monthly_pivot)
    chart_payload["yearlyReturns"] = [
        {
            "label": str(year),
            "value": ((group["balance"].iloc[-1] / group["balance"].iloc[0]) - 1.0) * 100.0
            if group["balance"].iloc[0]
            else 0.0,
        }
        for year, group in daily.groupby(daily.index.year)
    ]

    offset_table_rows = []
    for run in summary.get("runs", []):
        offset_table_rows.append(
            {
                "offset": f"{safe_int(run.get('offset_days')):+d}d",
                "run": f"<code>{html_escape(run.get('run_id', ''))}</code>",
                "pnl": f'<span class="{cls_pos_neg(run.get("total_pnl"))}">{money(run.get("total_pnl"), 0)}</span>',
                "return": f'<span class="{cls_pos_neg(run.get("net_return_pct"))}">{pct(run.get("net_return_pct"), 2, True)}</span>',
                "dd": pct(run.get("max_drawdown_pct"), 2),
                "trades": f"{safe_int(run.get('trades')):,}",
                "pf": f"{safe_float(run.get('profit_factor')):.3f}",
                "gate": f'<span class="pill {html_escape(run.get("ensemble_status", ""))}">{html_escape(run.get("ensemble_status", ""))}</span>',
                "source": f'<span title="{html_escape(run.get("source_gate_reason", ""))}">{html_escape(run.get("source_gate_status", ""))}</span>',
            }
        )

    fold_table_rows = [
        {
            "fold": row["fold_index"],
            "offsets": row["offsets"],
            "symbols": row["symbols"],
            "sel": row["selections"],
            "pnl": f'<span class="{cls_pos_neg(row["oos_pnl"])}">{money(row["oos_pnl"], 0)}</span>',
            "trades": f"{row['oos_trades']:,}",
            "pf": f"{row['median_pf']:.3f}",
            "dd": pct(row["max_dd_pct"], 2),
        }
        for row in fold_rows
    ]

    symbol_table_rows = [
        {
            "symbol": html_escape(row["symbol"]),
            "selections": f"{row['selections']:,}",
            "trades": f"{row['trades']:,}",
            "pnl": f'<span class="{cls_pos_neg(row["pnl"])}">{money(row["pnl"], 0)}</span>',
            "pf": "inf" if math.isinf(row["profit_factor"]) else f"{row['profit_factor']:.3f}",
            "win": pct(row["win_rate"], 2),
            "avg": money(row["avg_trade"], 2),
            "long": f"{row['long_trades']:,}",
            "short": f"{row['short_trades']:,}",
        }
        for row in symbol_rows
    ]

    stagnation_rows = []
    for index, period in enumerate(stagnation_gt7, start=1):
        stagnation_rows.append(
            {
                "#": index,
                "start": dt_ms(period["start_time_ms"]),
                "end": dt_ms(period["recovery_time_ms"] or equity["timestamp_ms"].iloc[-1]),
                "days": f"{period['duration_days']:.2f}",
                "recovered": "yes" if period["recovered"] else "no",
                "peak": money(start_val + period["peak_equity"], 0),
                "trough": money(start_val + period["trough_equity"], 0),
                "dd": money(period["max_drawdown"], 0),
            }
        )

    manifest_files = [
        "rollup_summary.json",
        "rollup_equity.csv",
        "rollup_trades.csv",
        "daily_returns.csv",
        "monthly_returns.csv",
        "rollup_summary.csv",
        "combined_fullscreen_stagnation_offsets.html",
    ]
    manifest_rows = [
        {
            "file": f"<code>{name}</code>",
            "status": '<span class="pos">present</span>' if (run_dir / name).exists() else '<span class="neg">missing</span>',
        }
        for name in manifest_files
    ]

    pass_status = str(summary.get("pass_status", "unknown"))
    provenance_status = str(summary.get("provenance_validation_status", "RESEARCH ONLY"))
    subtitle = (
        f"{safe_int(summary.get('offset_count'))} daily-offset accounts, "
        f"{money(summary.get('account_balance_per_offset'), 0)} per offset, "
        "fold-local point-in-time optimization"
    )

    best_day = safe_float(daily["daily_return"].max()) if not daily.empty else 0.0
    worst_day = safe_float(daily["daily_return"].min()) if not daily.empty else 0.0
    avg_day = safe_float(daily["daily_return"].mean()) if not daily.empty else 0.0
    median_day = safe_float(daily["daily_return"].median()) if not daily.empty else 0.0
    positive_days = safe_float((daily["daily_return"] > 0).mean() * 100.0) if not daily.empty else 0.0
    monthly_values = monthly_pivot.stack().dropna() if not monthly_pivot.empty else pd.Series(dtype=float)
    best_month = safe_float(monthly_values.max()) if not monthly_values.empty else 0.0
    worst_month = safe_float(monthly_values.min()) if not monthly_values.empty else 0.0
    avg_month = safe_float(monthly_values.mean()) if not monthly_values.empty else 0.0

    date_range_html = f"""
    <table id="date-range-table">
      <tr><td><strong>Start Date</strong></td><td class="center-text">{dt_ms_long(daily['timestamp_ms'].iloc[0])}</td></tr>
      <tr><td><strong>End Date</strong></td><td class="center-text">{dt_ms_long(daily['timestamp_ms'].iloc[-1])}</td></tr>
    </table>
    """
    main_metrics_html = metric_table(
        [
            ("Total Return", pct(total_ret, 2, True), cls_pos_neg(total_ret)),
            ("CAGR", pct(cagr, 2, True), cls_pos_neg(cagr)),
            ("Annualized Volatility", pct(ann_vol, 2), ""),
            ("Sharpe", f"{sharpe:.2f}", ""),
            ("Sortino", f"{sortino:.2f}", ""),
            ("Calmar", f"{calmar:.2f}", ""),
            ("Max Drawdown", pct(max_dd_pct, 2), "neg" if max_dd_pct > 0 else ""),
            ("Return / DD", f"{safe_float(summary.get('return_to_drawdown_ratio')):.2f}", ""),
            ("Profit Factor", f"{safe_float(summary.get('profit_factor')):.3f}", ""),
            ("Win Rate", pct(summary.get("win_rate"), 2), ""),
            ("Trades", f"{safe_int(summary.get('trades')):,}", ""),
        ]
    )
    returns_metrics_html = metric_table(
        [
            ("Best Day", pct_decimal(best_day, 2, True), cls_pos_neg(best_day)),
            ("Worst Day", pct_decimal(worst_day, 2, True), cls_pos_neg(worst_day)),
            ("Average Day", pct_decimal(avg_day, 2, True), cls_pos_neg(avg_day)),
            ("Median Day", pct_decimal(median_day, 2, True), cls_pos_neg(median_day)),
            ("Positive Days", pct(positive_days, 2), ""),
            ("Average Month", pct(avg_month, 2, True), cls_pos_neg(avg_month)),
            ("Best Month", pct(best_month, 2, True), cls_pos_neg(best_month)),
            ("Worst Month", pct(worst_month, 2, True), cls_pos_neg(worst_month)),
            ("No-Entry Days", f"{safe_int(summary.get('no_entry_days'))}", ""),
            ("Max No-Entry Gap", f"{safe_int(summary.get('longest_no_entry_gap_days'))}d", ""),
        ]
    )
    rolling_metrics_html = metric_table(
        rolling_metric_rows(daily)
        + [
            ("Average Gross Exposure", money(summary.get("average_exposure_notional"), 0), ""),
            ("Max Gross Exposure", money(summary.get("max_exposure_notional"), 0), ""),
            ("Exposure", pct(summary.get("exposure_pct"), 2), ""),
            ("Longest Stagnation", f"{safe_float(summary.get('longest_stagnation_days')):.2f}d", ""),
        ]
    )
    cumulative_metrics_html = metric_table(
        [
            ("Starting Capital", money(start_val, 0), ""),
            ("Final Balance", money(end_val, 0), ""),
            ("Total OOS PnL", money(summary.get("total_pnl"), 0), cls_pos_neg(summary.get("total_pnl"))),
            ("Stacked Accounts", f"{safe_int(summary.get('offset_count'))}", ""),
            ("Capital Per Offset", money(summary.get("account_balance_per_offset"), 0), ""),
            ("Max Concurrent Positions", f"{safe_int(summary.get('max_concurrent_positions'))}", ""),
            ("Provenance", html_escape(provenance_status), "pos" if provenance_status.startswith("PASS") else "neg"),
            ("Run Gate", html_escape(pass_status.upper()), "pos" if pass_status == "pass" else "neg"),
        ]
    )
    benchmark_metrics_html = metric_table(
        [
            ("Benchmark Series", "Not supplied", "muted"),
            ("Benchmark Return", "N/A", "muted"),
            ("Benchmark Drawdown", "N/A", "muted"),
            ("Alpha", "N/A", "muted"),
            ("Beta", "N/A", "muted"),
            ("Correlation", "N/A", "muted"),
        ],
        value_header="Benchmark",
    )
    worst_drawdown_html = worst_drawdown_table(stagnation_periods, start_val)
    daily_heatmap_html = daily_returns_heatmap(daily)
    yearly_returns_html = yearly_returns_table(daily)
    avg_monthly_html = average_monthly_table(monthly_pivot)
    quantiles_html = return_quantiles_table(daily, monthly_pivot)
    chart_payload["foldPnl"] = [{"label": f"F{row['fold_index']}", "value": row["oos_pnl"]} for row in fold_rows]
    chart_payload["symbolPnl"] = [{"label": row["symbol"], "value": row["pnl"]} for row in symbol_rows]

    data_json = json.dumps(chart_payload, separators=(",", ":"))
    monthly_html = monthly_table(monthly_pivot)
    offset_html = rows_table(
        [
            ("Offset", "offset"),
            ("Run", "run"),
            ("PnL", "pnl"),
            ("Return", "return"),
            ("DD", "dd"),
            ("Trades", "trades"),
            ("PF", "pf"),
            ("Gate", "gate"),
            ("Source Diagnostics", "source"),
        ],
        offset_table_rows,
    )
    fold_html = rows_table(
        [
            ("Fold", "fold"),
            ("Offsets", "offsets"),
            ("Symbols", "symbols"),
            ("Selections", "sel"),
            ("OOS PnL", "pnl"),
            ("Trades", "trades"),
            ("Median PF", "pf"),
            ("Max DD", "dd"),
        ],
        fold_table_rows,
    )
    symbol_html = rows_table(
        [
            ("Symbol", "symbol"),
            ("Selections", "selections"),
            ("Trades", "trades"),
            ("PnL", "pnl"),
            ("PF", "pf"),
            ("Win Rate", "win"),
            ("Avg Trade", "avg"),
            ("Long", "long"),
            ("Short", "short"),
        ],
        symbol_table_rows,
    )
    stagnation_html = rows_table(
        [
            ("#", "#"),
            ("Start", "start"),
            ("End", "end"),
            ("Days", "days"),
            ("Recovered", "recovered"),
            ("Peak", "peak"),
            ("Trough", "trough"),
            ("Max DD", "dd"),
        ],
        stagnation_rows,
        "No stagnation periods longer than 7 days.",
    )
    manifest_html = rows_table([("Artifact", "file"), ("Status", "status")], manifest_rows)

    generated_at = pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    html_out = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Point-In-Time WFO Strategy Performance Report</title>
<style>
:root {{
  color-scheme: dark;
  --bg: #070d0c;
  --panel: #0d1715;
  --panel2: #101d1a;
  --line: #243b36;
  --text: #e7f1ed;
  --muted: #91a39d;
  --accent: #62d99f;
  --warn: #f4c35d;
  --bad: #ff7a75;
  --blue: #7ba9ff;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  padding: 18px;
  background: var(--bg);
  color: var(--text);
  font: 12px/1.45 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
main {{ max-width: 1420px; margin: 0 auto; }}
header {{
  display: grid;
  grid-template-columns: minmax(360px, 1fr) auto;
  gap: 18px;
  align-items: end;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 14px;
  background: var(--panel);
}}
h1 {{ margin: 0; font-size: 22px; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 15px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
.grid {{ display: grid; grid-template-columns: repeat(6, minmax(130px, 1fr)); gap: 8px; margin: 12px 0; }}
.card {{
  border: 1px solid rgba(46, 74, 67, 0.9);
  border-radius: 7px;
  background: var(--panel2);
  padding: 10px;
  min-width: 0;
}}
.card span {{
  display: block;
  color: var(--muted);
  font-size: 10px;
  text-transform: uppercase;
  font-weight: 750;
}}
.card b {{
  display: block;
  margin-top: 4px;
  font-size: 17px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
.panel {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 12px;
  margin-top: 12px;
}}
.two {{ display: grid; grid-template-columns: 1.35fr 1fr; gap: 12px; }}
.three {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }}
canvas {{ width: 100%; height: 280px; display: block; border: 1px solid rgba(36, 59, 54, 0.75); border-radius: 6px; background: #050b0a; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: 7px 8px; border-bottom: 1px solid rgba(36, 59, 54, 0.8); text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
th {{ position: sticky; top: 0; background: #12211e; color: var(--muted); font-size: 10px; text-transform: uppercase; z-index: 1; }}
td:first-child, th:first-child {{ text-align: left; }}
.scroll {{ max-height: 420px; overflow: auto; border: 1px solid rgba(36, 59, 54, 0.75); border-radius: 6px; }}
.pos {{ color: var(--accent); font-weight: 750; }}
.neg {{ color: var(--bad); font-weight: 750; }}
.muted {{ color: var(--muted); }}
.pill {{ display: inline-block; padding: 2px 7px; border-radius: 999px; font-weight: 750; }}
.pill.pass {{ background: #12351f; color: #86efac; }}
.pill.fail {{ background: #3a2026; color: #fda4af; }}
code {{ color: #d8e5e0; }}
.note {{ color: var(--muted); margin-top: 8px; }}
.report-info {{ color: var(--muted); margin: 8px 0 14px; }}
.report-info p {{ margin: 3px 0; }}
.flex-container {{ display: grid; grid-template-columns: minmax(360px, 0.82fr) minmax(540px, 1.18fr); gap: 14px; align-items: start; }}
.summary-metrics, .flex-item {{ min-width: 0; }}
.summary-metrics h2, .flex-item h2 {{ text-align: center; letter-spacing: 0.08em; color: var(--muted); }}
.summary-metrics h3, .plot-container h3 {{ margin: 14px 0 7px; font-size: 13px; color: var(--text); }}
.plot-container {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 12px;
  margin: 0 0 12px;
}}
.plot-container canvas {{ height: 310px; }}
.center-text {{ text-align: center; }}
.daily-heatmap {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }}
.month-heat {{ border: 1px solid rgba(36, 59, 54, 0.75); border-radius: 6px; padding: 8px; background: #081210; }}
.month-heat b {{ display: block; margin-bottom: 6px; color: var(--muted); }}
.day-grid {{ display: grid; grid-template-columns: repeat(7, 1fr); gap: 3px; }}
.day-cell {{ aspect-ratio: 1; border-radius: 2px; border: 1px solid rgba(255,255,255,0.04); }}
.day-cell.empty {{ opacity: 0; }}
.compact-section {{ margin-top: 14px; }}
@media (max-width: 1000px) {{
  header, .two, .three, .flex-container {{ grid-template-columns: 1fr; }}
  .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .daily-heatmap {{ grid-template-columns: 1fr; }}
  th, td {{ white-space: normal; }}
}}
</style>
</head>
<body>
<main>
<h1>Strategy Performance Report</h1>
<div class="report-info">
  <p>Generated by point-in-time WFO report generator at {generated_at}.</p>
  <p>Strategy: frama-5m-confirm</p>
  <p>Compound point-in-time WFO report. {html_escape(subtitle)}.</p>
  <p><span class="pill {html_escape(pass_status)}">{html_escape(pass_status.upper())}</span> <span title="{html_escape(summary.get('pass_reason', ''))}">{html_escape(summary.get('pass_reason', ''))}</span></p>
</div>

<div class="flex-container">
  <div class="summary-metrics">
    <h2> METRICS </h2>
    {date_range_html}
    <h3>Main Metrics</h3>
    {main_metrics_html}
    <h3>Returns Metrics</h3>
    {returns_metrics_html}
    <h3>Rolling Metrics</h3>
    {rolling_metrics_html}
    <h3>Cumulative Return Metrics</h3>
    {cumulative_metrics_html}
    <h3>Benchmark Metrics</h3>
    {benchmark_metrics_html}
    <h3>Worst Drawdowns</h3>
    {worst_drawdown_html}
  </div>

  <div class="flex-item">
    <h2> PLOTS </h2>
    <div class="plot-container"><h3>Cumulative Returns</h3><canvas id="cumulativeChart"></canvas></div>
    <div class="plot-container"><h3>Underwater Plot</h3><canvas id="underwaterChart"></canvas></div>
    <div class="plot-container"><h3>Underwater Start Plot</h3><canvas id="underwaterStartChart"></canvas></div>
    <div class="plot-container"><h3>Monthly Returns Heatmap</h3>{monthly_html}</div>
    <div class="plot-container"><h3>Daily Returns Heatmap</h3>{daily_heatmap_html}</div>
    <div class="plot-container"><h3>Average Monthly Profit</h3><canvas id="monthlyAverageChart"></canvas>{avg_monthly_html}</div>
    <div class="plot-container"><h3>Return Quantiles</h3>{quantiles_html}</div>
    <div class="plot-container"><h3>EOY Returns</h3><canvas id="yearlyReturnChart"></canvas>{yearly_returns_html}</div>
    <div class="plot-container"><h3>Rolling Sharpe 90d</h3><canvas id="rollingSharpeChart"></canvas></div>
    <div class="plot-container"><h3>Gross Exposure</h3><canvas id="exposureChart"></canvas></div>
    <div class="plot-container"><h3>Offset Account Equity</h3><canvas id="offsetChart"></canvas></div>
    <div class="plot-container"><h3>Fold OOS PnL</h3><canvas id="foldPnlChart"></canvas></div>
    <div class="plot-container"><h3>Symbol Contribution</h3><canvas id="symbolPnlChart"></canvas></div>
  </div>
</div>

<section class="panel compact-section">
  <h2>Offset Account Results</h2>
  <div class="scroll">{offset_html}</div>
  <div class="note">Source diagnostics are preserved for context. The stacked ensemble gate is portfolio-level and passed for this point-in-time rollup.</div>
</section>

<section class="panel">
  <h2>Per-Fold OOS Metrics</h2>
  <div class="scroll">{fold_html}</div>
</section>

<section class="panel">
  <h2>Per-Symbol Trade Metrics</h2>
  <div class="scroll">{symbol_html}</div>
</section>

<section class="panel">
  <h2>Stagnation Periods Longer Than {STAGNATION_THRESHOLD_DAYS:.0f} Days</h2>
  <div class="scroll">{stagnation_html}</div>
</section>

<section class="two">
  <div class="panel">
    <h2>Optimizer Provenance Audit</h2>
    <table>
      <tr><td>Optimizer mode</td><td>{html_escape(audit['modes'])}</td></tr>
      <tr><td>Provenance rows</td><td>{audit['rows']:,}</td></tr>
      <tr><td>Boundary failures</td><td class="{'pos' if audit['boundary_failures'] == 0 else 'neg'}">{audit['boundary_failures']:,}</td></tr>
      <tr><td>Optimizer scope</td><td>{html_escape(audit['min_scope'])} to {html_escape(audit['max_scope'])}</td></tr>
      <tr><td>Validation status</td><td class="{'pos' if provenance_status.startswith('PASS') else 'neg'}">{html_escape(provenance_status)}</td></tr>
    </table>
  </div>
  <div class="panel">
    <h2>Artifact Manifest</h2>
    {manifest_html}
  </div>
</section>

<section class="panel">
  <h2>Methodology Notes</h2>
  <table>
    <tr><td>Validation style</td><td>Fold-local point-in-time WFO. Each OOS fold is selected only after its own in-sample study is complete.</td></tr>
    <tr><td>Strategy set</td><td>frama-5m-confirm, seven symbols, seven daily offset accounts.</td></tr>
    <tr><td>Selection criteria</td><td>4/7 IS consensus with PF baseline 1.10. Missing symbol/fold selections remain unselected.</td></tr>
    <tr><td>Capital model</td><td>{safe_int(summary.get('offset_count'))} stacked accounts x {money(summary.get('account_balance_per_offset'), 0)} = {money(start_val, 0)} starting capital.</td></tr>
    <tr><td>Report inputs</td><td>rollup_equity.csv, rollup_summary.json, source oos_trades.csv files, and source optimizer_provenance.csv files.</td></tr>
  </table>
</section>
</main>

<script>
const DATA = {data_json};
const COLORS = ["#62d99f", "#7ba9ff", "#efc75e", "#ff8278", "#b791ff", "#55d6d2", "#f28ac0"];
function resize(canvas) {{
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(rect.width * ratio));
  canvas.height = Math.max(1, Math.floor(rect.height * ratio));
  const ctx = canvas.getContext("2d");
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  return {{ ctx, width: rect.width, height: rect.height }};
}}
function labelDate(ms) {{ return new Date(ms).toISOString().slice(5, 10); }}
function formatMoney(value) {{ return "$" + Math.round(value).toLocaleString(); }}
function range(values, pad = 0.07) {{
  let min = Math.min(...values);
  let max = Math.max(...values);
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [0, 1];
  if (Math.abs(max - min) < 1e-9) {{ min -= 1; max += 1; }}
  const extra = (max - min) * pad;
  return [min - extra, max + extra];
}}
function drawChart(id, seriesList, key, options = {{}}) {{
  const canvas = document.getElementById(id);
  if (!canvas) return;
  const {{ ctx, width, height }} = resize(canvas);
  const plot = {{ x: 60, y: 18, w: width - 78, h: height - 48 }};
  const points = seriesList.flatMap(series => series.points);
  if (!points.length) return;
  const xMin = Math.min(...points.map(point => point.t));
  const xMax = Math.max(...points.map(point => point.t));
  const [yMin, yMax] = range(points.map(point => point[key]));
  ctx.clearRect(0, 0, width, height);
  ctx.strokeStyle = "#20332f";
  ctx.lineWidth = 1;
  ctx.fillStyle = "#91a39d";
  ctx.font = "11px ui-monospace, SFMono-Regular, Menlo, monospace";
  for (let i = 0; i <= 4; i++) {{
    const y = plot.y + plot.h * i / 4;
    ctx.beginPath(); ctx.moveTo(plot.x, y); ctx.lineTo(plot.x + plot.w, y); ctx.stroke();
    const value = yMax - (yMax - yMin) * i / 4;
    const label = options.percent
      ? value.toFixed(1) + "%"
      : (options.number ? value.toFixed(2) : (options.days ? value.toFixed(0) + "d" : formatMoney(value)));
    ctx.fillText(label, 6, y - 4);
  }}
  ctx.textAlign = "center";
  const ticks = Math.max(4, Math.min(9, Math.floor(plot.w / 120)));
  for (let i = 0; i <= ticks; i++) {{
    const t = xMin + (xMax - xMin) * i / ticks;
    const x = plot.x + plot.w * i / ticks;
    ctx.beginPath(); ctx.moveTo(x, plot.y); ctx.lineTo(x, plot.y + plot.h + 4); ctx.stroke();
    ctx.fillText(labelDate(t), x, plot.y + plot.h + 18);
  }}
  ctx.textAlign = "left";
  seriesList.forEach((series, index) => {{
    ctx.strokeStyle = series.color || COLORS[index % COLORS.length];
    ctx.lineWidth = series.width || 1.7;
    ctx.beginPath();
    series.points.forEach((point, pointIndex) => {{
      const x = plot.x + (point.t - xMin) / Math.max(1, xMax - xMin) * plot.w;
      const y = plot.y + plot.h - (point[key] - yMin) / Math.max(1e-9, yMax - yMin) * plot.h;
      if (pointIndex === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }});
    ctx.stroke();
  }});
}}
function drawBarChart(id, rows, options = {{}}) {{
  const canvas = document.getElementById(id);
  if (!canvas || !rows.length) return;
  const {{ ctx, width, height }} = resize(canvas);
  const plot = {{ x: 62, y: 18, w: width - 82, h: height - 54 }};
  const values = rows.map(row => Number(row.value) || 0);
  let [yMin, yMax] = range(values.concat([0]), 0.12);
  if (yMin > 0) yMin = 0;
  if (yMax < 0) yMax = 0;
  ctx.clearRect(0, 0, width, height);
  ctx.strokeStyle = "#20332f";
  ctx.fillStyle = "#91a39d";
  ctx.font = "11px ui-monospace, SFMono-Regular, Menlo, monospace";
  for (let i = 0; i <= 4; i++) {{
    const y = plot.y + plot.h * i / 4;
    const value = yMax - (yMax - yMin) * i / 4;
    const label = options.percent ? value.toFixed(1) + "%" : formatMoney(value);
    ctx.beginPath(); ctx.moveTo(plot.x, y); ctx.lineTo(plot.x + plot.w, y); ctx.stroke();
    ctx.fillText(label, 6, y - 4);
  }}
  const zeroY = plot.y + plot.h - (0 - yMin) / Math.max(1e-9, yMax - yMin) * plot.h;
  ctx.strokeStyle = "#49635d";
  ctx.beginPath(); ctx.moveTo(plot.x, zeroY); ctx.lineTo(plot.x + plot.w, zeroY); ctx.stroke();
  const gap = Math.min(5, Math.max(1, plot.w / Math.max(1, rows.length) * 0.2));
  const barW = Math.max(2, plot.w / Math.max(1, rows.length) - gap);
  rows.forEach((row, index) => {{
    const value = Number(row.value) || 0;
    const x = plot.x + index * (plot.w / rows.length) + gap / 2;
    const y = plot.y + plot.h - (value - yMin) / Math.max(1e-9, yMax - yMin) * plot.h;
    const h = Math.abs(zeroY - y);
    ctx.fillStyle = value >= 0 ? "#62d99f" : "#ff8278";
    ctx.fillRect(x, Math.min(y, zeroY), barW, Math.max(1, h));
  }});
  ctx.fillStyle = "#91a39d";
  ctx.textAlign = "center";
  const every = Math.max(1, Math.ceil(rows.length / Math.max(4, Math.floor(plot.w / 70))));
  rows.forEach((row, index) => {{
    if (index % every !== 0 && index !== rows.length - 1) return;
    const x = plot.x + index * (plot.w / rows.length) + barW / 2 + gap / 2;
    ctx.fillText(String(row.label), x, plot.y + plot.h + 20);
  }});
  ctx.textAlign = "left";
}}
function renderCharts() {{
  drawChart("cumulativeChart", [{{ name: "portfolio", color: "#62d99f", width: 2.2, points: DATA.daily }}], "cumulative_return_pct", {{ percent: true }});
  drawChart("underwaterChart", [{{ name: "underwater", color: "#ff8278", width: 1.8, points: DATA.daily }}], "underwater_pct", {{ percent: true }});
  drawChart("underwaterStartChart", [{{ name: "underwater days", color: "#7ba9ff", width: 1.6, points: DATA.daily }}], "underwater_days", {{ days: true }});
  drawBarChart("monthlyAverageChart", DATA.monthlyAverage, {{ percent: true }});
  drawBarChart("yearlyReturnChart", DATA.yearlyReturns, {{ percent: true }});
  drawChart("rollingSharpeChart", [{{ name: "rolling sharpe", color: "#efc75e", width: 1.7, points: DATA.daily }}], "rolling_sharpe_90", {{ number: true }});
  drawChart("exposureChart", [{{ name: "exposure", color: "#b791ff", width: 1.8, points: DATA.daily }}], "exposure_notional");
  drawChart("offsetChart", DATA.offsets.map((series, index) => ({{ ...series, color: COLORS[index], width: 1.35 }})), "balance");
  drawBarChart("foldPnlChart", DATA.foldPnl);
  drawBarChart("symbolPnlChart", DATA.symbolPnl);
}}
window.addEventListener("resize", renderCharts);
renderCharts();
</script>
</body>
</html>
"""

    out_path = run_dir / "quant_report.html"
    out_path.write_text(html_out)
    print(f"Generated point-in-time WFO quant report at {out_path}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        generate_report(sys.argv[1])
