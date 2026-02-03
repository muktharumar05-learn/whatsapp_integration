# Use official Python base image
FROM python:3.11-slim

# Set work directory inside container
WORKDIR /app

# Install system dependencies (if any, e.g. gcc for psycopg2)
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium --with-deps

# Copy app source code
COPY ./app ./app
COPY ./agent ./agent
COPY ./client ./client
COPY ./database ./database
COPY ./html_templates ./html_templates
COPY ./service ./service
COPY ./prompts ./prompts
COPY config.yaml .
COPY ./scrape ./scrape
COPY ./rag ./rag

# Expose port (if you run on 8000)
EXPOSE 8000

# Command to run FastAPI with Uvicorn
CMD ["uvicorn", "app.whatsapp:app", "--host", "0.0.0.0", "--port", "8000"]