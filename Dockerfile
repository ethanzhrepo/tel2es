# Multi-stage Dockerfile for Telegram Scraper
FROM python:3.11-slim as base

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Create directory for session files
RUN mkdir -p /app/sessions

# Set Python path
ENV PYTHONPATH=/app/src

# Default command (can be overridden)
CMD ["python", "src/main.py", "start"]
