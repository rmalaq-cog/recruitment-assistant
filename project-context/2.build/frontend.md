# Frontend Build Notes: Recruitment Assistant

## Summary

Implemented a simple static web recruiter workbench for the Recruitment Assistant MVP. The interface supports role intake, editable criteria, pasted candidate materials, local candidate comparison, evidence review, decision labels, and Markdown shortlist export.

## Implemented Components

- Static frontend entrypoint: `frontend/index.html`.
- Workbench styling: `frontend/styles.css`.
- Client-side interaction and local analysis flow: `frontend/app.js`.

## UX Coverage

- Role intake fields for title, job description, required criteria, and preferred criteria.
- Candidate input cards with add/remove controls.
- Analysis status indicator.
- Candidate comparison table with rank, fit, confidence, strengths, gaps, and recruiter decision.
- Evidence panel with source snippets, missing information, and interview prompts.
- Markdown export area with copy action.

## Design Decisions

- Chose static HTML/CSS/JS rather than React to keep this frontend slice dependency-free and immediately runnable from a file URL.
- Built the first screen as the actual recruiter workbench, not a landing page.
- Used a restrained operational UI optimized for desktop/tablet comparison workflows.
- Kept all analysis local in the browser for this phase because the frontend persona contract says backend endpoint wiring belongs to integration work.
- Preserved the backend API contract in the UI shape: job criteria, candidate inputs, run status, evaluations, decisions, and export.

## Runtime And Integration Notes

- Resolved `AAMAD_TARGET_RUNTIME=crewai` from the SAD and PRD.
- The UI currently simulates Researcher/Evaluator/Recommender outputs locally with deterministic keyword matching.
- `@integration.eng` should replace local analysis with calls to the FastAPI endpoints implemented by `@backend.eng`:
  - `POST /jobs`
  - `PUT /jobs/{job_id}/criteria`
  - `POST /runs`
  - `GET /runs/{run_id}`
  - `POST /runs/{run_id}/decisions`
  - `GET /runs/{run_id}/export`

## Validation

- The frontend can run directly from `frontend/index.html` without a dev server.
- Manual browser validation should cover adding/removing candidates, running analysis, selecting comparison rows, changing decisions, and copying export content.

## Known Gaps

- No backend API calls are wired in this phase.
- No file upload control is implemented yet; candidate materials are pasted as text.
- No persistence between browser sessions.
- No automated frontend test runner is configured.
- No authentication or role-based access UI is included, consistent with local MVP scope.

## Sources

- PRD: `project-context/1.define/prd.md`.
- SAD: `project-context/1.define/sad.md`.
- Frontend persona instructions: `.github/agents/frontend-eng.agent.md`.
- User request, 2026-09-26: build the frontend and document decisions/status in `project-context/2.build/frontend.md`.

## Assumptions

- Static web UI is acceptable under the requested simple web interface option.
- Candidate paste input is acceptable for the first frontend build slice because file ingestion wiring is not yet integrated.
- Integration work will connect the UI to the FastAPI backend in a later AAMAD step.

## Open Questions

- Should the integrated frontend remain static or move to React/Vite when backend wiring begins?
- Should PDF/DOCX upload controls be added before or during integration?
- What final visual language should be used if the app becomes a hosted pilot?

## Audit

| Timestamp | Persona | Action | Runtime | Notes |
| --- | --- | --- | --- | --- |
| 2026-09-26 | frontend-eng | develop-fe | crewai | Resolved `AAMAD_TARGET_RUNTIME=crewai`. Implemented dependency-free static recruiter workbench with role intake, candidate paste inputs, local comparison, evidence review, decision labels, and Markdown export. Backend endpoint wiring deferred to integration per frontend persona contract. |