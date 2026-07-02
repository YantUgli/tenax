# Pin the exact patch version so `pipenv install --deploy` (which enforces the
# Pipfile's python_full_version) matches and the build is reproducible.
FROM python:3.12.3-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIPENV_VENV_IN_PROJECT=1

WORKDIR /app

# Install pipenv and project deps first (better layer caching)
RUN pip install --no-cache-dir pipenv
COPY Pipfile Pipfile.lock ./
RUN pipenv install --deploy --system

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
