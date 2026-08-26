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
COPY embeddings/ embeddings/
COPY config.py retrieval.py gate.py ratelimit.py main.py ./

# Fail the build rather than the first request if the corpus and the vectors
# ever ship out of step with each other.
RUN python -c "import retrieval; assert retrieval.VECTORS.shape[0] == len(retrieval.ARTICLES); print('corpus/vector alignment OK:', retrieval.VECTORS.shape)"

EXPOSE 8000

# Railway injects PORT. Default to 8000 so the image also runs locally.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
