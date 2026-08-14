FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies (if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY drivers/driver_service.py ./drivers/driver_service.py
COPY proc ./proc
COPY security ./security

# Expose port the FastAPI app runs on (default 8000)
EXPOSE 8000

# Set environment variable for OAuth secret placeholder (override in production)
ENV UOS_OAUTH_SECRET=placeholder_secret

# Run the FastAPI app with UVicorn
CMD ["uvicorn", "drivers.driver_service:app", "--host", "0.0.0.0", "--port", "8000", "--log-config", "uvicorn_logger.json"]
