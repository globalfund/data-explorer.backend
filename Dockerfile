# Start with python 3.11
FROM python:3.11-alpine

RUN apk add --no-cache git libmagic

COPY . /app
WORKDIR /app

# Pre-install python dependencies
RUN pip install -r requirements.txt

# Run the app
CMD ["gunicorn", "-w", "8", "app:app", "-b", "0.0.0.0:4004", "--timeout", "600"]
