FROM ubuntu:latest
EXPOSE 25565


RUN apt-get update && apt-get install -y python uv

WORKDIR /usr/local/app/mods
COPY src/server-side/* ./

RUN uv venv
RUN uv pip install -r requirements

CMD ["./run.sh"]
