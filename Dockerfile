FROM ubuntu:latest
EXPOSE 25565


RUN apt-get update 
RUN apt-get install -y python3

WORKDIR /usr/local/a
COPY src/server-side/* ./

RUN pip install -r requirements

CMD ["uv run app.py"]
