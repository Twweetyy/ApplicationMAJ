# Image du portail web BDDMAS
FROM python:3.12-slim

# Logs Python affichés en direct, pas de fichiers .pyc
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Dépendances installées avant le code : Docker garde cette couche en cache
# tant que requirements.txt ne change pas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

# Transforme les cubes Insee présents dans data/ (sans bloquer le portail en cas
# d'échec), puis démarre le portail accessible depuis l'hôte
CMD ["sh", "-c", "python scripts/transformer_recensement.py || echo '[ATTENTION] Le transformer a échoué, le portail démarre quand même.'; exec uvicorn webapp:app --host 0.0.0.0 --port 5000"]
