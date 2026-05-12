import logging
from unittest.mock import patch
from fastapi.testclient import TestClient
import pytest

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

try:
    logger.debug("Aplicando mocks para check_kafka_connection e Producer")
    with patch('main.check_kafka_connection', return_value=True):
        with patch('main.Producer', autospec=True):
            from main import app
except Exception as e:
    logger.error("Erro ao aplicar mocks: %s", e)
    raise

client = TestClient(app)

def test_read_root() -> None:
    """Testa o endpoint raiz."""
    logger.debug("Iniciando test_read_root")
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the FastAPI Kafka Producer API"}
    logger.debug("Finalizando test_read_root")

def test_run_scenario() -> None:
    """Testa o endpoint run_scenario."""
    logger.debug("Iniciando test_run_scenario")
    response = client.get("/run_scenario/")
    assert response.status_code == 200
    assert response.json() == {"message": "Scenario simulation started."}
    logger.debug("Finalizando test_run_scenario")

def test_upload_file() -> None:
    """Testa o upload de arquivo JSON válido."""
    logger.debug("Iniciando test_upload_file")
    file_content = '[{"key1": "value1"}, {"key2": "value2"}]'
    response = client.post("/upload_file/", files={"file": ("test.json", file_content, "application/json")})
    logger.debug(f"Resposta recebida: {response.json()}")
    assert response.status_code == 200
    assert response.json() == {"message": "2 registros enviados para Kafka com sucesso."}
    logger.debug("Finalizando test_upload_file")

def test_upload_file_invalid_json() -> None:
    """Testa o upload de arquivo JSON inválido (não é uma lista)."""
    logger.debug("Iniciando test_upload_file_invalid_json")
    file_content = '{"key1": "value1", "key2": "value2"}'  # Not a list
    response = client.post("/upload_file/", files={"file": ("test.json", file_content, "application/json")})
    logger.debug(f"Resposta recebida: {response.json()}")
    assert response.status_code == 400
    assert "O arquivo JSON deve conter uma lista de objetos JSON." in response.json()["detail"]
    logger.debug("Finalizando test_upload_file_invalid_json")

def test_upload_file_malformed_json() -> None:
    """Testa o upload de arquivo JSON malformado."""
    logger.debug("Iniciando test_upload_file_malformed_json")
    file_content = '[{"key1": "value1", {"key2": "value2"}]'  # Malformed JSON
    response = client.post("/upload_file/", files={"file": ("test.json", file_content, "application/json")})
    logger.debug(f"Resposta recebida: {response.json()}")
    assert response.status_code == 400
    assert "Erro ao decodificar JSON" in response.json()["detail"]
    logger.debug("Finalizando test_upload_file_malformed_json")

