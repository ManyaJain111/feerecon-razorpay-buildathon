# Frontend Deployment Guide (Vercel)

This frontend is a single-page payment gateway contract audit & dispute dashboard.

## Option A: Deploy with Vercel CLI (Fastest)

1. Install Vercel CLI:
   ```bash
   npm i -g vercel
   ```

2. Deploy the `frontend/` directory:
   ```bash
   cd frontend
   vercel
   ```

3. To deploy to production:
   ```bash
   vercel --prod
   ```

## Option B: Deploy via GitHub on Vercel Dashboard

1. Push your repository to GitHub.
2. In Vercel, click **Add New Project** and import your repository.
3. In **Project Settings**:
   - **Root Directory**: Select `frontend`
   - **Framework Preset**: `Other`
   - **Build Command**: (Leave empty)
   - **Output Directory**: (Leave empty or `.`)
4. Click **Deploy**.

## Connecting to your Backend

When deployed, open your Vercel URL and click the **Backend** button in the top navigation bar. Enter your deployed backend URL (e.g. `https://feerecon-backend.onrender.com`). It will verify the connection (`/health`) and save the configuration in your browser's local storage.
