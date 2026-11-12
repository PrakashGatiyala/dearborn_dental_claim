# Deployment — Render (backends) · Netlify (frontends) · Supabase (Postgres)

Three backends, three frontends, one Postgres database.

| Part | Where | Folder |
|---|---|---|
| Vyne gateway API | Render (Docker) | `vyne_mock/backend` |
| HCSC AS/400 API | Render (Docker) | `as400/backend` |
| Dearborn agent API | Render (Docker) | `backend` |
| Vyne portal | Netlify | `vyne_mock/frontend` |
| AS/400 portal | Netlify | `as400/frontend` |
| Dearborn workbench | Netlify | `frontend` |
| Database | Supabase | one project, all three APIs |

Deploy in this order: **Supabase → Render → Netlify → back to Render** (the
last step is adding the Netlify URLs to the backends).

## How the three systems connect

```
 vyne_sender.py ──▶ VYNE API ──▶ AS/400 API ──▶ DEARBORN API
                    (forwards)   (suspends,     (agents + technician)
                                  then refers)        │
                                      ◀───────────────┘  approve → pay write-back
```

Only these calls exist between services, so only these URLs are needed:

| Call | Made by | Needs the env var |
|---|---|---|
| Vyne → AS/400 (forward a claim) | Vyne API | `AS400_API_URL` on **Vyne** |
| AS/400 → Dearborn (refer a suspended claim) | AS/400 API | `DEARBORN_API_URL` on **AS/400** |
| Dearborn → AS/400 (write back an approval) | Dearborn API | `AS400_API_URL` on **Dearborn** |

Vyne never calls Dearborn directly; a claim reaches Dearborn only after the
AS/400 suspends it.

---

## 1. Supabase

1. Create a project. Copy **Connection string → Transaction pooler** (port 6543):
   `postgresql://postgres.<ref>:<PASSWORD>@aws-0-<region>.pooler.supabase.com:6543/postgres`
2. Use the same string for all three APIs. They keep apart by schema: Vyne uses
   schema `vyne`, the AS/400 uses `as400`, Dearborn uses `public`.
3. Everything is created on startup (schemas, tables, the `claim_files` table).
   Postgres is required — there is no SQLite fallback. To load the agent's
   reference data, run once locally with `DATABASE_URL` set:
   `cd backend && python seed_data.py`, then from the repo root
   `python cob_edi_generator.py --count 22` and `python seed_cob_claims.py`.

## 2. Render — three Web Services (Runtime: Docker)

New → Web Service → connect the repo → **Docker**. Render sets `PORT`; the
Dockerfiles already honour it.

| | Vyne | AS/400 | Dearborn |
|---|---|---|---|
| Root Directory | `vyne_mock/backend` | `as400/backend` | `backend` |
| Dockerfile path | `./Dockerfile` | `./Dockerfile` | `./Dockerfile` |
| Health check path | `/v1/health` | `/as400/health` | `/health` |

### Environment variables (Render → service → Environment)

| Variable | Vyne | AS/400 | Dearborn |
|---|---|---|---|
| `DATABASE_URL` | Supabase string | Supabase string | Supabase string |
| `ALLOWED_ORIGINS` | Vyne Netlify URL | AS/400 Netlify URL | Dearborn Netlify URL |
| `AS400_API_URL` | **AS/400 Render URL** | — | **AS/400 Render URL** |
| `DEARBORN_API_URL` | — | **Dearborn Render URL** | — |
| `AS400_PORTAL_URL` | AS/400 Netlify URL | AS/400 Netlify URL | — |
| `VYNE_PORTAL_URL` | Vyne Netlify URL | Vyne Netlify URL | — |
| `DEARBORN_PORTAL_URL` | — | Dearborn Netlify URL | — |
| `AZURE_OPENAI_API_KEY` | — | — | your key |
| `AZURE_OPENAI_ENDPOINT` | — | — | your endpoint |
| `AZURE_OPENAI_DEPLOYMENT` | — | — | e.g. `gpt-4o` |
| `AZURE_OPENAI_API_VERSION` | — | — | e.g. `2024-12-01-preview` |

URLs have no trailing slash. `ALLOWED_ORIGINS` takes a comma-separated list.
The `*_PORTAL_URL` values are only used to build the "Open in Vyne / AS/400 /
workbench" links shown in the UIs.

Optional: `AS400_ADJUDICATION_DELAY` (AS/400, seconds before the batch run picks a
claim up).

## 3. Netlify — three sites

New site from Git for each. `netlify.toml` (already in each folder) sets the
build command, publish directory and the single-page-app redirect.

| Environment variable | Vyne site | AS/400 site | Dearborn site |
|---|---|---|---|
| Base directory | `vyne_mock/frontend` | `as400/frontend` | `frontend` |
| `VITE_API_URL` | Vyne Render URL | AS/400 Render URL | Dearborn Render URL |
| `VITE_AS400_PORTAL_URL` | AS/400 Netlify URL | — | — |
| `VITE_LOGIN_USER` (optional) | login name | operator ID | login name |
| `VITE_LOGIN_PASSWORD` (optional) | password | password | password |

`VITE_*` values are baked in at build time — change one, then **Trigger deploy**.
Leave `VITE_LOGIN_*` unset to keep the defaults.

## 4. Finish the loop

Put the three Netlify URLs into the Render variables above (`ALLOWED_ORIGINS`,
`*_PORTAL_URL`) and redeploy the APIs. Without this the browser blocks the calls
(CORS) and the portal links point at localhost.

## 5. Run the demo against the cloud

```
set VYNE_API_URL=https://<vyne>.onrender.com
set AS400_API_URL=https://<as400>.onrender.com
set DEARBORN_API_URL=https://<dearborn>.onrender.com
set DATABASE_URL=<supabase string>
python reset_demo.py
python vyne_sender.py --all
```

---

## Where to change each password

| What | Where | Then |
|---|---|---|
| **Supabase database password** | Supabase → Project Settings → Database → *Reset database password* | Put the new string in `DATABASE_URL` on **all three** Render services (and your local `.env`), then redeploy them |
| **Render / Netlify / Supabase account logins** | each dashboard's own account settings | — |
| **Azure OpenAI key** | Azure portal → your OpenAI resource → Keys and Endpoint → regenerate | Update `AZURE_OPENAI_API_KEY` on the Dearborn Render service |
| **Dearborn workbench login** (default `admin` / `demo123`) | Netlify → Dearborn site → Environment variables → `VITE_LOGIN_USER`, `VITE_LOGIN_PASSWORD` | Trigger deploy |
| **Vyne portal login** (default `admin` / `demo123`) | Netlify → Vyne site → same two variables | Trigger deploy |
| **AS/400 sign-on** (default `OPER01` / `DEMO123`) | Netlify → AS/400 site → same two variables | Trigger deploy |

The three portal logins are a demo gate that runs in the browser, so the values
are visible to anyone who inspects the page. They keep casual visitors out; they
are not real security. The APIs themselves have no authentication.

---

## Things to know before a client demo

- **Free Render services sleep after ~15 minutes idle.** Vyne and the AS/400 move
  claims along with background timers, so a sleeping service stalls the chain and
  the first request takes about a minute to wake. Use the paid Starter plan, or
  open all three health URLs a few minutes before presenting.
- **Dearborn keeps everything in Postgres.** The bronze/silver/gold claim files,
  uploaded documents and technician edits are rows in `claim_files`, so redeploys
  lose nothing and no persistent disk is needed.
- **Secrets:** keep the Azure key and database password only in Render's
  environment settings and your local `.env`. Never commit them.
