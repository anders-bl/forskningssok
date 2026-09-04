FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# /health/live, ikke /health/ready: en HEALTHCHECK som leser databasen ville drept
# containeren ved disk-treghet. Liveness spør «lever prosessen», readiness spør «kan vi ta
# trafikk» — Docker skal ha den første, oppetidsmonitoren den andre.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=4).status==200 else 1)"

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
