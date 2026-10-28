FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-server.txt /app/
RUN pip install --no-cache-dir -r requirements-server.txt \
    && groupadd --gid 10001 logbook \
    && useradd --uid 10001 --gid 10001 --no-create-home logbook \
    && mkdir -p /app/data && chown 10001:10001 /app/data
COPY common.py /app/
COPY server /app/server
USER 10001:10001
CMD ["python", "-m", "server", "serve", "--database", "/app/data/logbook.sqlite", "--host", "127.0.0.1"]
