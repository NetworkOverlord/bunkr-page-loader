FROM python:3.11-slim

RUN apt update && apt install -y wget curl unzip chromium chromium-driver

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY bunkr_headless_page_loader.py ./
ENTRYPOINT ["python", "bunkr_headless_page_loader.py"]
