# Integration Build Notes: Recruitment Assistant

## Summary

Executed `*integrate-api` for the Recruitment Assistant MVP by connecting the static recruiter workbench to the FastAPI backend contract defined in the SAD. The integrated flow now creates a job intake, saves edited criteria, starts a candidate analysis run, renders ranked results, saves recruiter decisions, and loads Markdown export content from the backend.

## Integrated Components

- Frontend workbench: `frontend/index.html`, `frontend/app.js`, `frontend/styles.css`.
- Backend API: `backend/app/main.py`.
- Runtime: `AAMAD_TARGET_RUNTIME=crewai`.
- Backend API base URL: configurable in the workbench, defaulting to `http://localhost:8000` and persisted in `localStorage`.

## API Wiring

| Frontend action | Backend endpoint | Status |
| --- | --- | --- |
| Create job intake | `POST /jobs` | Wired |
| Save edited criteria | `PUT /jobs/{job_id}/criteria` | Wired |
| Start analysis | `POST /runs` | Wired |
| Render completed output | `POST /runs` response | Wired |
| Save recruiter decision | `POST /runs/{run_id}/decisions` | Wired |
| Load Markdown export | `GET /runs/{run_id}/export?format=markdown` | Wired |

The frontend maps `profiles`, `evaluations`, and `recommendation.ranked_candidates` into the existing comparison table model. Evidence snippets come from `CandidateProfile.evidence`; strengths, gaps, risks, confidence, and follow-up prompts come from the backend evaluation and recommendation payloads.

## Backend Compatibility Changes

- Added local CORS middleware in `backend/app/main.py` for `http://localhost:4173`, `http://127.0.0.1:4173`, and `null` origins so the static/Vite frontend can call the local FastAPI API during MVP development.

## Verification

### API Smoke Test

Ran a focused FastAPI `TestClient` round-trip:

- `GET /health` returned `200` and status `ok`.
- `POST /jobs` returned `201`.
- `PUT /jobs/{job_id}/criteria` returned `200`.
- `POST /runs` returned `201`, status `completed`, and 2 ranked candidates.
- `POST /runs/{run_id}/decisions` returned `200`.
- `GET /runs/{run_id}/export?format=markdown` returned `200` and `# Recruitment Shortlist Export`.

### Browser Round-Trip

Started the backend with:

```bash
/home/renan/projetos/crewai-curso/.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Reloaded the shared workbench at `http://localhost:4173/` and clicked **Run analysis**. The browser completed the backend-backed flow, rendered 2 analyzed candidates, displayed source evidence for Alex Example, and populated the Markdown export from the backend.

### Diagnostics

VS Code diagnostics reported no errors for the touched backend and frontend files.

## Known Issues and Gaps

- The backend still uses deterministic local analysis by default; live CrewAI kickoff remains scaffolded but not enabled until provider credentials and prompt-trace policy are finalized.
- Candidate inputs are still pasted text only. PDF/DOCX upload parsing remains unwired.
- The API contract is synchronous for the local MVP run path. Polling `GET /runs/{run_id}` is available, but the frontend currently renders from the completed `POST /runs` response.
- Recruiter decisions are saved through the backend, but Markdown export does not yet include saved decision labels because backend export generation does not read the decision store.
- Authentication, authorization, queue-backed background work, hosted rate limiting, and encrypted shared storage remain deferred per SAD.

## Sources

- PRD: `project-context/1.define/prd.md`.
- SAD: `project-context/1.define/sad.md`.
- Frontend build notes: `project-context/2.build/frontend.md`.
- Backend build notes: `project-context/2.build/backend.md`.
- Integration persona instructions: `.github/agents/integration-eng.agent.md`.
- User request, 2026-09-26: run `@integration.eng` and document integration in `project-context/2.build/integration.md`.

## Assumptions

- `AAMAD_TARGET_RUNTIME=crewai` is the resolved runtime for this integration slice.
- The MVP can use the backend's deterministic local analysis service while CrewAI live execution remains scaffolded for a later runtime handoff.
- The current static frontend can remain dependency-free for integration as long as the API contract is isolated in `frontend/app.js`.
- Pasted candidate text is sufficient for the basic round-trip requested in this step.

## Open Questions

- Should Markdown export include saved recruiter decision labels in the backend response?
- Should the frontend move to polling `GET /runs/{run_id}` before QA, or is synchronous local analysis acceptable for the MVP demo?
- Should upload parsing be integrated before QA or kept as a known post-MVP gap?

## Audit

| Timestamp | Persona | Action | Runtime | Notes |
| --- | --- | --- | --- | --- |
| 2026-09-26 | integration-eng | integrate-api | AAMAD_TARGET_RUNTIME=crewai | Connected static frontend to FastAPI endpoints for job intake, criteria update, analysis run, decision save, and Markdown export. Added local CORS support and verified API plus browser round-trip. |