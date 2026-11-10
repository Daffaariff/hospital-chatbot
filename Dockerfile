FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 FASTEMBED_CACHE_PATH=/models
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt
# NOTE: bake embedding models into the image so startup needs no downloads
RUN python -c "from fastembed import TextEmbedding, SparseTextEmbedding; from fastembed.rerank.cross_encoder import TextCrossEncoder; TextEmbedding('BAAI/bge-small-en-v1.5'); SparseTextEmbedding('Qdrant/bm25'); TextCrossEncoder('jinaai/jina-reranker-v1-turbo-en')"
COPY . .
EXPOSE 8000
CMD ["python", "runner.py", "-p", "8000"]
