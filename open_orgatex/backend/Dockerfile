FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (curl for healthcheck, ping/iputils for network diagnostics)
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application code
COPY . /app/open_orgatex/backend

EXPOSE 8788

CMD ["uvicorn", "open_orgatex.backend.app:app", "--host", "0.0.0.0", "--port", "8788"]
