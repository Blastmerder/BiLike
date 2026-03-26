FROM ubuntu:latest
EXPOSE 25565


RUN apt-get update 
RUN apt-get install python3 uv

WORKDIR /usr/local/a
COPY src/server-side/* ./

RUN uv venv
RUN uv pip install -r requirements

CMD ["uv run app.py"]
