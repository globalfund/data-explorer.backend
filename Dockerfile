# Start with python 3.11
FROM python:3.11-alpine

RUN apk add --no-cache git libmagic

COPY . /app
WORKDIR /app

# Pre-install python dependencies
RUN pip install -r requirements.txt
