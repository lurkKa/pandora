FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure upload directory exists
RUN mkdir -p uploads logs

# Expose port
EXPOSE 8000

# Run the application
# Note: For persistence (SQLite), mount a volume to /app/academy.db at runtime
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
