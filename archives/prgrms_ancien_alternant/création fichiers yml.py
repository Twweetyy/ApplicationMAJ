import requests
from bs4 import BeautifulSoup
import yaml
import os

themes = [
    {"dictionnaire_variables_POP":"https://www.insee.fr/fr/statistiques/8647014"},
    {"dictionnaire_variables_COU":"https://www.insee.fr/fr/statistiques/8647008"},
    {"dictionnaire_variables_LOG":"https://www.insee.fr/fr/statistiques/8647012"},
    {"dictionnaire_variables_DIP":"https://www.insee.fr/fr/statistiques/8647010"},
    {"dictionnaire_variables_ACT":"https://www.insee.fr/fr/statistiques/8647006"}
]

for th in themes:
    for name, url in th.items():
        resp = requests.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        variables = {}
        for li in soup.select("ul.bloc.liste li.item"):
            text = " ".join(li.get_text(strip=True).split())
            if " : " in text:
                code, label = text.split(" : ", 1)
                variables[code] = label
        fname = "test/" + name + ".yml"
        with open(fname, "w", encoding="utf-8") as f:
            yaml.dump(variables, f, allow_unicode=True, sort_keys=True)
        print(f"Thème '{name}' → {len(variables)} variables extraites dans {fname}")