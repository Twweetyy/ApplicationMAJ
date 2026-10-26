import os
import pandas as pd

SOURCE = r"\\srvsig03p\Partage_SIG\Opendata\Alternants\Bilal 2026-2027\MAS\ApplicationMAJ\data\data2022\FD_INDCVI_2022.csv"
SORTIE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(SORTIE_DIR, exist_ok=True)
sortie = os.path.join(SORTIE_DIR, "FD_INDCVI_2022.csv")

premier = True
for bloc in pd.read_csv(SOURCE, sep=";", dtype=str, chunksize=500_000):
    bloc = bloc[bloc["IRIS"].str.startswith("59512", na=False)]
    bloc.to_csv(sortie, sep=";", index=False, mode="w" if premier else "a", header=premier)
    premier = False
print("OK :", sortie)