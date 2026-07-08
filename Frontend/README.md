# ResumePilot Frontend

Next.js dashboard for the local ResumePilot MVP.

## Stack

- Next.js App Router
- React and TypeScript
- Tailwind CSS
- Server route handlers as a backend-for-frontend proxy to FastAPI

## Local setup

```bash
cd Frontend
cp .env.example .env
npm install
npm run dev
```

Default frontend URL:

```text
http://127.0.0.1:3000
```

The dashboard expects FastAPI to be running at `RESUMEPILOT_API_BASE_URL`, defaulting to:

```text
http://127.0.0.1:8002
```

## OpenClaw WebChat / dashboard path

The dashboard is aligned with the OpenClaw local Gateway flow:

```bash
openclaw models set google-vertex/<model-id>
openclaw gateway run --bind loopback
openclaw dashboard
```

Keep Google Cloud credentials and OpenClaw gateway tokens in local environment or OpenClaw config, not in Git.
