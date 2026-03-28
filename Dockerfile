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
    && rm -rf /var/lib/apt/lists/*

# --- zsh: Oh My Zsh + autocomplete ---
RUN sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended
RUN git clone https://github.com/zsh-users/zsh-autosuggestions \
        ${ZSH_CUSTOM:-/root/.oh-my-zsh/custom}/plugins/zsh-autosuggestions \
    && git clone https://github.com/zsh-users/zsh-completions \
        ${ZSH_CUSTOM:-/root/.oh-my-zsh/custom}/plugins/zsh-completions
RUN sed -i 's/plugins=(git)/plugins=(git zsh-autosuggestions zsh-completions)/' /root/.zshrc

# --- uv (Python package manager) ---
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# --- asdf (version manager for Java, Gradle) ---
RUN git clone https://github.com/asdf-vm/asdf.git /root/.asdf --branch v0.18.0
ENV ASDF_DIR="/root/.asdf"
ENV PATH="$ASDF_DIR/bin:$ASDF_DIR/shims:$PATH"

# Add asdf to zsh
RUN echo '\n. "$ASDF_DIR/asdf.sh"' >> /root/.zshrc \
    && echo 'fpath=(${ASDF_DIR}/completions $fpath)' >> /root/.zshrc \
    && echo 'autoload -Uz compinit && compinit' >> /root/.zshrc

# Install asdf plugins only (versions are managed via .tool-versions or asdf install at runtime)
RUN asdf plugin add java https://github.com/halcyon/asdf-java.git \
    && asdf plugin add gradle https://github.com/rfrancis/asdf-gradle.git

# Install Android SDK command-line tools
ENV ANDROID_HOME="/opt/android-sdk"
RUN mkdir -p $ANDROID_HOME/cmdline-tools \
    && wget -q https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -O /tmp/cmdtools.zip \
    && unzip -q /tmp/cmdtools.zip -d /tmp/cmdtools \
    && mv /tmp/cmdtools/cmdline-tools $ANDROID_HOME/cmdline-tools/latest \
    && rm -rf /tmp/cmdtools /tmp/cmdtools.zip
ENV PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"

# --- System libs required by tensorflow / torch ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    libhdf5-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# --- Install project ---
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY rlmobtest/ ./rlmobtest/

RUN uv sync --frozen --python 3.12

# Make rlmobtest CLI available
ENV PATH="/app/.venv/bin:$PATH"

# OLLAMA_BASE_URL is set by docker-compose to point to the ollama service
ENV OLLAMA_BASE_URL="http://ollama:11434"

SHELL ["/bin/zsh", "-c"]
CMD ["zsh"]
