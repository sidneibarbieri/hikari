# Usa uma imagem oficial Python 3.9 Slim como imagem de base.
FROM python:3.9-slim

# Define o diretório de trabalho no container.
WORKDIR /app

# Instala as dependências necessárias, incluindo curl.
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*

# Copia o arquivo de dependências primeiro, para aproveitar o cache do Docker.
COPY requirements.txt .

# Instala as dependências do projeto.
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante dos arquivos do projeto para o diretório de trabalho.
COPY . .

# Comando para executar a aplicação usando Uvicorn.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

