FROM python:3.12-slim

WORKDIR /app

# Dependances d'abord (cache des couches)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code
COPY pokebot ./pokebot

# La base SQLite et les caches vivent dans /app/data (volume)
ENV HOST=0.0.0.0 \
    PORT=8000 \
    PYTHONUNBUFFERED=1

EXPOSE 8000
VOLUME ["/app/data"]

CMD ["python", "-m", "pokebot", "serve"]
