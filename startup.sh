#!/bin/bash
# Azure App Service startup script (native Python runtime)
# Configured via: az webapp config set --startup-file startup.sh
#
# server.py exposes a module-level `app = create_app()` (FastAPI instance).
# Gunicorn + UvicornWorker is the Azure-recommended production server combo.

# Ensure reports directory exists (App Service ephemeral filesystem)
mkdir -p reports

# Start with gunicorn (production) using uvicorn worker class
# server:app  →  filename: server.py, FastAPI object: app
gunicorn -w 2 -k uvicorn.workers.UvicornWorker \
  --bind "0.0.0.0:${PORT:-8000}" \
  --timeout 120 \
  --access-logfile - \
  server:app
