import json, pandas as pd
with open('sol_data_cache/FUNDING_SOL.json') as f:
    h = json.load(f)
print('records:', len(h))
print('sample:', h[0])
print('keys:', list(h[0].keys()))
fr = pd.DataFrame(h)
print('columns:', list(fr.columns))
from slate_core.dex.data.load_data import load_candles
df = load_candles('sol_data_cache/HYPERLIQUID_SOL_1h.json')
print('candle range:', df.index[0], '->', df.index[-1])
fr_time = pd.to_datetime(fr['time'], unit='ms') if 'time' in fr.columns else None
if fr_time is not None:
    print('funding range:', fr_time.iloc[0], '->', fr_time.iloc[-1])
    overlap = (fr_time >= df.index[0]) & (fr_time <= df.index[-1])
    print('funding in candle range:', overlap.sum())
