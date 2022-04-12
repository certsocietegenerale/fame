FROM debian:latest

WORKDIR /opt

ENV PYTHONUNBUFFERED=1

RUN apt update && \
  apt upgrade -y && \
  DEBIAN_FRONTEND=noninteractive apt install -y \
  git \
  python3-dev \
  python3-pip \
  screen \
  p7zip-full \
  libjpeg-dev \
  zlib1g-dev \
  libmagic-dev \
  apt-transport-https \
  netcat \
  ca-certificates \
  curl \
  gnupg2 \
  pkg-config \
  libvirt-dev \
  sudo \
  software-properties-common

RUN curl -fsSL https://download.docker.com/linux/debian/gpg | apt-key add - && \
    add-apt-repository \
    "deb [arch=amd64] https://download.docker.com/linux/debian \
    $(lsb_release -cs) \
    stable"

RUN curl -o /bin/wait-for https://raw.githubusercontent.com/eficode/wait-for/master/wait-for && \
    chmod +x /bin/wait-for

RUN apt-get update && apt-get install -y \
    docker-ce \
    docker-ce-cli \
    containerd.io


RUN groupadd -r fame && \
    useradd -M -r -d /opt/fame -g fame -G docker fame && \
    install -d -m 0755 -o fame -g fame /opt/fame && \
    echo 'fame ALL=(root) NOPASSWD: /usr/bin/dockerd ""' > /etc/sudoers.d/fame

COPY . /opt/fame

RUN chown -R fame:fame /opt/fame

USER fame

RUN  pip3 install virtualenv && \
    /opt/fame/utils/run.sh

CMD ["/opt/fame/docker/docker-entrypoint.sh", "web"]
EXPOSE 4200
