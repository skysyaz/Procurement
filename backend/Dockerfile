FROM python:3.11-slim

# Install system + build dependencies (lean: no tesseract / poppler — OCR
# is now handled by Gemini PDF, no native rasterisation needed).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    curl \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for caching
COPY backend/requirements.txt ./

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir emergentintegrations \
        --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ \
 && pip install --no-cache-dir resend celery redis

# Copy backend code
COPY backend/ ./
RUN mkdir -p /app/uploads && chmod +x /app/start.sh

EXPOSE 8001
CMD ["/app/start.sh"]