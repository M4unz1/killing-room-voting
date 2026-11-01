FROM python:3.13-slim
WORKDIR /app
COPY requirements-discord.txt .
RUN pip install --no-cache-dir -r requirements-discord.txt && mkdir /data && chown 10001:10001 /app /data
COPY --chown=10001:10001 . /app
USER 10001:10001
ENV PYTHONUNBUFFERED=1
EXPOSE 8765
CMD ["python", "server.py"]
