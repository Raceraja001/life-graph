# JVM sandbox image for the verifier chain (life_graph/services/sandbox.py),
# used for projects whose registry sets `sandbox_toolchain: jvm` — Kotlin,
# Java and Android projects built with Gradle.
#
# Same contract as docker/verifier: checks run here read-only and with no
# network. Gradle and the project's dependencies are not baked in: the setup
# phase (network on) runs the project's wrapper once into a cached Gradle
# home, and checks read it read-only (GRADLE_RO_DEP_CACHE) and run Gradle from
# the cached distribution, offline.
#
# Carries the Android SDK pieces a unit-test build needs (platform and build
# tools), so an Android project's JVM unit tests run without an emulator.
#
# Build:  docker build -t life-graph-verifier:jvm17 docker/verifier-jvm
FROM eclipse-temurin:17-jdk

ARG CMDLINE_TOOLS=11076708
ARG ANDROID_PLATFORM=android-35
ARG BUILD_TOOLS=35.0.0
ENV ANDROID_HOME=/opt/android-sdk \
    ANDROID_SDK_ROOT=/opt/android-sdk

# git: test suites and Gradle plugins commonly read the repository.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/android-sdk/cmdline-tools \
    && curl -fsSL -o /tmp/tools.zip \
       "https://dl.google.com/android/repository/commandlinetools-linux-${CMDLINE_TOOLS}_latest.zip" \
    && unzip -q /tmp/tools.zip -d /tmp/tools \
    && mv /tmp/tools/cmdline-tools /opt/android-sdk/cmdline-tools/latest \
    && rm -rf /tmp/tools /tmp/tools.zip \
    && yes | /opt/android-sdk/cmdline-tools/latest/bin/sdkmanager --licenses > /dev/null \
    && /opt/android-sdk/cmdline-tools/latest/bin/sdkmanager \
       "platforms;${ANDROID_PLATFORM}" "build-tools;${BUILD_TOOLS}" > /dev/null \
    && chmod -R a+rX /opt/android-sdk

# Never run as root; the sandbox also passes --user explicitly.
USER 65534:65534
WORKDIR /work
