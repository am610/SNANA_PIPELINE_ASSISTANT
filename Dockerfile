# Use standard, lightweight python base image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies (git, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy package files
COPY pyproject.toml README.md /app/
COPY src /app/src
COPY knowledge /app/knowledge
COPY eval /app/eval
COPY skill /app/skill

# Install package with all LLM backend dependencies
RUN pip install --no-cache-dir .[all]

# Expose package configs and entrypoint
ENV PYTHONPATH="/app/src:${PYTHONPATH}"

# Default entrypoint to the snana-assistant CLI
ENTRYPOINT ["snana-assistant"]

# Instructions for running the container:
#
# 1. Local Docker:
#    docker build -t snana-assistant .
#    docker run --rm -v $(pwd)/.env:/app/.env -v ~/.claude/snana-knowledge:/root/.claude/snana-knowledge snana-assistant diagnose "..."
#
# 2. HPC Singularity:
#    singularity run docker://username/snana-assistant:latest diagnose "..."
