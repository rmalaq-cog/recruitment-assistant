# Deployment Guide: Recruitment Assistant

## Release Scope / Version Summary

- Release: Tier-0 local MVP delivery candidate, version `0.1.0`.
- Runtime alignment: `AAMAD_TARGET_RUNTIME=crewai`.
- Application scope: FastAPI backend, dependency-free static recruiter workbench, SQLite persistence, deterministic local recruitment analysis path, CrewAI-compatible agent/task configuration, Markdown/JSON export, and local audit-event storage.
- Delivery intent: local demo and Docker-based evaluation only. This is not a shared production deployment.
- Source documents reviewed: PRD at `project-context/1.define/prd.md`, SAD at `project-context/1.define/sad.md`, and QA status at `project-context/2.build/qa.md`.

## QA and Security Status

QA status is documented in `project-context/2.build/qa.md`. The local workbench happy path passed for role intake, criteria editing, pasted candidate analysis, ranked comparison, evidence review, recruiter decision save, and export rendering. The backend smoke path passed health, job creation, criteria update, run creation, decision save, JSON export, and validation handling.

Known QA gaps remain for this delivery candidate:

- `QA-001`: protected-class terms in raw candidate source text are not always blocked by guardrails.
- `QA-002`: backend Markdown export omits generated timestamp, explicit job criteria, and persisted recruiter decisions.
- `QA-003`: PDF/DOCX upload parsing is listed in requirements but not wired into the API/UI.
- `QA-004`: frontend uses synchronous run creation instead of granular polling phases.
- `QA-005`: automated regression tests are not yet present.

No `security.md` artifact is present under `project-context/`. For this Tier-0 mini-project, delivery proceeds with an accepted security documentation gap and the explicit limitation that the app is suitable only for local/demo use with synthetic or approved candidate data. A formal `@security.eng` review is required before any shared pilot, real candidate-data processing, authentication-enabled deployment, or internet-exposed hosting.

## Hosting Approach

### Local Development

Run the backend with Uvicorn and serve the static frontend locally:

```bash
cd recruitment-assistant
cp .env.example .env
../.venv/bin/python -m pip install -r backend/requirements.txt
AAMAD_TARGET_RUNTIME=crewai ../.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
cd recruitment-assistant
../.venv/bin/python -m http.server 4173 --directory frontend
```

Open `http://localhost:4173/`. The backend health endpoint is `http://127.0.0.1:8000/health`.

### Docker Compose

Use Docker Compose for a repeatable local package:

```bash
cd recruitment-assistant
cp .env.example .env
docker compose up --build
```

Services:

- Backend API: `http://localhost:8000`
- Frontend workbench: `http://localhost:4173`
- Persistent local storage: Docker volume `recruitment-assistant_recruitment-storage`

The backend container uses `backend/app/main.py` as the FastAPI entrypoint and installs dependencies from `backend/requirements.txt`.

The default Compose package intentionally does not pass provider credentials into the container. This keeps `docker compose config` diagnostics from rendering secrets and matches the validated deterministic local path. When live CrewAI/provider execution is enabled, pass provider credentials through an untracked local override file or a secret manager approved for the target environment.

## Environment Variable Matrix

Reference `.env.example` for keys only. Do not commit secret values.

| Key | Required | Default / Example | Purpose |
| --- | --- | --- | --- |
| `AAMAD_TARGET_RUNTIME` | Yes | `crewai` | Selects the CrewAI-aligned runtime path. |
| `MODEL` | No for deterministic local path | `gpt-5.5` | Model name for future live CrewAI/provider execution. |
| `OPENAI_API_KEY` | No for deterministic local path | blank | Provider credential when live model execution is enabled. |
| `OPENAI_API_BASE` | No | blank | Optional provider-compatible API base URL. |
| `DATABASE_URL` | Yes | `sqlite:///./storage/recruitment_assistant.db` | SQLite database location for local execution. |
| `STORAGE_DIR` | Yes | `./storage` | Local file and database storage directory. |
| `CREWAI_STORAGE_DIR` | Yes | `./storage/crewai` | CrewAI runtime storage directory. |
| `MAX_CANDIDATES_PER_RUN` | Yes | `10` | MVP batch-size limit. |
| `LOG_LEVEL` | No | `INFO` | Backend logging verbosity. |
| `CREWAI_TRACING` | No | `false` | Enables CrewAI tracing for the Application Crew when supported by the installed CrewAI version. |
| `CREWAI_MAX_ITER` | No | `8` | Agent iteration budget for live CrewAI path. |
| `CREWAI_MAX_RPM` | No | `30` | Provider request-rate budget for live CrewAI path. |
| `CREWAI_MAX_EXECUTION_TIME` | No | `120` | Agent execution-time budget in seconds. |
| `CREWAI_TEMPERATURE` | No | `0.2` | Model temperature for live CrewAI path. |
| `CREWAI_MAX_TOKENS` | No | `4000` | Model output-token budget for live CrewAI path. |

## Install, Start, Stop, and Roll Back

### Install Locally

```bash
cd recruitment-assistant
cp .env.example .env
../.venv/bin/python -m pip install -r backend/requirements.txt
```

### Start Locally

```bash
cd recruitment-assistant
AAMAD_TARGET_RUNTIME=crewai ../.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
cd recruitment-assistant
../.venv/bin/python -m http.server 4173 --directory frontend
```

### Start with Docker

```bash
cd recruitment-assistant
docker compose up --build
```

### Stop

For local Python processes, stop the backend and frontend terminals with `Ctrl+C`.

For Docker Compose:

```bash
cd recruitment-assistant
docker compose down
```

To remove local Docker data after confirming it is no longer needed:

```bash
cd recruitment-assistant
docker compose down --volumes
```

### Roll Back

This Tier-0 package has no migration system. Rollback is source-controlled and data-light:

1. Stop the local or Docker Compose services.
2. Return to the previous known-good Git revision or branch.
3. Restore `storage/recruitment_assistant.db` or the Docker volume from a backup when persisted demo runs are needed.
4. Reinstall dependencies or rebuild containers from the restored revision.
5. Verify `GET /health` returns `status: ok` or the expected `degraded` state if provider configuration is intentionally absent.

## Access Control Notes

- Local demo authentication is disabled by design.
- The app must be run on localhost or an otherwise private developer network for Tier-0 use.
- Recruiter decisions are advisory workflow records, not automated employment decisions.
- Shared or hosted deployment requires authentication, role-scoped access, HTTPS, rate limiting, retention controls, encrypted storage, and a completed security review.
- Do not process real candidate data in the Tier-0 package unless the operator has an approved privacy basis and accepts the documented MVP risks.
- Do not add provider credentials directly to committed Compose files. Use local overrides or a deployment secret manager for live model execution.

## Monitoring & Observability

### What to Monitor

- Service health: `GET /health` reports service status, runtime selection, SQLite availability, and whether model credentials are configured without exposing secret values.
- API traffic: every request and response is logged with method, path, status code, duration in milliseconds, and an `x-correlation-id` response header.
- Application Crew execution: each analysis run logs start, deterministic crew phases (`research_candidates`, `evaluate_candidates`, `recommend_shortlist`), completion, guardrail failure, and unhandled execution errors.
- Errors and exceptions: HTTP exceptions are logged at warning level; unexpected exceptions are logged with stack traces and returned as redacted `500` responses with a correlation ID.
- Persistence/audit health: SQLite stores jobs, analysis runs, review decisions, and audit events such as job creation, criteria update, run completion, decisions, and exports.
- Data-protection signals: monitor logs for unexpected raw candidate text or secrets. Application logs intentionally record IDs, counts, timings, statuses, and configuration booleans rather than API keys or candidate source content.

### Log Levels and Storage

- Configure backend verbosity with `LOG_LEVEL`. Recommended local/demo value is `INFO`; use `DEBUG` only for short troubleshooting windows; use `WARNING` or `ERROR` for quieter demos.
- Local Uvicorn logs are written to the backend process stdout/stderr. If launched from a terminal, they remain in that terminal scrollback or any shell redirection configured by the operator.
- Docker Compose logs are written to container stdout/stderr and are viewable with:

```bash
cd recruitment-assistant
docker compose logs -f backend
```

- Persistent workflow audit events are stored in the SQLite database configured by `DATABASE_URL`, under the storage path configured by `STORAGE_DIR` or the Docker volume `recruitment-assistant_recruitment-storage`.
- This Tier-0 package does not ship log rotation, centralized log aggregation, metrics scraping, alerting, or APM. Add those controls before a shared pilot or production deployment.

### CrewAI Tracing

CrewAI tracing is optional for the local MVP and should be enabled only when live CrewAI/provider execution is intentionally being evaluated.

1. Authenticate with CrewAI from the environment that will run the backend:

```bash
crewai login
```

2. Enable tracing in the backend environment:

```bash
CREWAI_TRACING=true
```

3. Start the backend normally. When the installed CrewAI version supports `Crew(..., tracing=True)`, the Application Crew factory enables tracing and logs `crewai_tracing_enabled`. If the installed version does not expose that constructor option, the app continues without tracing and logs `crewai_tracing_requested_but_unsupported`.

4. View traces in the CrewAI dashboard using the account authenticated by `crewai login`. Filter by recent runs and compare dashboard timestamps with backend log entries for `application_crew_started` and `application_crew_completed`.

Redaction still applies when tracing is enabled: do not send real candidate data to a provider or external dashboard unless the target environment has approved privacy, retention, access-control, and security controls.

## Troubleshooting

| Symptom | Likely Cause | Resolution |
| --- | --- | --- |
| `/health` returns `degraded` | CrewAI YAML configuration validation failed | Check `backend/app/crew/config/agents.yaml` and `backend/app/crew/config/tasks.yaml`; confirm runtime is `crewai`. |
| Frontend cannot connect to backend | Backend not running, wrong URL, or port conflict | Start backend on port `8000`; update the frontend API URL field if using another port. |
| Docker backend cannot write database | Storage path or volume permissions are wrong | Use the provided `docker-compose.yml` volume and container defaults; rebuild with `docker compose up --build`. |
| `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock` | Current user cannot access the Docker daemon socket | Add the user to the Docker-managed group or fix Docker Desktop/snap socket permissions, then open a new shell and rerun `docker compose build`. |
| `Only sqlite:/// DATABASE_URL values are supported` | `DATABASE_URL` is not SQLite | Set `DATABASE_URL` to a `sqlite:///` URL for the MVP. |
| Analysis completes without live model credentials | Expected deterministic local path | Add provider credentials only after live CrewAI execution is intentionally enabled. |
| PDF/DOCX upload is unavailable | File upload API/UI is not wired in the MVP | Use pasted candidate text for this release or defer delivery until ingestion is implemented. |
| Guardrail misses protected terms in raw source text | Known QA gap `QA-001` | Do not use this package for production screening; fix guardrail source-text scanning before pilot. |

## Sources

- PRD: `project-context/1.define/prd.md`
- SAD: `project-context/1.define/sad.md`
- QA notes: `project-context/2.build/qa.md`
- Backend entrypoint: `backend/app/main.py`
- Backend requirements: `backend/requirements.txt`
- Environment template: `.env.example`
- Packaging: `Dockerfile`, `docker-compose.yml`, `.dockerignore`

## Assumptions

- This delivery is for a Tier-0 local mini-project, not a production or shared pilot release.
- The accepted target runtime is CrewAI via `AAMAD_TARGET_RUNTIME=crewai`.
- The deterministic backend path is the validated MVP behavior; live CrewAI/model-provider execution remains scaffolded but not release-gated.
- Synthetic or approved test data is used for demos.

## Open Questions

- Should `QA-001` be fixed before any Deliver sign-off beyond Tier-0 local demo?
- Should PDF/DOCX upload support remain a release gate or be formally moved to post-MVP?
- Should backend export be updated to include saved recruiter decisions and explicit job criteria before stakeholder demos?
- Which formal security-review template should be used for the missing `security.md` artifact?

## Audit

| Timestamp | Persona | Action | Runtime | Notes |
| --- | --- | --- | --- | --- |
| 2026-09-26 | devops-eng | `*prepare-release`, `*define-deploy`, `*document-deploy` | `AAMAD_TARGET_RUNTIME=crewai` | Reviewed PRD, SAD, and QA; confirmed no security.md artifact; added Docker packaging; documented local/Docker operations, env matrix, access-control notes, monitoring, troubleshooting, assumptions, gaps, and open questions. |