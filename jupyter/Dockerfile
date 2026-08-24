FROM quay.io/jupyter/minimal-notebook:latest

USER root

# Install system build tools, git, curl, and process tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    rsync \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager for ultra-fast venv management in terminal
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh

USER ${NB_UID}

# Install pure IDE extensions, visual Git, diff tools, formatting, and GPU gateway
RUN pip install --no-cache-dir \
    "jupyter-collaboration>=3.0.0" \
    "jupyterlab-git>=0.50.0" \
    "nbdime>=4.0.0" \
    "jupyterlab-code-formatter>=3.0.0" \
    "jupyter-resource-usage>=1.1.0" \
    "remote_ikernel" \
    "ruff" \
    "black" \
    "isort"

USER root

# Inject Dynamic Kernel Auto-Discovery and GitLab OAuth SSO modules
COPY dynamic_kernels.py /etc/jupyter/dynamic_kernels.py
COPY gitlab_auth.py /etc/jupyter/gitlab_auth.py
COPY jupyter_server_config.py /etc/jupyter/jupyter_server_config.py

# Fix permissions
RUN chown -R ${NB_UID}:${NB_GID} /etc/jupyter

USER ${NB_UID}

WORKDIR /home/jovyan/work
