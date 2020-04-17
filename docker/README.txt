# Docker support

This is probably the quickest way to spawn a Fame dev instance.

## Install docker

Follow the [official instructions](https://www.docker.com/community-edition).

## Clone the repo

    $ git clone https://github.com/certsocietegenerale/fame/
    $ cd fame/docker

## Build docker image

    $ docker build -t famedev:latest .

## Run docker image

To run container based on famedev image with docker inception (bind docker socket and bind fame temp dir).
So chose a temp directory on your system and use the following command.

    $ docker run -it -v /var/run/docker.sock:/var/run/docker.sock -v <FIXME local temp dir path>:/opt/fame/temp --name famedev -p 4200:4200 famedev:latest
