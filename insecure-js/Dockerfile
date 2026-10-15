# syntax=docker/dockerfile:1.7
#
# Build from the repository root:
#   docker build -f insecure-js/Dockerfile -t insecure-js .

# Base images, pinned by tag and digest. Keep both on the same Node release
# and Debian suite.
ARG NODE_BUILD_IMAGE=node:22.23.3-bookworm@sha256:0e5f906573693feaa1e21057ebdcfdb5bd5021f050b2dc7c9deceb629c7da2a8
ARG NODE_RUNTIME_IMAGE=node:22.23.3-bookworm-slim@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392

# --- deps: production node_modules, built against the runtime's glibc ---
# Runs on the builder's own platform, so a multi-platform build does not run
# npm ci under QEMU emulation.
FROM --platform=$BUILDPLATFORM ${NODE_BUILD_IMAGE} AS deps

WORKDIR /app

# sqlite3 falls back to a node-gyp build when no prebuilt binary matches the
# platform; the full bookworm image already has python3, make and g++ for that.
# npm's cache is a cache mount, so it is reused across builds and never ends up
# in a layer.
COPY insecure-js/package.json insecure-js/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm,sharing=locked \
    npm ci --omit=dev --legacy-peer-deps --no-audit --no-fund

# --- runtime ---
FROM ${NODE_RUNTIME_IMAGE}

LABEL org.opencontainers.image.title="insecure-js" \
      org.opencontainers.image.description="Node.js demo app backed by SQLite" \
      org.opencontainers.image.source="https://github.com/Corgea/insecure-kubernetes-deployments"

# tini runs as PID 1 so SIGTERM reaches node and exited children are reaped.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*

ENV NODE_ENV=production
# overridden at deploy time
ENV SESSION_SECRET=prod-7f3e9c2a51b84d06a1c9e0f4b2d8a6c3

WORKDIR /app

# init_db.js and server.js create data.db in the working directory, so the
# node user owns the directory; the code and node_modules stay root-owned.
RUN chown node:node /app

# Dependencies before sources: they change far less often.
COPY --from=deps /app/node_modules ./node_modules
COPY insecure-js/package.json insecure-js/init_db.js insecure-js/server.js insecure-js/styles.css ./

# Numeric so a pod with runAsNonRoot: true can be admitted; the kubelet cannot
# verify a user name. 1000 is the node user in the official images.
USER 1000:1000

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["node", "-e", "require('http').get('http://127.0.0.1:3000/styles.css', (res) => process.exit(res.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"]

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sh", "-c", "node init_db.js && exec node server.js"]
