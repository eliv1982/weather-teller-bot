FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Run as an unprivileged user. /app must be writable by it (bot.log + rotated backups).
RUN useradd --no-create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && chown appuser:appuser /app

COPY --chown=appuser:appuser . .

USER appuser

CMD ["python", "bot.py"]
