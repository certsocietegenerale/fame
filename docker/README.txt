To build docker image with famedev name:
docker build -t famedev ./docker

To run container based on famedev image with docker inception:
docker run -it -v /var/run/docker.sock:/var/run/docker.sock famedev
