FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    PATH="/home/sentinel/.local/bin:${PATH}"
WORKDIR /app
RUN addgroup --system sentinel && adduser --system --ingroup sentinel sentinel
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /app/storage && chmod +x /app/scripts/start.sh && chown -R sentinel:sentinel /app
USER sentinel
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready')"
CMD ["sh", "scripts/start.sh"]
