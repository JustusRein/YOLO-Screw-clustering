
FROM mambaorg/micromamba:2.3.2

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libxrender1 libxext6 libxkbcommon-x11-0 \
    libxcb-xinerama0 libxcb-cursor0 libglib2.0-0 \
    libsm6 libice6 \
    && rm -rf /var/lib/apt/lists/*

USER $MAMBA_USER
RUN micromamba install -y -n base -c conda-forge freecad \
    && micromamba clean --all --yes

WORKDIR /app

COPY --chown=mambauser:mambauser scripts/ /app/scripts/
COPY --chown=mambauser:mambauser docker/entrypoint.sh /app/entrypoint.sh

RUN sed -i 's/\r$//' /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh

USER root
RUN mkdir -p /data/input /data/output \
    && chown -R mambauser:mambauser /data

USER mambauser

ENV INPUT_CSV=/data/input/distractors.csv
ENV OUTPUT_DIR=/data/output
ENV RANDOM_SEED=42
ENV EXPORT_STEP=1
ENV EXPORT_FCSTD=0
ENV PYTHONUNBUFFERED=1

CMD ["bash", "/app/entrypoint.sh"]
