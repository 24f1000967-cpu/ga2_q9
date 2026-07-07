# Orders API
 
FastAPI service demonstrating idempotent POST, cursor pagination, and per-client rate limiting.
 
- T (catalog size) = 51
- R (rate limit) = 19 requests / 10s per X-Client-Id
## Run locally
```
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```
 
## Deploy on Render (free, ~2 min)
1. Push this folder to a new GitHub repo.
2. Go to https://render.com -> New -> Web Service -> connect the repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Deploy. Render gives you a public URL like `https://your-app.onrender.com`.
**Note:** this repo includes a `runtime.txt` pinning `python-3.11.9`. Render's
default Python (3.14 as of writing) doesn't yet have a prebuilt wheel for
`pydantic-core`, which makes pip try to compile it from source and fail
(`Read-only file system` / maturin error). Pinning to 3.11 avoids that
entirely since prebuilt wheels exist for it. If Render ignores `runtime.txt`,
set the Python version explicitly in the service's Environment settings instead.
 
## Deploy on Railway (also ~2 min)
1. https://railway.app -> New Project -> Deploy from GitHub repo (or `railway up` from this folder with the Railway CLI).
2. Railway auto-detects the Procfile and Python app.
3. It gives you a public URL automatically.
## Endpoints
- `POST /orders` with header `Idempotency-Key: <k>` and `X-Client-Id: <id>`
- `GET /orders?limit=P&cursor=C` with header `X-Client-Id: <id>`
