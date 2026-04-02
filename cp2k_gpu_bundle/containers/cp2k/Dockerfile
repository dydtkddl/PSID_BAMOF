ARG CP2K_BASE_IMAGE=cp2k/cp2k:2024.3_openmpi_generic_cuda_P100_psmp
FROM ${CP2K_BASE_IMAGE}
# <!-- REVIEW-FIX M-09 -->
# Pilot CP2K runtime must use a GPU-capable upstream image.
# 2025.2 CPU-only tags were previously pulled under a misleading local image name.

ARG UID=1000
ARG GID=1000
ARG USER_NAME=operator

USER root
RUN apt-get update && apt-get install -y \
    python3 python3-pip tmux procps jq less \
    && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    GROUP_NAME="${USER_NAME}"; \
    if ! getent group "${USER_NAME}" >/dev/null; then \
      if getent group "${GID}" >/dev/null; then \
        GROUP_NAME="$(getent group "${GID}" | cut -d: -f1)"; \
      else \
        groupadd -g "${GID}" "${USER_NAME}"; \
      fi; \
    fi; \
    if ! id -u "${USER_NAME}" >/dev/null 2>&1; then \
      useradd -o -m -u "${UID}" -g "${GROUP_NAME}" -s /bin/bash "${USER_NAME}"; \
    fi

RUN python3 -m pip install --no-cache-dir \
    rich tqdm alive-progress pyyaml pandas numpy psutil

USER ${USER_NAME}
WORKDIR /workspace
