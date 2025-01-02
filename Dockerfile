FROM python:3.10-slim

WORKDIR /app

# Install system dependencies including curl for health checks
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the entire project
COPY . .

# Install requirements and the package
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install -e .

# Default command (can be overridden in docker-compose.yml)
CMD ["uvicorn", "nmkr_support_v4.api:app", "--host", "0.0.0.0", "--port", "8000"] 