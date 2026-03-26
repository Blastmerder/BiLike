FROM python:3.8-slim-buster

WORKDIR /usr/local/
COPY . .

RUN echo $(ls)
RUN pip install -r requirements.txt

CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0"]
