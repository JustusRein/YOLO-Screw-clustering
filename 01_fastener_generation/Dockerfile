
FROM mambaorg/micromamba:2.3.2

USER root

RUN apt-get update && apt-get install -y \
    git \
    xvfb \
    libgl1 \
    libxrender1 \
    libxext6 \
    libxkbcommon-x11-0 \
    libxcb-xinerama0 \
    libxcb-cursor0 \
    libglib2.0-0 \
    libsm6 \
    libice6 \
    && rm -rf /var/lib/apt/lists/*

USER $MAMBA_USER

# Install FreeCAD and missing Python dependency
RUN micromamba install -y -n base \
    -c conda-forge \
    freecad \
    defusedxml \
    && micromamba clean --all --yes

# Install Fasteners Workbench
RUN mkdir -p \
    /home/mambauser/.local/share/FreeCAD/Mod \
    && git clone --depth 1 \
    https://github.com/shaise/FreeCAD_FastenersWB.git \
    /home/mambauser/.local/share/FreeCAD/Mod/Fasteners

WORKDIR /app

COPY --chown=mambauser:mambauser scripts/ /app/scripts/
COPY --chown=mambauser:mambauser run.sh /app/run.sh

# Fix Windows line endings
RUN sed -i 's/\r$//' /app/run.sh \
    && chmod +x /app/run.sh

USER root

RUN mkdir -p /data/input /data/output \
    && chown -R mambauser:mambauser /data

USER mambauser

ENV INPUT_CSV=/data/input/fasteners.csv
ENV OUTPUT_DIR=/data/output
ENV QTWEBENGINE_DISABLE_SANDBOX=1

CMD ["bash", "/app/run.sh"]
