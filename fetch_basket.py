"""Fetch REAL multi-timescale basket: daily + 1h + 8h funding for ~24 coins (Binance fapi).

Honest scope: 1m->1d real bars (NO 1s — not cached, infeasible to backtest honestly).
Polite rate limiting + retry on 429. Caches per (coin, tf). Run in background.
"""
import json, os, time
import pandas as pd, requests

KL = "https://fapi.binance.com/fapi/v1/klines"
FR = "https://fapi.binance.com/fapi/v1/fundingRate"
BASKET = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "LINK", "DOT",
          "LTC", "BCH", "ATOM", "UNI", "NEAR", "APT", "ARB", "OP", "INJ", "FIL",
          "AAVE", "MKR", "SUI", "TIA"]
CACHE = "sol_data_cache"


def _get(url, params, attempts=6):
    for a in range(attempts):
        try:
            r = requests.get(url, params=params, timeout=20)
            if r.status_code == 429:
                time.sleep(5 * (a + 1)); continue
            return r.json()
        except Exception:
            time.sleep(3 * (a + 1))
    return None


def fetch_klines(sym, interval, days):
    path = f"{CACHE}/BASKET_{sym}_{interval}.json"
    if os.path.exists(path):
        return len(json.load(open(path)))
    start = int((time.time() - days * 86400) * 1000); out = []; cur = start
    while cur < time.time() * 1000:
        d = _get(KL, {"symbol": sym, "interval": interval, "startTime": cur, "limit": 1500})
        if not d: break
        out.extend(d); cur = d[-1][0] + ({"1m":60000,"1h":3600000,"1d":86400000}[interval])
    if not out: return 0
    rows = [{"timestamp": pd.Timestamp(k[0], unit="ms").isoformat(),
             "open": float(k[1]), "high": float(k[2]), "low": float(k[3]),
             "close": float(k[4]), "volume": float(k[5])} for k in out]
    json.dump(rows, open(path, "w"))
    return len(rows)


def fetch_funding(sym, days=1100):
    path = f"{CACHE}/BASKET_{sym}_FUNDING.json"
    if os.path.exists(path):
        return len(json.load(open(path)))
    start = int((time.time() - days * 86400) * 1000); out = []; cur = start
    while cur < time.time() * 1000:
        d = _get(FR, {"symbol": sym, "startTime": cur, "limit": 1000})
        if not d: break
        out.extend(d); cur = d[-1]["fundingTime"] + 1
    if not out: return 0
    json.dump(out, open(path, "w"))
    return len(out)


def main():
    for sym_bare in BASKET:
        sym = sym_bare + "USDT"
        n1d = fetch_klines(sym, "1d", 1500)
        time.sleep(0.3)
        n1h = fetch_klines(sym, "1h", 400)
        time.sleep(0.3)
        nfr = fetch_funding(sym)
        time.sleep(0.3)
        print(f"{sym_bare:5s}: 1d={n1d} 1h={n1h} funding={nfr}", flush=True)
    print("BASKET FETCH DONE")


if __name__ == "__main__":
    main()
