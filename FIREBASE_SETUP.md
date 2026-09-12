# Firebase Analytics & Authentication Setup

This project now includes Firebase Analytics and Firebase Authentication with JSON-based service account authentication for the backend.

## Client Configuration

The web UI uses the Firebase Web SDK (v12.19.0) loaded via CDN:

- **Analytics**: `getAnalytics(app)` initialized on each page
- **Authentication**: Google Sign-In via popup, token verified server-side
- **Config**: Served publicly via `/api/auth/firebase-config` (values from cookiecucci project)

Frontend initialization is handled by `static/firebase-init.js` and auto-injected into all static pages.

## Backend JSON Authentication

Server-side verification uses Firebase Admin SDK with a service account JSON file.

### 1. Create `firebase_service_account.json`

Download a service account key from Firebase Console:
Project Settings → Service Accounts → Generate new private key

Save the file as `firebase_service_account.json` in project root (gitignored).

Set env var if using custom path:
```bash
export FIREBASE_SERVICE_ACCOUNT_PATH=/path/to/firebase_service_account.json
```

Example placeholder: `firebase_service_account.json.example`

### 2. Install dependencies

```bash
pip install -r requirements.txt
# firebase-admin will be installed
```

### 3. Endpoints

- `GET /api/auth/firebase-config` → public client config
- `GET /api/auth/status` → check if Admin SDK initialized
- `POST /api/auth/verify-token` → verify Firebase ID token
  ```json
  { "idToken": "eyJ..." }
  ```

### 4. Analytics Events

Built-in events logged:
- `page_view` on init
- `login` on successful Google sign-in
- `click` events for outbound links

You can extend tracking in `firebase-init.js` or page scripts using `logEvent`.

## Security Notes

- `firebase_service_account.json` is gitignored. Never commit secrets.
- Client config (apiKey) is public by design.
- Backend token verification ensures only authenticated users can access protected API routes.

## Quick Test

Start server:
```bash
python3 run.py --ui
```

Open http://localhost:8000
- Sign in via header Sign in button
- Check `/api/auth/status` → `{"initialized": true, ...}` if service account present
