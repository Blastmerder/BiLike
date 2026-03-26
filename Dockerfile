FROM python:3.8-slim-buster

WORKDIR /usr/local/a
COPY src/server-side/* ./

RUN pip install -r requirements

CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0"]
