import pickle, sys, pandas as pd
sys.path.insert(0, '.')

with open('wacc_regulatorio/data/cache/beta_prices_2019_2026.pkl', 'rb') as f:
    obj = pickle.load(f)

print(type(obj))
if isinstance(obj, pd.DataFrame):
    print("Columns:", list(obj.columns))
    print("Index type:", type(obj.index))
    print("Shape:", obj.shape)
    print(obj.head(3))
elif isinstance(obj, dict):
    print("Keys:", list(obj.keys())[:20])
    for k, v in list(obj.items())[:3]:
        print(f"  {k}: {type(v).__name__}", getattr(v, 'shape', ''))

with open('wacc_regulatorio/data/cache/market_caps.pkl', 'rb') as f:
    mc = pickle.load(f)
print("\nmarket_caps type:", type(mc))
if isinstance(mc, pd.DataFrame):
    print("Columns:", list(mc.columns))
    print(mc.head(5).to_string())
elif isinstance(mc, dict):
    print("Keys:", list(mc.keys())[:10])
