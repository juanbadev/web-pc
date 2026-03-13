FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=America/New_York

RUN apt-get update && apt-get install -y \
    ttyd \
    bash \
    vim \
    nano \
    curl \
    wget \
    git \
    python3 \
    python3-pip \
    htop \
    tree \
    net-tools \
    iputils-ping \
    sudo \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for safety
RUN useradd -m -s /bin/bash -u 1000 linuxuser \
    && echo "linuxuser:linuxuser" | chpasswd \
    && usermod -aG sudo linuxuser \
    && echo "linuxuser ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Create welcome message
RUN echo '#!/bin/bash\n\
echo ""\n\
echo "  ╔══════════════════════════════════════╗"\n\
echo "  ║     Bienvenido a tu Linux Cloud      ║"\n\
echo "  ║   Tu entorno privado en el navegador ║"\n\
echo "  ╚══════════════════════════════════════╝"\n\
echo ""\n\
echo "  Usuario: $(whoami)"\n\
echo "  Fecha:   $(date)"\n\
echo "  Sistema: Ubuntu 22.04 LTS"\n\
echo ""\n\
exec bash' > /usr/local/bin/entrypoint.sh && chmod +x /usr/local/bin/entrypoint.sh

# .bashrc personalizado
RUN echo 'export PS1="\[\033[01;32m\]linuxuser@cloud\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ "' >> /home/linuxuser/.bashrc \
    && echo 'alias ll="ls -la --color=auto"' >> /home/linuxuser/.bashrc \
    && echo 'alias la="ls -A --color=auto"' >> /home/linuxuser/.bashrc \
    && echo 'echo "Escribe '\''help'\'' para ver comandos disponibles"' >> /home/linuxuser/.bashrc

USER linuxuser
WORKDIR /home/linuxuser

EXPOSE 7681

CMD ["ttyd", "-p", "7681", "--writable", "--credential", "user:cloud123", "/usr/local/bin/entrypoint.sh"]
