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
  netcat-traditional \
  ca-certificates \
  curl \
  gnupg2 \
  pkg-config \
  libvirt-dev \
  sudo \
  unzip \
  lsb-release \
  protobuf-compiler

RUN curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc && \
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(lsb_release -cs) stable" >> /etc/apt/sources.list.d/docker.list && \
    apt update && DEBIAN_FRONTEND=noninteractive apt install -y \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    default-jdk


RUN curl -o /bin/wait-for https://raw.githubusercontent.com/eficode/wait-for/master/wait-for && \
    chmod +x /bin/wait-for

RUN groupadd -r fame && \
    useradd -M -r -d /opt/fame -g fame -G docker fame && \
    install -d -m 0755 -o fame -g fame /opt/fame && \
    echo 'fame ALL=(root) NOPASSWD: /usr/bin/dockerd ""' > /etc/sudoers.d/fame && \
    echo 'fame ALL=(root) NOPASSWD: /bin/rm -f /var/run/docker.sock /var/run/docker/containerd/containerd.sock /var/run/docker.pid /var/run/docker/containerd/containerd.pid' >> /etc/sudoers.d/fame

COPY . /opt/fame

RUN chown -R fame:fame /opt/fame

USER fame

RUN cd /opt/fame && mkdir -p env storage temp && pip3 install virtualenv --break-system-packages \
    && git config --global user.name fame && git config --global user.email git@fame

CMD ["/opt/fame/docker/docker-entrypoint.sh", "web"]
EXPOSE 4200
