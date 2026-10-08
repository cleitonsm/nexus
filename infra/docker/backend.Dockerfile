FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# OCR local de PDF digitalizado (SPEC-005, D2): Poppler gera a imagem da
# pagina e o Tesseract reconhece o texto, em portugues e ingles.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        poppler-utils tesseract-ocr tesseract-ocr-por tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Modelos locais ficam no volume backend_cache; originais, em documents_data.
ENV HF_HOME=/app/cache
RUN mkdir -p /app/cache /app/data/documents

# PyTorch apenas para CPU: evita os pacotes de GPU, que multiplicam a imagem.
RUN pip install --no-cache-dir torch==2.5.1 \
    --index-url https://download.pytorch.org/whl/cpu

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend/alembic.ini /app/alembic.ini
COPY backend/src /app/src

EXPOSE 8000

# O servico worker usa esta mesma imagem com: python -m src.cli.worker
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
