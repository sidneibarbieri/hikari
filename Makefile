.PHONY: help up acceptance down clean

LOCAL := deploy/local

help:
	@echo "Hikari Platform — comandos disponíveis:"
	@echo ""
	@echo "  make up          Sobe todos os serviços (Docker Compose)"
	@echo "  make acceptance  Roda a suíte completa de testes de aceitação"
	@echo "  make down        Para e remove os contêineres"
	@echo "  make clean       Remove artefatos locais e caches"
	@echo ""
	@echo "Atalho para revisores (sobe + testa):"
	@echo "  make review"
	@echo ""

review: up acceptance

up:
	@test -f $(LOCAL)/.env || cp $(LOCAL)/.env $(LOCAL)/.env
	docker-compose -f $(LOCAL)/docker-compose.yml up -d --build

acceptance:
	bash $(LOCAL)/run_acceptance.sh

down:
	docker-compose -f $(LOCAL)/docker-compose.yml down

clean:
	rm -rf output .playwright-cli $(LOCAL)/artifacts
	find . \( -name '__pycache__' -o -name '*.pyc' -o -name '.DS_Store' \) -prune -exec rm -rf {} +
