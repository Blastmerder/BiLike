FROM ubuntu:latest
EXPOSE 25565


RUN apt-get update 
RUN apt-get install -y python

WORKDIR /usr/local/a
COPY src/server-side/* ./

RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir uv

RUN uv venv
RUN uv pip install -r requirements

CMD ["uv run app.py"]
