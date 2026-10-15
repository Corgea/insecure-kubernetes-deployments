# syntax=docker/dockerfile:1.7
#
# Build from the repository root:
#   docker build -f insecure-java/Dockerfile -t insecure-java .
#
# The jar is built inside the image, so a local ./gradlew bootJar is no longer
# needed before docker build.

# --- build: Spring Boot jar from source with the Gradle wrapper ---
FROM eclipse-temurin:17.0.20.1_1-jdk-jammy@sha256:43f4431cc895d37ceb115e2e1f160545ec45caee9c1cb4246fc6bb879d58aeda AS build

WORKDIR /workspace

# Wrapper and build scripts first: the Gradle distribution and dependency
# downloads stay cached until the build definition changes.
COPY insecure-java/gradlew insecure-java/settings.gradle insecure-java/build.gradle ./
COPY insecure-java/gradle ./gradle
RUN ./gradlew --no-daemon dependencies > /dev/null

COPY insecure-java/src ./src
RUN ./gradlew --no-daemon bootJar \
    && cp build/libs/insecure-java-0.0.1-SNAPSHOT.jar /workspace/app.jar

# --- runtime: JRE only ---
FROM eclipse-temurin:17.0.20.1_1-jre-jammy@sha256:8993f1aed8b25fcea7a7047a7949c1866fa558fc6830d938c22c4f13b26be9d7

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app

COPY --from=build /workspace/app.jar ./app.jar

USER app

EXPOSE 8080

# curl ships with the Temurin Ubuntu images.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["curl", "-fsS", "-o", "/dev/null", "http://127.0.0.1:8080/"]

# Size the heap from the container memory limit instead of the host's RAM.
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75", "-jar", "/app/app.jar"]
