FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Create a non-root user and group
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Install dependencies first for layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code and entrypoint script
COPY . .

# Ensure /data exists for SQLite persistence and permissions are set for appuser
RUN mkdir -p /data && \
    chmod +x /app/docker-entrypoint.sh && \
    chown -R appuser:appuser /app /data

USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]

