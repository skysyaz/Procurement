FROM python:3.11-slim

# Install system + build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    tesseract-ocr \
    libtesseract-dev \
    poppler-utils \
    curl \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Cap glibc malloc arenas — drastically reduces RSS / VSZ growth in
# multi-threaded Python (uvicorn + tesseract spawn), prevents Render
# free-tier OOM during bulk OCR.
ENV MALLOC_ARENA_MAX=2

WORKDIR /app

# Copy requirements first for caching
COPY backend/requirements.txt ./

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir --no-deps google-genai==1.71.0 \
 && pip install --no-cache-dir google-auth httpx websockets tenacity distro sniffio anyio

# Copy backend code
COPY backend/ ./
RUN mkdir -p /app/uploads && chmod +x /app/start.sh

EXPOSE 8001
CMD ["/app/start.sh"]