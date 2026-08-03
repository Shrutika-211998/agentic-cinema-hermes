FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    STORAGE_BACKEND=firestore \
    VERTEX_AI_ENABLED=true \
    CLOUD_LOGGING_ENABLED=true \
    GCS_ENABLED=true \
    GOOGLE_CLOUD_LOCATION=asia-south1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY adk_app ./adk_app
COPY mcp ./mcp
COPY data ./data
COPY index.html styles.css app.js ./
COPY package.json README.md LICENSE ./

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/output /app/data \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080
CMD ["python", "-m", "src.server"]
