FROM python:3.12-slim

LABEL org.opencontainers.image.title="discord-autoticker-bot" \
      org.opencontainers.image.description="Discord bot that replies to \$TICKER mentions with stock quotes." \
      org.opencontainers.image.source="https://github.com/ByYudkowskysTentacle/discord-autoticker-bot" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later"

# PYTHONUNBUFFERED   : stream logs immediately (so `docker logs` is live).
# PYTHONDONTWRITEBYTECODE : no .pyc clutter in the image.
# PIP_NO_CACHE_DIR / PIP_DISABLE_PIP_VERSION_CHECK : smaller, quieter builds.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first so this layer stays cached across code changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Ship the license and the source modules. Keeping the AGPL text in the image
# is good practice for a copyleft project.
COPY LICENSE ./
COPY bot.py market_api.py utils.py ./

# Run as an unprivileged user rather than root.
RUN useradd --create-home --uid 10001 botuser
USER botuser

CMD ["python", "bot.py"]
