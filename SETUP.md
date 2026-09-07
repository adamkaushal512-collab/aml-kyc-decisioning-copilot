# Setup

Basic instructions for running the backend and frontend locally. See
[`README.md`](./README.md) for the project overview and
[`ARCHITECTURE.md`](./ARCHITECTURE.md) for the pipeline design.

## Backend (Python/FastAPI)

Requires Python 3.12+.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`. Check
`http://localhost:8000/health` to confirm it's running.

## Frontend (TypeScript/React via Vite)

Requires Node 20+.

```bash
cd frontend
npm install
npm run dev
```

The app will be available at the URL Vite prints (typically
`http://localhost:5173`).

## Status

Both are early scaffolds: the backend exposes only a `/health` endpoint and
the frontend is the default Vite + React + TypeScript template with no
custom components yet. See `README.md` for overall project status.
