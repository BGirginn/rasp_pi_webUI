# Pi Control Panel - Panel Dockerfile
# Multi-stage build for API + static UI

# Stage 1: Build React UI
FROM node:20-alpine AS ui-builder

WORKDIR /app/ui

# Copy package files
COPY ui/package*.json ./

# Install dependencies
RUN npm install

# Copy source
COPY ui/ ./

# Build production bundle
RUN npm run build

# Stage 2: Python API
FROM python:3.11-slim

WORKDIR /app

# Set Python path for package imports
ENV PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi-dev \
    openssh-client \
    iproute2 \
    sshpass \
    && rm -rf /var/lib/apt/lists/*

# Copy API requirements
COPY api/requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy API source
COPY api/ ./

# Copy built UI from previous stage
COPY --from=ui-builder /app/ui/dist /srv/ui

# Create non-root user
RUN useradd -m -u 1000 panel && \
    chown -R panel:panel /app /srv/ui

USER panel

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8080/api/health', timeout=5)"

# Run API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

