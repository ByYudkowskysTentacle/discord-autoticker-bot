FROM python:3.12-slim

# Don't buffer stdout/stderr so logs show up promptly in container platforms.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first so this layer is cached across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py market_api.py utils.py ./

# Run as a non-root user.
RUN useradd --create-home --uid 10001 botuser
USER botuser

CMD ["python", "bot.py"]
