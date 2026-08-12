.PHONY: help up acceptance review down clean

LOCAL := deploy/local

help:
	@echo "Hikari Platform — comandos disponíveis:"
	@echo ""
	@echo "  make up          Sobe todos os serviços (Docker Compose)"
	@echo "  make acceptance  Roda a suíte em um ambiente descartável"
	@echo "  make down        Para e remove os contêineres"
	@echo "  make clean       Remove artefatos locais e caches"
	@echo ""
	@echo "Atalho para revisores (sobe + testa):"
	@echo "  make review"
	@echo ""

review: acceptance

up:
	@test -f $(LOCAL)/.env || cp $(LOCAL)/.env.example $(LOCAL)/.env
	bash $(LOCAL)/bootstrap.sh

acceptance:
	bash $(LOCAL)/tests/acceptance_isolated.sh

down:
	@if docker compose version >/dev/null 2>&1; then docker compose -f $(LOCAL)/docker-compose.yml down; else docker-compose -f $(LOCAL)/docker-compose.yml down; fi

clean:
	rm -rf output .playwright-cli $(LOCAL)/artifacts
	find . \( -name '__pycache__' -o -name '*.pyc' -o -name '.DS_Store' \) -prune -exec rm -rf {} +
