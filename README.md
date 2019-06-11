# Aruco Tracker Demo

I recently put together this application/set of scripts to collect motion tracking data for a variety of purposes.
I was principally interested in collecting motion data in order to calculate and graph displacement, acceleration and power required - without having to attach physical sensors (and write MCU code).

This project has a few components :
* Docker 	| for managing components
* Postgres 	| Data storage
* * I tested InfluxDB, MySQL/MariaDB and Postgres. Postgres had the best performance by far for both writing and later reading.
* * InfluxDB, no matter what I did, choked under load and was unusable. Worse it silently dropped samples.
* * MariaDB worked, but processing the data for display was clunky.
* Python2.7 	| Leverages OpenCV and OpenCV contrib to do motion tracking and inserts the result into the database.

To start, you'll need a network for your containers :
`
docker network create aruco-tracker
`

Then start the database :
`
docker run --name aruco-pg --network=aruco-tracker --rm -v /home/you/pgdata:/var/lib/postgresql/data --detach=false -e POSTGRES_USER=aruco -e POSTGRES_PASSWORD="aruco" postgres
`

The above command creates a transient docker container with Postgres in it.
The database will be accessible by its name from containers in the same network.

You'll also want Grafana, as my SQL snippets are built for Grafana :
`
docker run --network=aruco-tracker -d -p 3000:3000 --name=grafana -v grafana-storage:/var/lib/grafana grafana/grafana
`

You'll want to connect to http://localhost:3000 to set up Grafana. I'll hopefully add some provisioning scripts later.

You can now build the Python application :
`
docker build -t aruco-tracker:1 .
`

Once that's done you're ready to go :D

Start the application to process "testfile.mp4" :
`
docker run --rm -ti --detach=false -v "$PWD:/host" --network=aruco-tracker aruco-tracker:1
`
The application will process testfile.mp4 and insert the results into the database.
You can now go back to the Grafana web interface and interact with the data.

I should note that testfile.mp4 isn't a great test file for a few of reasons :
* The camera's shutter speed was set too low, which means the markers are subject to severe motion blur.
* The camera has a relatively large sensor and the aperture was set large too, so the depth of field is very narrow and as a result the markers go out of focus a lot.
* The image has a lot of confounding detail in it (junk in the background).
* testfile.mp4 has been re-encoded to have a lower bitrate for this repository, which introduced compression artifacts.
That said, it works surprisingly well.

## Here are some SQL snippets to get you started :

### Displacement :
```sql
SELECT 
"when" as "time",
"frame_count" as "frame_count",
(CAST(geometry->>'0X' as FLOAT) + CAST(geometry->>'1X' as FLOAT) + CAST(geometry->>'2X' as FLOAT) + CAST(geometry->>'3X' as FLOAT))/4 as "4X",
(CAST(geometry->>'0Y' as FLOAT) + CAST(geometry->>'1Y' as FLOAT) + CAST(geometry->>'2Y' as FLOAT) + CAST(geometry->>'3Y' as FLOAT))/4 as "4Y",
CAST(geometry->>'0X' as FLOAT) - COALESCE(CAST(LAG(geometry->>'0X') OVER (ORDER BY "when" DESC) as FLOAT), -1) as "displacement X",
CAST(geometry->>'0Y' as FLOAT) - COALESCE(CAST(LAG(geometry->>'0Y') OVER (ORDER BY "when" DESC) as FLOAT), -1) as "displacement Y"
FROM (
SELECT * FROM samples WHERE aruco_id = 4
ORDER BY "when"
) main
```

### Acceleration :
```sql
SET session my.vars.id = '8';

SELECT 
time, 
ABS("acceleration") as "Accel ID 8"
FROM 
(
SELECT 
time,
COALESCE(
(displacement - LAG(displacement) OVER (ORDER BY time DESC))/((time - LAG(time) OVER (ORDER BY time DESC))*1000),
-1) AS "acceleration"
FROM (
SELECT 
("frame_count"*1000/30) + CAST(extract(epoch from (NOW() - INTERVAL '6 HOUR')) as INTEGER) as "time",
(CAST(geometry->>'0X' as FLOAT) + CAST(geometry->>'1X' as FLOAT) + CAST(geometry->>'2X' as FLOAT) + CAST(geometry->>'3X' as FLOAT))/4 as "4X",
(CAST(geometry->>'0Y' as FLOAT) + CAST(geometry->>'1Y' as FLOAT) + CAST(geometry->>'2Y' as FLOAT) + CAST(geometry->>'3Y' as FLOAT))/4 as "4Y",
POINT(
(
COALESCE(CAST(LAG(geometry->>'0X') OVER (ORDER BY "when" DESC) as FLOAT),0) +
COALESCE(CAST(LAG(geometry->>'1X') OVER (ORDER BY "when" DESC) as FLOAT), 0) +
COALESCE(CAST(LAG(geometry->>'2X') OVER (ORDER BY "when" DESC) as FLOAT), 0) + 
COALESCE(CAST(LAG(geometry->>'3X') OVER (ORDER BY "when" DESC) as FLOAT), 0)
)/4,
(
COALESCE(CAST(LAG(geometry->>'0Y') OVER (ORDER BY "when" DESC) as FLOAT),0) +
COALESCE(CAST(LAG(geometry->>'1Y') OVER (ORDER BY "when" DESC) as FLOAT), 0) +
COALESCE(CAST(LAG(geometry->>'2Y') OVER (ORDER BY "when" DESC) as FLOAT), 0) + 
COALESCE(CAST(LAG(geometry->>'3Y') OVER (ORDER BY "when" DESC) as FLOAT), 0)
)/4)
<->
POINT((
COALESCE(CAST((geometry->>'0X') as FLOAT),0) +
COALESCE(CAST((geometry->>'1X') as FLOAT), 0) +
COALESCE(CAST((geometry->>'2X') as FLOAT), 0) + 
COALESCE(CAST((geometry->>'3X') as FLOAT), 0)
)/4, 
(
COALESCE(CAST((geometry->>'0Y') as FLOAT),0) +
COALESCE(CAST((geometry->>'1Y') as FLOAT), 0) +
COALESCE(CAST((geometry->>'2Y') as FLOAT), 0) + 
COALESCE(CAST((geometry->>'3Y') as FLOAT), 0)
)/4) as "displacement"
FROM (
SELECT * FROM samples WHERE aruco_id = current_setting('my.vars.id')::int
ORDER BY "when"
LIMIT ALL
) displacement
LIMIT ALL) "4x"
) "4xSTD",
(
SELECT AVG("acceleration"), STDDEV("acceleration") FROM
(
SELECT 
time,
COALESCE(
(displacement - LAG(displacement) OVER (ORDER BY time DESC))/((time - LAG(time) OVER (ORDER BY time DESC))*1000),
-1) AS "acceleration"
FROM (
SELECT 
("frame_count"*1000/30) + CAST(extract(epoch from (NOW() - INTERVAL '6 HOUR')) as INTEGER) as "time",
(CAST(geometry->>'0X' as FLOAT) + CAST(geometry->>'1X' as FLOAT) + CAST(geometry->>'2X' as FLOAT) + CAST(geometry->>'3X' as FLOAT))/4 as "4X",
(CAST(geometry->>'0Y' as FLOAT) + CAST(geometry->>'1Y' as FLOAT) + CAST(geometry->>'2Y' as FLOAT) + CAST(geometry->>'3Y' as FLOAT))/4 as "4Y",
POINT(
(
COALESCE(CAST(LAG(geometry->>'0X') OVER (ORDER BY "when" DESC) as FLOAT),0) +
COALESCE(CAST(LAG(geometry->>'1X') OVER (ORDER BY "when" DESC) as FLOAT), 0) +
COALESCE(CAST(LAG(geometry->>'2X') OVER (ORDER BY "when" DESC) as FLOAT), 0) + 
COALESCE(CAST(LAG(geometry->>'3X') OVER (ORDER BY "when" DESC) as FLOAT), 0)
)/4,
(
COALESCE(CAST(LAG(geometry->>'0Y') OVER (ORDER BY "when" DESC) as FLOAT),0) +
COALESCE(CAST(LAG(geometry->>'1Y') OVER (ORDER BY "when" DESC) as FLOAT), 0) +
COALESCE(CAST(LAG(geometry->>'2Y') OVER (ORDER BY "when" DESC) as FLOAT), 0) + 
COALESCE(CAST(LAG(geometry->>'3Y') OVER (ORDER BY "when" DESC) as FLOAT), 0)
)/4)
<->
POINT((
COALESCE(CAST((geometry->>'0X') as FLOAT),0) +
COALESCE(CAST((geometry->>'1X') as FLOAT), 0) +
COALESCE(CAST((geometry->>'2X') as FLOAT), 0) + 
COALESCE(CAST((geometry->>'3X') as FLOAT), 0)
)/4, 
(
COALESCE(CAST((geometry->>'0Y') as FLOAT),0) +
COALESCE(CAST((geometry->>'1Y') as FLOAT), 0) +
COALESCE(CAST((geometry->>'2Y') as FLOAT), 0) + 
COALESCE(CAST((geometry->>'3Y') as FLOAT), 0)
)/4) as "displacement"
FROM (
SELECT * FROM samples WHERE aruco_id = current_setting('my.vars.id')::int
ORDER BY "when"
LIMIT ALL
) displacement
LIMIT ALL) "4x"
) "4xSTDa"
) x
WHERE ABS("4xSTD"."acceleration" - x.avg) < x.stddev * 2;
```

### Rate of work:
```sql
SET session my.vars.id = '8';
SET session my.vars.objectweight = '5';

SELECT 
time, 
ABS("displacement") * ABS("acceleration") * current_setting('my.vars.objectweight')::FLOAT as "Joules (8)"
FROM 
(
SELECT 
time,
COALESCE(
(displacement - LAG(displacement) OVER (ORDER BY time DESC))/((time - LAG(time) OVER (ORDER BY time DESC))*1000),
-1) AS "acceleration",
displacement
FROM (
SELECT 
("frame_count"*1000/30) + CAST(extract(epoch from (NOW() - INTERVAL '6 HOUR')) as INTEGER) as "time",
(CAST(geometry->>'0X' as FLOAT) + CAST(geometry->>'1X' as FLOAT) + CAST(geometry->>'2X' as FLOAT) + CAST(geometry->>'3X' as FLOAT))/4 as "4X",
(CAST(geometry->>'0Y' as FLOAT) + CAST(geometry->>'1Y' as FLOAT) + CAST(geometry->>'2Y' as FLOAT) + CAST(geometry->>'3Y' as FLOAT))/4 as "4Y",
POINT(
(
COALESCE(CAST(LAG(geometry->>'0X') OVER (ORDER BY "when" DESC) as FLOAT),0) +
COALESCE(CAST(LAG(geometry->>'1X') OVER (ORDER BY "when" DESC) as FLOAT), 0) +
COALESCE(CAST(LAG(geometry->>'2X') OVER (ORDER BY "when" DESC) as FLOAT), 0) + 
COALESCE(CAST(LAG(geometry->>'3X') OVER (ORDER BY "when" DESC) as FLOAT), 0)
)/4,
(
COALESCE(CAST(LAG(geometry->>'0Y') OVER (ORDER BY "when" DESC) as FLOAT),0) +
COALESCE(CAST(LAG(geometry->>'1Y') OVER (ORDER BY "when" DESC) as FLOAT), 0) +
COALESCE(CAST(LAG(geometry->>'2Y') OVER (ORDER BY "when" DESC) as FLOAT), 0) + 
COALESCE(CAST(LAG(geometry->>'3Y') OVER (ORDER BY "when" DESC) as FLOAT), 0)
)/4)
<->
POINT((
COALESCE(CAST((geometry->>'0X') as FLOAT),0) +
COALESCE(CAST((geometry->>'1X') as FLOAT), 0) +
COALESCE(CAST((geometry->>'2X') as FLOAT), 0) + 
COALESCE(CAST((geometry->>'3X') as FLOAT), 0)
)/4, 
(
COALESCE(CAST((geometry->>'0Y') as FLOAT),0) +
COALESCE(CAST((geometry->>'1Y') as FLOAT), 0) +
COALESCE(CAST((geometry->>'2Y') as FLOAT), 0) + 
COALESCE(CAST((geometry->>'3Y') as FLOAT), 0)
)/4) as "displacement"
FROM (
SELECT * FROM samples WHERE aruco_id = current_setting('my.vars.id')::int
ORDER BY "when"
LIMIT ALL
) displacement
LIMIT ALL) "4x"
) "4xSTD",
(
SELECT AVG("acceleration"), STDDEV("acceleration") FROM
(
SELECT 
time,
COALESCE(
(displacement - LAG(displacement) OVER (ORDER BY time DESC))/((time - LAG(time) OVER (ORDER BY time DESC))*1000),
-1) AS "acceleration"
FROM (
SELECT 
("frame_count"*1000/30) + CAST(extract(epoch from (NOW() - INTERVAL '6 HOUR')) as INTEGER) as "time",
(CAST(geometry->>'0X' as FLOAT) + CAST(geometry->>'1X' as FLOAT) + CAST(geometry->>'2X' as FLOAT) + CAST(geometry->>'3X' as FLOAT))/4 as "4X",
(CAST(geometry->>'0Y' as FLOAT) + CAST(geometry->>'1Y' as FLOAT) + CAST(geometry->>'2Y' as FLOAT) + CAST(geometry->>'3Y' as FLOAT))/4 as "4Y",
POINT(
(
COALESCE(CAST(LAG(geometry->>'0X') OVER (ORDER BY "when" DESC) as FLOAT),0) +
COALESCE(CAST(LAG(geometry->>'1X') OVER (ORDER BY "when" DESC) as FLOAT), 0) +
COALESCE(CAST(LAG(geometry->>'2X') OVER (ORDER BY "when" DESC) as FLOAT), 0) + 
COALESCE(CAST(LAG(geometry->>'3X') OVER (ORDER BY "when" DESC) as FLOAT), 0)
)/4,
(
COALESCE(CAST(LAG(geometry->>'0Y') OVER (ORDER BY "when" DESC) as FLOAT),0) +
COALESCE(CAST(LAG(geometry->>'1Y') OVER (ORDER BY "when" DESC) as FLOAT), 0) +
COALESCE(CAST(LAG(geometry->>'2Y') OVER (ORDER BY "when" DESC) as FLOAT), 0) + 
COALESCE(CAST(LAG(geometry->>'3Y') OVER (ORDER BY "when" DESC) as FLOAT), 0)
)/4)
<->
POINT((
COALESCE(CAST((geometry->>'0X') as FLOAT),0) +
COALESCE(CAST((geometry->>'1X') as FLOAT), 0) +
COALESCE(CAST((geometry->>'2X') as FLOAT), 0) + 
COALESCE(CAST((geometry->>'3X') as FLOAT), 0)
)/4, 
(
COALESCE(CAST((geometry->>'0Y') as FLOAT),0) +
COALESCE(CAST((geometry->>'1Y') as FLOAT), 0) +
COALESCE(CAST((geometry->>'2Y') as FLOAT), 0) + 
COALESCE(CAST((geometry->>'3Y') as FLOAT), 0)
)/4) as "displacement"
FROM (
SELECT * FROM samples WHERE aruco_id = current_setting('my.vars.id')::int
ORDER BY "when"
LIMIT ALL
) displacement
LIMIT ALL) "4x"
) "4xSTDa"
) x
WHERE ABS("4xSTD"."acceleration" - x.avg) < x.stddev * 2;
```

