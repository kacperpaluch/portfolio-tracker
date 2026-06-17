# --- Etap 1: build frontendu ---
FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- Etap 2: backend + gotowy frontend ---
FROM python:3.13-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    DB_PATH=/app/data/portfolio.db \
    TZ=Europe/Warsaw

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY --from=frontend /frontend/dist ./frontend/dist

VOLUME ["/app/data"]
EXPOSE 8000

WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
