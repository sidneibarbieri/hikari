from typing import List, Dict
import json
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from confluent_kafka import Producer, Consumer, KafkaException

app = FastAPI()

bootstrap_servers = "kafka:9092"

def check_kafka_connection(bootstrap_servers: str) -> None:
    """
    Verifica a conexão com o Kafka.

    Args:
        bootstrap_servers (str): Endereço do servidor Kafka.
    """
    consumer = Consumer({
        'bootstrap.servers': bootstrap_servers,
        'group.id': 'test_group',
        'auto.offset.reset': 'earliest'
    })
    try:
        consumer.list_topics(timeout=10)
    except KafkaException as e:
        raise HTTPException(status_code=500, detail="Kafka broker is not available: " + str(e))
    finally:
        consumer.close()

@app.on_event("startup")
async def startup_event() -> None:
    """Evento de inicialização da aplicação."""
    check_kafka_connection(bootstrap_servers)

@app.get("/")
async def read_root() -> Dict[str, str]:
    """Endpoint raiz."""
    return {"message": "Welcome to the FastAPI Kafka Producer API"}

@app.get("/run_scenario/")
async def run_scenario() -> Dict[str, str]:
    """Endpoint para iniciar a simulação do cenário."""
    return {"message": "Scenario simulation started."}

@app.post("/upload_file/")
async def upload_file(file: UploadFile = File(...)) -> Dict[str, str]:
    """
    Endpoint para upload de arquivo JSON.

    Args:
        file (UploadFile): Arquivo JSON a ser enviado.

    Returns:
        Dict[str, str]: Mensagem de sucesso.
    """
    try:
        content = await file.read()
        data = json.loads(content)
        if not isinstance(data, list):
            raise HTTPException(status_code=400, detail="O arquivo JSON deve conter uma lista de objetos JSON.")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Erro ao decodificar JSON")

    return {"message": f"{len(data)} registros enviados para Kafka com sucesso."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

