FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

COPY engine/requirements.txt /app/engine/requirements.txt
RUN python -m venv "${VIRTUAL_ENV}" \
    && pip install --no-cache-dir -r /app/engine/requirements.txt

COPY engine /app/engine
COPY provider/container /app/provider/container

EXPOSE 8080

CMD ["python", "/app/provider/container/runner.py"]
