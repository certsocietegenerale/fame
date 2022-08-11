# Docker support

This is probably the quickest way to spawn a Fame dev instance.

## Install docker

Follow the [official instructions](https://www.docker.com/community-edition).

## Clone the repo

    $ git clone https://github.com/certsocietegenerale/fame/

## Run docker image

    $ cd fame/docker
    $ cp fame.env.template fame.env
    $ echo "DEFAULT_EMAIL=admin@changeme.fame" >> fame.env
    $ echo "DEFAULT_PASSWORD=changeme" >> fame.env
    $ docker-compose up --build
