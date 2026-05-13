.PHONY: review up acceptance down clean-local

COMPOSE_DIR := deploy/local

review: up acceptance

up:
	cd $(COMPOSE_DIR) && test -f .env || cp .env.example .env
	cd $(COMPOSE_DIR) && docker-compose up -d --build

acceptance:
	cd $(COMPOSE_DIR) && bash run_acceptance.sh

down:
	cd $(COMPOSE_DIR) && docker-compose down

clean-local:
	rm -rf output .playwright-cli deploy/local/artifacts
	find . \( -name '__pycache__' -o -name '*.pyc' -o -name '.DS_Store' \) -prune -exec rm -rf {} +
