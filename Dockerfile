FROM python:3.12-slim

WORKDIR /app

# System deps for psycopg2 and bcrypt
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Non-root user for security
RUN useradd -m -u 1001 prismrag && chown -R prismrag:prismrag /app
USER prismrag

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", \
     "--workers", "4", "--proxy-headers", "--forwarded-allow-ips", "*"]
