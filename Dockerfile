# Portable image for the FastAPI backend: works on Render, Hugging Face Spaces
# and any other Docker host.
#
# The repo root is the build context, so the app lives under backend/ and is
# copied into place at build time.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# LibreOffice enables the legacy DOC/ODT/RTF/XLS pairs. Without it the API simply
# stops advertising those targets, so it is safe to omit in a slim build.
ARG INSTALL_LIBREOFFICE=true
RUN if [ "$INSTALL_LIBREOFFICE" = "true" ]; then \
        apt-get update && \
        apt-get install -y --no-install-recommends libreoffice-writer libreoffice-calc fonts-dejavu-core && \
        rm -rf /var/lib/apt/lists/*; \
    fi

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/tests ./tests

RUN mkdir -p /app/temp/uploads /app/temp/outputs

ENV APP_ENV=production \
    UPLOAD_DIR=/app/temp/uploads \
    OUTPUT_DIR=/app/temp/outputs

# Hugging Face Spaces expects 7860; Render injects its own $PORT. Honour
# whatever the platform provides and fall back to 7860 when it does not.
EXPOSE 7860 10000

CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860} --timeout-keep-alive 75"]
