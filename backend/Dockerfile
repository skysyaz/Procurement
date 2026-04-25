FROM python:3.11-slim

# OCR system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr poppler-utils curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir emergentintegrations \
        --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ \
 && pip install --no-cache-dir pytesseract pdf2image resend celery redis

COPY backend/ ./
RUN mkdir -p /app/uploads && chmod +x /app/start.sh

# Render injects $PORT
EXPOSE 8001
CMD ["/app/start.sh"]
