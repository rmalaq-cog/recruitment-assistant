# Backend Build Notes: Recruitment Assistant

## Summary

Implemented the MVP backend scaffold for the Recruitment Assistant using FastAPI and CrewAI-compatible configuration. The backend exposes the SAD-defined API surface, stores run state and audit events in SQLite, and provides a deterministic local analysis path for development and tests while preserving CrewAI YAML agent/task definitions for runtime integration.

## Implemented Components

- FastAPI application entrypoint: `backend/app/main.py`.
- Pydantic request/response schemas: `backend/app/models.py`.
- SQLite persistence and audit tables: `backend/app/storage.py`.
- Recruitment workflow service: `backend/app/services.py`.
- Compliance-sensitive guardrails and redaction helpers: `backend/app/guardrails.py`.
- CrewAI runtime factory: `backend/app/crew/crew.py`.
- Externalized CrewAI agent and task definitions:
  - `backend/app/crew/config/agents.yaml`
  - `backend/app/crew/config/tasks.yaml`
- Backend dependency manifest: `backend/requirements.txt`.

## API Endpoints

| Method | Path | Status |
| --- | --- | --- |
| `GET` | `/health` | Implemented |
| `POST` | `/jobs` | Implemented |
| `PUT` | `/jobs/{job_id}/criteria` | Implemented |
| `POST` | `/runs` | Implemented |
| `GET` | `/runs/{run_id}` | Implemented |
| `POST` | `/runs/{run_id}/decisions` | Implemented |
| `GET` | `/runs/{run_id}/export` | Implemented for Markdown and JSON |

## CrewAI Adapter Compliance

- Resolved runtime: `AAMAD_TARGET_RUNTIME=crewai`.
- Agent/task definitions are externalized to YAML under `backend/app/crew/config/`.
- Crew composition includes Researcher, Evaluator, and Recommender agents.
- Process mode is `Process.sequential` in `RecruitmentCrewFactory.build()`.
- Agent config sets `allow_delegation=false`, `max_iter=8`, `max_execution_time=120`, and `max_retry_limit=2`.
- Crew config sets `memory=False` and `max_rpm` from environment settings.
- Task config includes explicit output files and context chaining.
- Runtime controls recorded for implementation: model from `MODEL`, temperature from `CREWAI_TEMPERATURE`, max tokens from `CREWAI_MAX_TOKENS`, max RPM from `CREWAI_MAX_RPM`.

## Runtime Behavior

The current API uses a deterministic local analysis service so the MVP can run without live LLM credentials. This service extracts candidate facts from provided text, maps candidates against job criteria, applies compliance-sensitive guardrails, creates ranked recommendations, persists audit metadata, and exports recruiter-facing Markdown or JSON.

The CrewAI factory and YAML configuration are present for the Build phase to switch endpoint execution from deterministic service logic to live CrewAI kickoff once model provider settings and prompt-trace storage are finalized.

## Validation

- FastAPI was installed into the configured Python 3.13 venv.
- Pending command validation after implementation:
  - `python -m compileall backend`
  - FastAPI smoke test with `TestClient`
  - `aamad validate --phase build` when applicable

## Known Gaps

- File upload parsing endpoints are not implemented yet; current MVP backend accepts pasted text candidate materials through JSON.
- PDF/DOCX parser dependencies are declared but not wired into upload endpoints.
- Real CrewAI kickoff is scaffolded but not used by default because live LLM credentials and prompt-trace persistence policy are not finalized.
- Authentication, authorization, queue-backed background jobs, encrypted storage, and hosted rate limiting remain deferred per SAD.
- Prompt Trace and Trace Log directories are not populated by the deterministic local workflow yet.

## Sources

- PRD: `project-context/1.define/prd.md`.
- SAD: `project-context/1.define/sad.md`.
- CrewAI adapter rule: `.cursor/rules/adapter-crewai.mdc`.
- Backend persona instructions: `.github/agents/backend-eng.agent.md`.
- User request, 2026-09-26: implement backend with CrewAI application crew and FastAPI/Flask endpoints.

## Assumptions

- FastAPI is the selected backend framework from the SAD-approved FastAPI/Flask option.
- Local deterministic execution is acceptable for initial backend validation, with CrewAI configuration implemented for runtime handoff.
- Pasted candidate text is sufficient for this backend slice; file upload parsing is an adjacent integration task.
- SQLite storage is acceptable for local MVP auditability.

## Open Questions

- Which provider/model should be used for live CrewAI kickoff beyond the placeholder `MODEL=gpt-5.5`?
- Should uploaded PDF/DOCX parsing be implemented in backend build or assigned to integration work?
- What maximum upload file size should be enforced?
- What prompt-trace redaction policy should be applied before storing traces under `project-context/2.build/logs`?

## Audit

| Timestamp | Persona | Action | Runtime | Notes |
| --- | --- | --- | --- | --- |
| 2026-09-26 | backend-eng | develop-be | crewai | Resolved `AAMAD_TARGET_RUNTIME=crewai`. Implemented FastAPI backend scaffold, SQLite audit storage, deterministic local analysis flow, guardrails, CrewAI factory, and YAML config for Researcher, Evaluator, and Recommender agents. Runtime controls: `memory=False`, sequential process, `allow_delegation=false`, `max_iter=8`, `max_execution_time=120`, `max_retry_limit=2`, `CREWAI_MAX_RPM=30`, `CREWAI_TEMPERATURE=0.2`, `CREWAI_MAX_TOKENS=4000`. |