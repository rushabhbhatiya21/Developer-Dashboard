# Dockerfile.dashboard
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies for dashboard
RUN pip install --no-cache-dir -r requirements.txt

# Copy dashboard application
COPY templates ./templates
COPY health_dashboard.py ./health_dashboard.py

# Create non-root user
RUN useradd -m -u 1000 dashboard && chown -R dashboard:dashboard /app
USER dashboard

# Expose dashboard port
EXPOSE 8090

# Set default environment variables
ENV DASHBOARD_PORT=8090
ENV REFRESH_INTERVAL=30
ENV WORKER_ENDPOINTS="http://ocr_worker:8080,http://llm_worker:8081,http://o1_llm_worker:8082,http://strikethrough_worker:8083,http://summary_worker:8084"

# Health check for the dashboard itself
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8090/health || exit 1

# Run the dashboard
CMD ["python", "health_dashboard.py"]