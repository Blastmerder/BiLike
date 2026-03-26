FROM debian:latest
EXPOSE 25565


RUN apt-get update 
RUN apt-get install -y python3 python3-pip
RUN apt-get install -y uv

WORKDIR /usr/local/a
COPY src/server-side/* ./

RUN python3 -m pip install --upgrade pip \
    && python3 -m pip install --no-cache-dir -r requirements

CMD ["uv", "run", "app.py"]
