# Backend image for Railway (built from the repo root)
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY recipe_agent ./recipe_agent
COPY data ./data
# the committed 25-recipe dataset seeds an empty volume on first start
COPY output/records ./output/records

ENV DATA_DIR=/data FETCH_MODE=auto
EXPOSE 8000
CMD ["sh", "-c", "uvicorn recipe_agent.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
