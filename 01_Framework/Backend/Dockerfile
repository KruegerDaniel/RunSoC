FROM python:3.11-slim AS builder

ENV MPLBACKEND=Agg
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libfreetype6-dev \
    libpng-dev \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
 && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# --- Runtime stage (no gcc/dev headers) ---
FROM python:3.11-slim AS runner

ENV MPLBACKEND=Agg
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Runtime libs only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libfreetype6 \
    libpng16-16 \
  && rm -rf /var/lib/apt/lists/*


RUN useradd -r -u 10001 -g nogroup appuser

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

COPY src/ ./src
ENV PYTHONPATH=/app/src

# Drop privileges
USER 10001

EXPOSE 5001

CMD ["gunicorn", "-b", "0.0.0.0:5001", "--workers", "2", "--timeout", "60", "--graceful-timeout", "30", "src.app:app"]
