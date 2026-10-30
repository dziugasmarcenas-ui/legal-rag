FROM python:3.12-slim

# Keeps the image small and logs unbuffered so Railway shows them live.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first, so a code change does not reinstall them.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The parsed corpus and the vectors ship inside the image. The container needs
# no Voyage key at boot and serves exactly the vectors the evaluation ran
# against -- a container that re-embedded on startup would be serving numbers
# nobody measured.
COPY data/articles.json data/articles.json
COPY data/history.json data/history.json
COPY data/links.json data/links.json
# The source chunks and their vectors live in one SQLite file. The old pair
# (sources.json + sources.npy) was 47 MB and had to be loaded whole into memory
# at import; the store is read per query and grows without rewriting the image.
COPY data/vectors.db data/vectors.db
# Measured numbers for /status, published as data because eval/ is excluded
# from the build context.
COPY data/quality.json data/quality.json
COPY embeddings/corpus.npy embeddings/corpus.npy
COPY embeddings/corpus.json embeddings/corpus.json
COPY embeddings/versions.npy embeddings/versions.npy
COPY embeddings/versions.json embeddings/versions.json
COPY static/ static/
COPY config.py retrieval.py gate.py edition.py ratelimit.py llm.py answer.py \
     paragraphs.py history.py oauth.py link_graph.py vector_store.py mcp_server.py main.py ./

# Fail the build rather than the first request if the corpus and the vectors
# ever ship out of step with each other.
RUN python -c "import retrieval; assert retrieval.VECTORS.shape[0] == len(retrieval.ARTICLES); print('corpus/vector alignment OK:', retrieval.VECTORS.shape)"

# The store must exist and agree with what retrieval serves: a fallback that
# silently ships no acts would still answer Code questions, so this is checked.
RUN python -c "import retrieval, vector_store; s = retrieval.vector_index(); assert s is not None, 'vectors.db missing'; assert s.count() == len(retrieval.source_index()[0]), 'store/record mismatch'; print('vector store OK:', s.count(), 'chunks')"

# Import the whole app, not just retrieval: a missing module in COPY is the
# failure mode that took the live service down once.
RUN python -c "import main; print('app imports OK')"

EXPOSE 8000

# Railway injects PORT. Default to 8000 so the image also runs locally.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
