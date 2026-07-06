FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure upload directory exists
RUN mkdir -p uploads logs

# Build the task store at image build time (task_store.db + prebuilt /api/tasks
# payload files): the runtime container never parses the 40MB tasks.json.
RUN python task_store.py --build

# Cap glibc malloc arenas: lower RSS fragmentation in the threaded worker.
ENV MALLOC_ARENA_MAX=2

# Expose port
EXPOSE 8000

# Run the application
# Note: For persistence (SQLite), mount a volume to /app/academy.db at runtime
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
