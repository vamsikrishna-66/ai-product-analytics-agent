FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir dbt-duckdb==1.11.1 duckdb==2.0.0 dbt-core==1.12.7 fastapi==0.115.12 uvicorn==0.34.2
COPY . .
CMD ["dbt", "build", "--profiles-dir", "."]
