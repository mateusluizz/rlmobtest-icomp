# RLMobTest — RL-based Android Testing Tool
# Requires: uv, asdf (Java/Gradle version management), Android SDK
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8

# --- Base system dependencies + zsh ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    unzip \
    zip \
    wget \
    ca-certificates \
    gnupg \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    libffi-dev \
    lzma \
    liblzma-dev \
    zsh \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# --- Root password (passed via build arg) ---
ARG ROOT_PASSWORD=changeme
RUN echo "root:${ROOT_PASSWORD}" | chpasswd

# --- Non-root user ---
RUN useradd -m -s /bin/zsh rlmob \
    && echo 'rlmob ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

# --- uv (installed system-wide) ---
RUN curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin sh
ENV PATH="/usr/local/bin:$PATH"

# --- asdf (installed in /opt for all users) ---
RUN git clone https://github.com/asdf-vm/asdf.git /opt/asdf --branch v0.18.0 \
    && chown -R rlmob:rlmob /opt/asdf
ENV ASDF_DIR="/opt/asdf"
ENV PATH="$ASDF_DIR/bin:$ASDF_DIR/shims:$PATH"

# Install asdf plugins (as root, PATH already includes /opt/asdf/bin)
RUN asdf plugin add java https://github.com/halcyon/asdf-java.git \
    && asdf plugin add gradle https://github.com/rfrancis/asdf-gradle.git

# --- Oh My Zsh + plugins for rlmob ---
ENV HOME_RLMOB="/home/rlmob"
RUN HOME=$HOME_RLMOB sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended \
    && git clone https://github.com/zsh-users/zsh-autosuggestions \
        $HOME_RLMOB/.oh-my-zsh/custom/plugins/zsh-autosuggestions \
    && git clone https://github.com/zsh-users/zsh-completions \
        $HOME_RLMOB/.oh-my-zsh/custom/plugins/zsh-completions \
    && sed -i 's/plugins=(git)/plugins=(git zsh-autosuggestions zsh-completions)/' $HOME_RLMOB/.zshrc

# Add asdf + PATH to rlmob's zsh
RUN echo '\n. "/opt/asdf/asdf.sh"' >> /home/rlmob/.zshrc \
    && echo 'fpath=(/opt/asdf/completions $fpath)' >> /home/rlmob/.zshrc \
    && echo 'autoload -Uz compinit && compinit' >> /home/rlmob/.zshrc \
    && echo 'export PATH="/usr/local/bin:/app/.venv/bin:$PATH"' >> /home/rlmob/.zshrc

# --- openjdk-17 for sdkmanager ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jdk-headless \
    && rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME="/usr/lib/jvm/java-17-openjdk-amd64"

# --- Android SDK command-line tools + platform-tools (adb) ---
ENV ANDROID_HOME="/opt/android-sdk"
RUN mkdir -p $ANDROID_HOME/cmdline-tools \
    && wget -q https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -O /tmp/cmdtools.zip \
    && unzip -q /tmp/cmdtools.zip -d /tmp/cmdtools \
    && mv /tmp/cmdtools/cmdline-tools $ANDROID_HOME/cmdline-tools/latest \
    && rm -rf /tmp/cmdtools /tmp/cmdtools.zip
ENV PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"
RUN yes | sdkmanager --licenses > /dev/null && sdkmanager "platform-tools" \
    && chown -R rlmob:rlmob $ANDROID_HOME

# --- System libs required by tensorflow / torch + gosu (entrypoint user drop) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    libhdf5-dev \
    libgomp1 \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# --- Install project as rlmob so venv has correct ownership ---
RUN mkdir -p /app && chown rlmob:rlmob /app
WORKDIR /app

USER rlmob
COPY --chown=rlmob:rlmob pyproject.toml uv.lock README.md ./
COPY --chown=rlmob:rlmob rlmobtest/ ./rlmobtest/
RUN uv sync --frozen --python 3.12

# Make rlmobtest CLI available
ENV PATH="/app/.venv/bin:$PATH"

ENV OLLAMA_BASE_URL="http://localhost:11434"

# Entrypoint fixes volume permissions at startup
USER root
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

SHELL ["/bin/zsh", "-c"]
ENTRYPOINT ["/entrypoint.sh"]
CMD ["zsh"]
