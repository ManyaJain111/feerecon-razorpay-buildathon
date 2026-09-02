# Backend Deployment Guide (Render / Docker)

The backend is a FastAPI service that performs deterministic fee arithmetic, multi-format PDF parsing (`poppler-utils`), reconciliation, and dispute claim generation.

## Option A: 1-Click Deploy to Render

1. Push your repository to GitHub.
2. In Render, go to **Blueprints** -> **New Blueprint Instance**.
3. Select your repository. Render will automatically read `render.yaml` and set up the Docker web service.
4. Once deployed, Render provides a URL (e.g. `https://feerecon-backend.onrender.com`).
5. Verify health: `https://feerecon-backend.onrender.com/health` returns `{"status":"ok","service":"fee-recon-backend"}`.

## Option B: Deploy via Docker (Any VPS / Railway / Fly.io)

1. Build the image:
   ```bash
   docker build -t feerecon-backend:latest .
   ```

2. Run the container:
   ```bash
   docker run -d -p 8000:8000 -v $(pwd)/reports:/app/reports --name feerecon feerecon-backend:latest
   ```

## Local Development

Run directly with uvicorn:
```bash
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```
Interactive OpenAPI documentation will be available at `http://localhost:8000/docs`.
