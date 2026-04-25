# Deploying ProcureFlow on Render — 5-minute guide

You only need to do this **once**. From then on every `git push` to your `main` branch auto-deploys.

---

## What you need before you start

1. **GitHub repo** with this code (you already have it ✅)
2. A **Render account** (free): https://render.com
3. A **MongoDB Atlas** cluster (free M0): https://cloud.mongodb.com
   - Click *Build a Database* → **M0 Free** → choose Singapore region
   - *Database Access* → add user `procureflow` with a password
   - *Network Access* → "Allow access from anywhere" `0.0.0.0/0`
   - *Connect* → *Drivers* → copy the connection string. Looks like:
     `mongodb+srv://procureflow:<pw>@cluster0.xxxx.mongodb.net/?retryWrites=true&w=majority`

That's the only manual prep — Render handles the rest.

---

## Step 1 · Apply the Blueprint (creates 3 services in 1 click)

1. In Render dashboard click **New +** (top right) → **Blueprint**.
2. Connect the GitHub repo that contains this code.
3. Render reads `render.yaml` and shows you the 3 services it'll create:
   - `procureflow-api`   (Web Service — backend + Celery)
   - `procureflow-web`   (Static Site — React)
   - `procureflow-redis` (Key Value — Redis)
4. It will ask you for the values marked `sync: false` — fill these and click **Apply**:

   | Variable | What to put |
   |---|---|
   | `MONGO_URL` | The connection string from MongoDB Atlas |
   | `ADMIN_EMAIL` | Your email (becomes the seeded admin user) |
   | `ADMIN_PASSWORD` | Strong password — change after first login |
   | `EMERGENT_LLM_KEY` | `sk-emergent-…` (from your Emergent profile) |

   Leave these **blank** for now — we'll fill them in step 2:
   - `FRONTEND_URL`
   - `CORS_ORIGINS`
   - `REACT_APP_BACKEND_URL`

   Leave `RESEND_API_KEY` blank to disable email sending (UI returns a polite 503).

5. Click **Apply**. Render builds and deploys everything (~5–8 min).

---

## Step 2 · Wire frontend ↔ backend URLs (1 minute, one time)

After the first deploy you'll see two URLs in the dashboard:

- Backend: `https://procureflow-api-XXXX.onrender.com`
- Frontend: `https://procureflow-web-XXXX.onrender.com`

Now plug them in:

1. Open **procureflow-api** → *Environment* → set:
   - `FRONTEND_URL` = `https://procureflow-web-XXXX.onrender.com`
   - `CORS_ORIGINS` = `https://procureflow-web-XXXX.onrender.com`
   - Click *Save Changes*. Render auto-restarts the API.

2. Open **procureflow-web** → *Environment* → set:
   - `REACT_APP_BACKEND_URL` = `https://procureflow-api-XXXX.onrender.com`
   - Click *Save Changes* → *Manual Deploy → Deploy latest commit* (the static site rebuilds with the new value baked in).

That's it.

---

## Step 3 · Log in and change the seed password

Open the frontend URL → log in with `ADMIN_EMAIL` / `ADMIN_PASSWORD` →
go to *Admin → Users* and create new accounts, or use *Forgot password?* to email yourself a reset (if you set `RESEND_API_KEY`).

---

## How upgrades work after that

Just `git push origin main` — Render auto-detects, rebuilds, and redeploys both services. Zero clicks, zero downtime on the static site.

---

## Costs at a glance

| Service | Plan | Monthly |
|---|---|---|
| procureflow-api | Starter | $7 |
| procureflow-web (static) | Free | $0 |
| procureflow-redis (Key Value) | Free | $0 |
| MongoDB Atlas M0 | Free | $0 |
| **Total** | | **$7/mo** |

Free Web Service tier ($0) works too, but the backend sleeps after 15 min of inactivity — first request after sleep takes ~30 s. Fine for occasional internal use; not great for daily users.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| First deploy fails on `procureflow-api` | Check *Logs* — usually `MONGO_URL` typo or Atlas IP allowlist blocking. |
| Login works but redirects loop | `CORS_ORIGINS` and `FRONTEND_URL` don't match the actual frontend URL exactly (no trailing slash). |
| "Email not configured" 503 when emailing | Add `RESEND_API_KEY` and a verified `RESEND_FROM_EMAIL`, then *Save Changes*. |
| Bulk uploads stay PROCESSING | Check *Logs* on `procureflow-api` — celery should print "ready". If Redis is unreachable, the API silently falls back to in-process processing (still works, slower). |
| Disk full | Bump `disk.sizeGB` in `render.yaml` and push, or resize from the dashboard. |

---

## Security note

The blueprint sets a fresh `JWT_SECRET` automatically with `generateValue: true`.
Cookies are `Secure; SameSite=None; HttpOnly` — works only over HTTPS, which Render gives you for free.

If you later want a custom domain (e.g. `procureflow.quatriz.com.my`), add it under *Settings → Custom Domains* on the static site, then update `FRONTEND_URL` + `CORS_ORIGINS` on the API to match.
