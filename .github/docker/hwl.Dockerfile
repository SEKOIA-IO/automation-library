# Image of the HWL actions of a module: the runner image plus the module
# manifest and its action_*.yml files. Build context: the module directory.
ARG HWL_BASE_IMAGE
FROM ${HWL_BASE_IMAGE}
COPY --chown=nonroot:nonroot manifest.json action_*.yml /app/
