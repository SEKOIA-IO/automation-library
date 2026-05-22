# [Choice] Python version
FROM python:3.11-bookworm

# 1. Update package index and remove unwanted packages, then clean APT cache
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get purge -y imagemagick imagemagick-6-common \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 2. Upgrade core packages and install dev tools
RUN python3 -m pip install --no-cache-dir --upgrade \
    pip \
    setuptools==78.1.0 \
    gitpython==3.1.41 \
    poetry \
    pre-commit
