"""Fetch DefiLlama histories for a yield-pool basket: stable + emissions (incentivized).

Selects (a) stablecoin pools (tokens subset of USDC/USDT/DAI) and (b) top incentivized
pools (apyReward high, TVL large, reputable project). Fetches per-pool daily history
(apyBase / apyReward / il7d / tvlUsd). Real data, keyless.
"""
import json, os, time
import requests, pandas as pd

INDEX = "sol_data_cache/amm_pools_index.json"
CACHE = "sol_data_cache/yield_pools"
os.makedirs(CACHE, exist_ok=True)
REPUTABLE = {"uniswap-v3", "uniswap", "curve", "curve-dex", "balancer", "pancakeswap",
             "sushiswap", "compound-v3", "compound", "aave-v3", "aave", "convex-finance",
             "stargate", "mstable", "angle", "frax-swap", "velodrome", "aerodrome",
             "radiant", "moonwell", "gitcoin", "pendle", "makerdao", "spark", "extra-finance",
             "kyberswap", "camelot", "zyber", "ramses", "solidlizard", "shadow-exchange",
             "biswap", "thena", "beefy", "yearn-finance", "mesh-swap", "dodo", "quickswap",
             "gamma", "level-finance", "spectra", "tapio", "steer-protocol", "mymetaverse"}


def load_index():
    return json.load(open(INDEX))


def select(index):
    stables, emiss = [], []
    STAB = {"USDC", "USDT", "DAI"}
    for p in index:
        sym = (p.get("symbol") or "").upper().replace("-", ",").replace("/", ",")
        toks = {t.strip() for t in sym.split(",") if t.strip()}
        tvl = p.get("tvlUsd") or 0
        ar = p.get("apyReward") or 0
        ab = p.get("apyBase") or 0
        if toks <= STAB and len(toks) == 2 and tvl > 2e6:
            stables.append((p, tvl))
        elif (ar or 0) > 3 and tvl > 3e6 and p.get("project") in REPUTABLE and (ab + ar) < 1500:
            emiss.append((p, ar, tvl))
    # dedupe stables by (symbol, chain), keep highest TVL
    seen = {}
    for p, tvl in sorted(stables, key=lambda x: -x[1]):
        k = (p.get("symbol"), p.get("chain"))
        if k not in seen:
            seen[k] = p
    stable_picks = list(seen.values())[:14]
    emiss.sort(key=lambda x: -x[1])
    emiss_picks = [p for p, ar, tvl in emiss[:30]]
    return stable_picks, emiss_picks


def fetch_chart(pool_id):
    path = f"{CACHE}/{pool_id}.json"
    if os.path.exists(path):
        return True
    try:
        r = requests.get(f"https://yields.llama.fi/chart/{pool_id}", timeout=40)
        data = r.json().get("data", [])
        if len(data) < 60:
            return False
        json.dump(data, open(path, "w"))
        return True
    except Exception as e:
        print(f"  {pool_id}: ERR {str(e)[:60]}")
        return False


def main():
    idx = load_index()
    stables, emiss = select(idx)
    print(f"selected: {len(stables)} stable pools, {len(emiss)} emissions pools")
    summary = []
    for tag, picks in [("stable", stables), ("emissions", emiss)]:
        for p in picks:
            ok = fetch_chart(p["pool"])
            if ok:
                summary.append({"tag": tag, "symbol": p.get("symbol"), "project": p.get("project"),
                                "chain": p.get("chain"), "pool": p["pool"],
                                "tvl": p.get("tvlUsd"), "apyBase": p.get("apyBase"),
                                "apyReward": p.get("apyReward")})
            time.sleep(0.4)
    json.dump(summary, open(f"{CACHE}/_basket_summary.json", "w"), indent=2)
    print(f"cached {len(summary)} pool histories -> {CACHE}/")
    # quick look at emissions decay
    import statistics
    for p in summary:
        if p["tag"] != "emissions": continue
        d = json.load(open(f"{CACHE}/{p['pool']}.json"))
        ar = [x.get("apyReward") or 0 for x in d]
        p["mean_ar"] = statistics.mean(ar); p["last_ar"] = ar[-1] if ar else 0
        p["n_days"] = len(d)
    print("\nemissions pools (mean vs current apyReward — shows decay):")
    for p in sorted([s for s in summary if s.get("tag") == "emissions"], key=lambda x: -(x.get("mean_ar", 0)))[:12]:
        print(f"  {p['symbol']:14s} {p['project']:14s} {p['chain']:10s} mean_ar={p.get('mean_ar',0):5.1f}% "
              f"now={p.get('last_ar',0):5.1f}%  ({p['n_days']}d)")


if __name__ == "__main__":
    main()
