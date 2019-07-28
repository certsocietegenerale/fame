To build docker image named famedev:
docker build -t famedev:latest .

To run container based on famedev image with docker inception (bind docker socket and bind fame temp dir) :
docker run -it -v /var/run/docker.sock:/var/run/docker.sock -v /opt/fame/temp:/opt/fame/temp --name famedev -p 4200:4200 famedev:latest /bin/bash

