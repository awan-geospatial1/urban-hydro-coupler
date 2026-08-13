# Use official Python runtime as parent image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies for SWMM and scientific libraries
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libgomp1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first (for better layer caching)
COPY pyproject.toml .
COPY README.md .

# Install Python dependencies
RUN pip install --no-cache-dir .

# Copy the rest of the application
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/
COPY data/ ./data/

# Create directories for outputs
RUN mkdir -p /app/data/outputs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Expose Streamlit default port
EXPOSE 8501

# Run the Streamlit app
CMD ["streamlit", "run", "src/dashboard/streamlit_app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.enableCORS=false"]
