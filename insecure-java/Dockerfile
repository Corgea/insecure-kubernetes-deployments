# syntax=docker/dockerfile:1.7
#
# Build from the repository root:
#   docker build -f insecure-java/Dockerfile -t insecure-java .
#
# The jar is built inside the image, so a local ./gradlew bootJar is no longer
# needed before docker build.

# Base images, pinned by tag and digest. Bump them together so the runtime JRE
# stays on the release the jar was compiled and tested with.
ARG JDK_IMAGE=eclipse-temurin:17.0.20.1_1-jdk-jammy@sha256:43f4431cc895d37ceb115e2e1f160545ec45caee9c1cb4246fc6bb879d58aeda
ARG JRE_IMAGE=eclipse-temurin:17.0.20.1_1-jre-jammy@sha256:8993f1aed8b25fcea7a7047a7949c1866fa558fc6830d938c22c4f13b26be9d7

# Same value as `version` in build.gradle: bootJar names the jar after it.
ARG APP_VERSION=0.0.1-SNAPSHOT

# --- build: Spring Boot jar from source with the Gradle wrapper ---
FROM ${JDK_IMAGE} AS build

WORKDIR /workspace

# Wrapper and build scripts first, so dependency resolution reruns only when the
# build definition changes. Gradle's home is a cache mount: the distribution and
# downloaded jars are kept between builds without being baked into a layer.
COPY insecure-java/gradlew insecure-java/settings.gradle insecure-java/build.gradle ./
COPY insecure-java/gradle ./gradle
RUN --mount=type=cache,target=/root/.gradle,sharing=locked \
    ./gradlew --no-daemon dependencies > /dev/null

COPY insecure-java/src ./src

# Split the fat jar into Spring Boot's layers (dependencies, loader, snapshot
# dependencies, application), so a code-only change rebuilds and pushes just
# the application layer instead of the whole fat jar.
RUN --mount=type=cache,target=/root/.gradle,sharing=locked \
    ./gradlew --no-daemon bootJar \
    && java -Djarmode=layertools -jar "build/libs/insecure-java-${APP_VERSION}.jar" \
        extract --destination /workspace/layers

# --- runtime: JRE only ---
FROM ${JRE_IMAGE}

ARG APP_VERSION

LABEL org.opencontainers.image.title="insecure-java" \
      org.opencontainers.image.description="Spring Boot cat picture app" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.source="https://github.com/Corgea/insecure-kubernetes-deployments"

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app

# Least to most frequently changed, so pulls of a new build reuse the
# dependency layers too.
COPY --from=build /workspace/layers/dependencies/ ./
COPY --from=build /workspace/layers/spring-boot-loader/ ./
COPY --from=build /workspace/layers/snapshot-dependencies/ ./
COPY --from=build /workspace/layers/application/ ./

# Numeric so a pod with runAsNonRoot: true can be admitted; the kubelet cannot
# verify a user name.
USER 10001:10001

EXPOSE 8080

# Size the heap from the container memory limit instead of the host's RAM, and
# exit on OutOfMemoryError so the container is restarted rather than left
# running a JVM that no longer serves requests. Set JAVA_OPTS at run time to
# add or replace flags.
ENV JAVA_OPTS="-XX:MaxRAMPercentage=75 -XX:+ExitOnOutOfMemoryError"

# curl ships with the Temurin Ubuntu images.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["curl", "-fsS", "-o", "/dev/null", "http://127.0.0.1:8080/"]

# The extracted layers are started through Spring Boot's launcher; there is no
# single jar in the image any more.
ENTRYPOINT ["java", "${JAVA_OPTS}", "org.springframework.boot.loader.JarLauncher"]
