FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AAMAD_TARGET_RUNTIME=crewai \
    STORAGE_DIR=/app/storage \
    CREWAI_STORAGE_DIR=/app/storage/crewai \
    DATABASE_URL=sqlite:////app/storage/recruitment_assistant.db

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
RUN mkdir -p /app/storage/crewai && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]