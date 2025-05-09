# Stage 1: Build base image with heavy dependencies
FROM mcr.microsoft.com/mirror/docker/library/ubuntu:22.04 AS base
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    wget \
    curl \
    unzip \
    xvfb \
    pulseaudio \
    ffmpeg \
    libnss3 \
    libnss3-tools \
    libgbm1 \
    libasound2 \
    portaudio19-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

# Build and install portaudio
RUN wget http://files.portaudio.com/archives/pa_stable_v190700_20210406.tgz \
    && tar -xvf pa_stable_v190700_20210406.tgz \
    && mv portaudio /usr/src/ \
    && cd /usr/src/portaudio \
    && ./configure \
    && make \
    && make install \
    && ldconfig

# Install Python packages that take time to build
RUN pip3 install pyaudio opencv-python-headless Pillow

# Stage 2: Final image
FROM base AS final

# Create app directories
RUN mkdir -p /app /app/recordings /app/screenshots
WORKDIR /app

# Set up audio and display
RUN usermod -aG audio root \
    && adduser root pulse-access \
    && mkdir -p /run/dbus \
    && chmod 755 /run/dbus \
    && rm -rf /var/run/pulse /var/lib/pulse /root/.config/pulse \
    && dbus-daemon --system --fork \
    && mkdir -p /var/run/dbus \
    && dbus-uuidgen > /var/lib/dbus/machine-id \
    && touch /root/.Xauthority \
    && chmod 600 /root/.Xauthority

# Set environment variables
ENV DISPLAY=:99 \
    DBUS_SESSION_BUS_ADDRESS=unix:path=/run/dbus/system_bus_socket \
    XDG_RUNTIME_DIR=/run/user/0 \
    X_SERVER_NUM=1 \
    SCREEN_WIDTH=1280 \
    SCREEN_HEIGHT=1024 \
    SCREEN_RESOLUTION=1280x1024 \
    COLOR_DEPTH=24

# Copy requirements first to leverage Docker cache
COPY requirements.txt /app/
RUN pip3 install -r requirements.txt

# Copy application files
COPY . /app/
RUN chmod +x /app/entrypoint.sh

# Copy pulseaudio config
RUN mv pulseaudio.conf /etc/dbus-1/system.d/pulseaudio.conf

ENTRYPOINT ["/app/entrypoint.sh"]


