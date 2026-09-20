FROM mcr.microsoft.com/playwright/python:v1.49.1-jammy

WORKDIR /suite

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/suite/src
ENV HEADLESS=true

CMD ["pytest", "-m", "smoke"]
