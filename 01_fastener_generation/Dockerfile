
FROM mambaorg/micromamba:2.3.2

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    git xvfb xauth \
    libgl1 libxrender1 libxext6 libxkbcommon-x11-0 \
    libxcb-xinerama0 libxcb-cursor0 libglib2.0-0 libsm6 \
    && rm -rf /var/lib/apt/lists/*

USER $MAMBA_USER

# FreeCAD installieren
RUN micromamba install -y -n base -c conda-forge \
    freecad defusedxml \
    && micromamba clean --all --yes

# Fasteners Workbench herunterladen
RUN mkdir -p /home/mambauser/.local/share/FreeCAD/Mod \
    && git clone --depth 1 \
       https://github.com/shaise/FreeCAD_FastenersWB.git \
       /home/mambauser/.local/share/FreeCAD/Mod/Fasteners

WORKDIR /app

# Generator-Macro und weitere Skripte kopieren
COPY --chown=mambauser:mambauser scripts/ /app/scripts/

# Entrypoint kopieren
COPY --chown=mambauser:mambauser docker/entrypoint.sh /app/entrypoint.sh

RUN sed -i 's/\r$//' /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh \
    && test -f /app/scripts/generate_fasteners.FCMacro

# Datenverzeichnisse
USER root
RUN mkdir -p /data/input /data/output \
    && chown -R mambauser:mambauser /data

USER mambauser

ENV INPUT_CSV=/data/input/fasteners.csv
ENV OUTPUT_DIR=/data/output
ENV QTWEBENGINE_DISABLE_SANDBOX=1
ENV PYTHONUNBUFFERED=1

CMD ["bash", "/app/entrypoint.sh"]
