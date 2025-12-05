############################################
# Multi-stage build for a lean single image #
############################################

# 1) Build the React frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2) Install Python deps into a venv
FROM python:3.11-alpine AS backend-build
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
COPY backend/requirements.txt ./backend/requirements.txt
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r backend/requirements.txt

# 3) Final runtime image
FROM python:3.11-alpine
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/backend \
    PORT=8000

# Runtime libs for uvicorn extras
RUN apk add --no-cache libstdc++

# App code + assets
COPY backend ./backend
COPY --from=frontend-build /app/frontend/dist ./frontend/dist
COPY --from=backend-build /opt/venv /opt/venv

# Ensure SQLite path exists
RUN mkdir -p /app/data

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

