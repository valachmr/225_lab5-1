FROM python:3.9-slim

RUN apt-get clean \
    && apt-get -y update

RUN apt-get -y install \
    nginx \
    python3-dev \
    build-essential \
    nfs-common

WORKDIR /app

COPY broadcaster.py .

EXPOSE 8080

CMD ["python3", "broadcaster.py"]
