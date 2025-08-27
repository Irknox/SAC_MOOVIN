FROM python:3.13.3-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY .env .env

COPY moovin_agents_SDK/ .

EXPOSE 8989

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8989"]
