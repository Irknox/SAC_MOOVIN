FROM python:3.13.3-slim

WORKDIR /app

COPY requirements.txt .

RUN apt-get update \
 && apt-get install -y --no-install-recommends libopus0 libopus-dev git \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt

COPY .env .env
COPY moovin_agents_SDK/ /app/

EXPOSE 8989

CMD ["python","-m","uvicorn","api:app","--host","0.0.0.0","--port","8989"]
