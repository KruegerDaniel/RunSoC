FROM python:3.11-slim

ENV MPLBACKEND=Agg
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# system deps for matplotlib
RUN apt-get update && apt-get install -y \
    gcc \
    libfreetype6-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src

ENV PYTHONPATH=/app/src

EXPOSE 5001

# IMPORTANT: point gunicorn at src.app:app (since app.py is now in src/)
CMD ["gunicorn", "-b", "0.0.0.0:5001", "--workers", "2", "src.app:app"]
