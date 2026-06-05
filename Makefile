.PHONY: install dev run scan test docker-up docker-down clean

# Cree l'environnement virtuel et installe les dependances
install:
	python3 -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt
	@test -f .env || cp .env.example .env
	@echo "✅ Installation terminee. Lancez 'make run' puis ouvrez http://127.0.0.1:8000"

# Installe aussi les outils de dev (pytest)
dev:
	. .venv/bin/activate && pip install -r requirements-dev.txt

# Lance l'interface web + le planificateur
run:
	. .venv/bin/activate && python -m pokebot serve

# Lance un seul cycle de scan (sans serveur)
scan:
	. .venv/bin/activate && python -m pokebot scan

# Tests
test:
	. .venv/bin/activate && pytest -q

# Docker
docker-up:
	@test -f .env || cp .env.example .env
	docker compose up --build -d
	@echo "✅ http://127.0.0.1:8000"

docker-down:
	docker compose down

clean:
	rm -rf .venv __pycache__ .pytest_cache
