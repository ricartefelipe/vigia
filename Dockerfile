FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY corpus ./corpus
COPY eval ./eval
RUN pip install --no-cache-dir .

ENV VIGIA_EMBEDDER=hash
ENTRYPOINT ["vigia"]
CMD ["retrieval"]
