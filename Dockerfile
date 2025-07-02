FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY moovin_agents_SDK/ .

EXPOSE 8989

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8989"]
