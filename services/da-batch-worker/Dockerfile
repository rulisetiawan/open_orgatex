FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (curl for healthcheck, ping/iputils for network diagnostics)
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Set timezone
ENV TZ=Asia/Jakarta
RUN cp /usr/share/zoneinfo/Asia/Jakarta /etc/localtime && echo "Asia/Jakarta" > /etc/timezone

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app

# Healthcheck probe (process running)
HEALTHCHECK --interval=60s --timeout=5s --start-period=10s --retries=3 \
  CMD pgrep -f "python worker.py" || exit 1

CMD ["python", "worker.py"]
