FROM python:3

COPY ./requirements.txt /
RUN pip install --no-cache-dir -r requirements.txt

COPY server /server

EXPOSE 5000

WORKDIR /server

CMD FLASK_APP=./server.py flask run --host=0.0.0.0