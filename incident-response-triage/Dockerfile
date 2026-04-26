FROM python:3.11-slim

ENV PORT=7860
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# 1. Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. Copy the server folder from your repo into the container
# This ensures server.main is at /app/server/main.py
COPY server/ ./server/

# 3. Create non-root user for HF Spaces
RUN useradd -m -u 1000 appuser && chown -R appuser /app
USER appuser

EXPOSE 7860

# 4. Start the app
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "7860"]