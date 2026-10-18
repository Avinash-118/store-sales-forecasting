FROM python:3.11.5-slim

WORKDIR /app

COPY . /app

RUN apt-get update && apt-get install -y \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    pandas==2.1.4 \
    numpy==1.26.2 \
    scikit-learn==1.3.2 \
    fastapi \
    "uvicorn[standard]" \
    streamlit \
    pymongo \
    psycopg2-binary \
    azure-identity \
    azure-keyvault-secrets \
    azure-storage-blob \
    torch \
    pytorch-lightning \
    "darts==0.27.1" \
    lightgbm \
    joblib==1.3.2

EXPOSE 8000 8501

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
