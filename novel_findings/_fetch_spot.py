"""Fetch real Binance SPOT daily klines for SOL/BTC/ETH — to use as the spot reference for perp-basis trading."""
import urllib.request, json, time, os
import pandas as pd

OUT = "sol_data_cache/SPOT_BINANCE_NOVELFINDINGS.json"

def fetch_klines(symbol, interval="1d", start_str="2022-06-01", end_str="2026-07-22"):
    url = "https://api.binance.com/api/v3/klines"
    start_ms = int(pd.Timestamp(start_str).timestamp() * 1000)
    end_ms   = int(pd.Timestamp(end_str).timestamp() * 1000)
    all_rows = []
    cur = start_ms
    for _ in range(50):
        params = f"?symbol={symbol}&interval={interval}&startTime={cur}&endTime={end_ms}&limit=1000"
        req = urllib.request.Request(url + params, headers={"User-Agent":"Mozilla/5.0"})
        try:
            r = urllib.request.urlopen(req, timeout=20)
            data = json.loads(r.read())
        except Exception as e:
            time.sleep(2)
            try:
                r = urllib.request.urlopen(req, timeout=30)
                data = json.loads(r.read())
            except Exception:
                break
        if not data: break
        all_rows.extend(data)
        last_open = data[-1][0]
        if last_open <= cur: break
        cur = last_open + 1
        if len(data) < 1000: break
        time.sleep(0.4)
    df = pd.DataFrame(all_rows, columns=["openTime","open","high","low","close","volume",
                                          "closeTime","qav","trades","tbb","tbq","ign"])
    df["timestamp"] = pd.to_datetime(df["openTime"], unit="ms")
    for c in ["open","high","low","close","volume"]:
        df[c] = df[c].astype(float)
    df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return df[["timestamp","open","high","low","close","volume"]]

out = {}
for sym in ["SOLUSDT", "BTCUSDT", "ETHUSDT"]:
    print(f"Fetching {sym} spot daily...")
    df = fetch_klines(sym)
    print(f"  got {len(df)} bars: {df['timestamp'].min()} -> {df['timestamp'].max()}")
    out[sym] = df.to_dict("records")
    time.sleep(0.5)

json.dump(out, open(OUT, "w"))
print(f"Wrote {OUT}")
