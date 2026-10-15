# syntax=docker/dockerfile:1.7
#
# Build from the repository root:
#   docker build -f workload-security-evaluator/Dockerfile -t workload-security-evaluator .

FROM ubuntu:jammy-20260924.1@sha256:5ec03bb3441e8b0bf3b4f9cd4629a1ae763010dc3035bb8da3ae6cf026486401

ARG DEBIAN_FRONTEND=noninteractive
# Release tag the Invoke-AtomicRedTeam installer is fetched from.
ARG ATOMIC_RED_TEAM_VERSION=v2.0.0.0

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# PowerShell from the Microsoft feed for this Ubuntu release. /etc/os-release
# gives the version, so lsb-core and software-properties-common are not needed.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates wget \
    && . /etc/os-release \
    && wget -q "https://packages.microsoft.com/config/ubuntu/${VERSION_ID}/packages-microsoft-prod.deb" \
    && dpkg -i packages-microsoft-prod.deb \
    && rm packages-microsoft-prod.deb \
    && apt-get update \
    && apt-get install -y --no-install-recommends powershell

# Tools the atomics call. libc6-dev is only a Recommends of gcc, so it is listed
# explicitly for the tests that compile C payloads.
# The apt lists are kept: the runtime exercises in the top-level README install
# extra packages (apt-get install netcat) without running apt-get update first.
RUN apt-get install -y --no-install-recommends \
        clang \
        curl \
        gcc \
        iproute2 \
        kmod \
        libc6-dev \
        make \
        nmap \
        sudo

# Invoke-AtomicRedTeam and the atomics.
RUN pwsh -NoLogo -NonInteractive -Command \
    "IEX (IWR 'https://raw.githubusercontent.com/redcanaryco/invoke-atomicredteam/${ATOMIC_RED_TEAM_VERSION}/install-atomicredteam.ps1' -UseBasicParsing); Install-AtomicRedTeam -getAtomics"

# Import the Invoke-AtomicRedTeam module automatically in every pwsh session.
RUN mkdir -p /root/.config/powershell \
    && echo 'Import-Module "/root/AtomicRedTeam/invoke-atomicredteam/Invoke-AtomicRedTeam.psd1" -Force' \
        > /root/.config/powershell/profile.ps1

# Runs as root on purpose: the atomics load kernel modules, edit cron and
# write under /etc, which is the behaviour the runtime sensors are tested on.
CMD ["sleep", "infinity"]
