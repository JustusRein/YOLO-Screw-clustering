FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
ARG BLENDER_VERSION=4.5.0
ENV BLENDER_DIR=/opt/blender-${BLENDER_VERSION}-linux-x64
ENV PATH=${BLENDER_DIR}:${PATH}
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/opt

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl xz-utils git libx11-6 libxi6 libxrender1 libxfixes3 \
    libxkbcommon0 libsm6 libgl1 libglu1-mesa libgomp1 libegl1 libwayland-client0 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL "https://download.blender.org/release/Blender4.5/blender-${BLENDER_VERSION}-linux-x64.tar.xz" \
    -o /tmp/blender.tar.xz \
    && tar -xJf /tmp/blender.tar.xz -C /opt \
    && rm /tmp/blender.tar.xz

# StepForge provides STEP parsing, tessellation and assembly transforms.
RUN git clone --depth 1 https://github.com/RandomLambda/StepForge.git /opt/stepforge

WORKDIR /workspace
COPY scripts/metadata.py /workspace/metadata.py
COPY scripts/generate_step_dataset.py /workspace/generate_step_dataset.py
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
