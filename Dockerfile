FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 FASTEMBED_CACHE_PATH=/models
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# NOTE: bake embedding models into the image so startup needs no downloads
RUN python -c "from fastembed import TextEmbedding, SparseTextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5'); SparseTextEmbedding('Qdrant/bm25')"
COPY . .
EXPOSE 8000
CMD ["python", "runner.py", "-p", "8000"]
