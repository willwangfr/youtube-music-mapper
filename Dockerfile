FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy the rest of the application
COPY . .

# Expose port
EXPOSE 8080

# Run the application
CMD ["gunicorn", "--chdir", "backend", "server:app", "--bind", "0.0.0.0:8080"]
