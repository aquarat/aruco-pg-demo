#!/usr/bin/python2

from __future__ import print_function
import cv2
import cv2.aruco as aruco
import datetime
import psycopg2
import json

DB = "aruco"
CAPTURE = False
CAPTURE_DEV = 0
VIDEO_INPUT_FILE = "testfile.mp4"

conn = psycopg2.connect(host="aruco-pg", database="aruco", user="aruco", password="aruco")

cur = conn.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS "samples" (
	"id" SERIAL PRIMARY KEY,
	"when" TIMESTAMP NOT NULL DEFAULT NOW(),
	"frame_count" INTEGER NOT NULL,
	"aruco_id" SMALLINT NOT NULL,
	"geometry" JSONB NOT NULL
)
; """)

if CAPTURE:
    cap = cv2.VideoCapture(CAPTURE_DEV)
else:
    cap = cv2.VideoCapture(VIDEO_INPUT_FILE)

measures = []
axi = ["X", "Y"]
lastMeasure = 0
aruco_dict = aruco.Dictionary_get(aruco.DICT_4X4_50)
parameters = aruco.DetectorParameters_create()
frame_counter = 0

while True:
    frame_counter = frame_counter + 1
    ret, frame = cap.read()
    now = datetime.datetime.utcnow().isoformat()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    corners, idsS, rejectedImgPoints = aruco.detectMarkers(gray, aruco_dict, parameters=parameters)

    cleanIDs = []
    if idsS is not None and len(idsS) > 0:
        for ID in idsS:
            cleanIDs.append(int(ID))

    for cid in range(len(cleanIDs)):
        for corner in range(len(corners[cid])):
            tempPayload = dict()
            tempPayload["measurement"] = str(cleanIDs[cid])
            tempPayload["time"] = now
            tempPayload["fields"] = dict()
            for cdes in range(0, 4):
                for axis in range(0, 2):
                    tempPayload["fields"][str(cdes) + axi[axis]] = int(corners[cid][0][cdes][axis])
            cur.execute('INSERT INTO samples (aruco_id, frame_count, geometry) VALUES (%s, %s, %s) RETURNING id;',
                        [cleanIDs[cid], frame_counter, json.dumps(tempPayload["fields"])])
            conn.commit()
            print("Current DB Sample : " + str(cur.fetchone()[0]), end='\r')

conn.commit()
conn.disconnect()

cap.release()
cv2.destroyAllWindows()
