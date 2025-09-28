FROM python:3.11-slim
WORKDIR /app

# Install system dependencies required for Bluetooth operations
RUN apt-get update && apt-get install -y \
    bluetooth \
    libbluetooth-dev \
    pkg-config \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for data persistence
RUN mkdir -p /app/data

# Set environment variables
ENV BLUEMON_CONFIG=/app/data/config.json
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose the web UI port
EXPOSE 8080

# Add health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# Create non-root user for security
RUN groupadd -r bluemon && useradd -r -g bluemon bluemon
RUN chown -R bluemon:bluemon /app
USER bluemon

# Run the application
CMD ["python", "bluemon.py"]