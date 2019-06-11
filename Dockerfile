FROM ubuntu:18.04

RUN apt update
RUN apt install -y python-pip libsm6 libxext6 libxrender1 libpq-dev
RUN pip install opencv-contrib-python
RUN pip install psycopg2

RUN mkdir /host

WORKDIR /host

ENTRYPOINT /host/aruco.py
