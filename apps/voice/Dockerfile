FROM python:3.13-slim
WORKDIR /app
COPY . .
RUN pip install uv
RUN uv sync --frozen
ENV PORT=8000
EXPOSE ${PORT}
CMD ["sh", "-c", "uv run uvicorn main:app --host 0.0.0.0 --port $PORT"]
