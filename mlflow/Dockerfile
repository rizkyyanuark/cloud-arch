FROM python:3.11-slim

WORKDIR /mlflow

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    mlflow>=2.12.0 \
    boto3>=1.34.0 \
    psycopg2-binary>=2.9.9 \
    cryptography>=42.0.0

COPY run_mlflow.sh /mlflow/run_mlflow.sh
RUN chmod +x /mlflow/run_mlflow.sh

EXPOSE 5000

CMD ["/mlflow/run_mlflow.sh"]
