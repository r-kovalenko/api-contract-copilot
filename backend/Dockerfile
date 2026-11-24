FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ripgrep && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-runtime.txt ./
RUN pip install --no-cache-dir -r requirements-runtime.txt
COPY app/oasdiff_pin.py ./app/oasdiff_pin.py
COPY install_oasdiff.py ./
RUN python install_oasdiff.py
COPY app ./app
COPY demo_code_search.py ./
COPY demo_model_provider.py ./
COPY alembic.ini ./
COPY alembic ./alembic
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
