FROM python:3.13-slim
WORKDIR /app
COPY . .
RUN pip install uv
RUN uv sync --frozen
ENV PORT=8000
EXPOSE ${PORT}
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/')" || exit 1
CMD uv run uvicorn main:app --host 0.0.0.0 --port ${PORT}
