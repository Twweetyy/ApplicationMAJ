import pandas as pd, os
d = r"data\data2023\sources_brutes_insee"
for f in ["base-ic-pop-2023.csv","base-ic-log-2023.csv","base-ic-emp-2023.csv","base-ic-men-2023.csv","base-ic-dip-2023.csv"]:
    df = pd.read_csv(os.path.join(d, f), sep=";", dtype=str)
    df = df[df["GEO"] == "595120101"]
    print("=====", f, len(df), "lignes")
    for c in df.columns:
        if c not in ("GEO", "OBS_VALUE"):
            print(f"  {c}: {sorted(df[c].dropna().unique().tolist())[:25]}")