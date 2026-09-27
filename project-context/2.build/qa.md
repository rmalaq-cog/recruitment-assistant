# QA Build Notes: Recruitment Assistant

## Summary

Executed `*qa` and `*verify-flow` smoke/acceptance checks for the Recruitment Assistant MVP using the PRD, SAD, frontend build notes, backend build notes, and integration build notes as source artifacts.

The main recruiter workflow is usable for the implemented MVP slice: job intake, criteria save, pasted candidate analysis, ranked comparison, evidence display, recruiter decision save, and shortlist export all work through the local FastAPI-backed workbench. QA found blocking/partial gaps around compliance guardrail coverage, export completeness, and file ingestion scope.

## Sources

- PRD: `project-context/1.define/prd.md`
- SAD: `project-context/1.define/sad.md`
- Frontend build notes: `project-context/2.build/frontend.md`
- Backend build notes: `project-context/2.build/backend.md`
- Integration build notes: `project-context/2.build/integration.md`
- QA agent instructions: `.github/agents/qa-eng.agent.md`, `.cursor/agents/qa-eng.md`

## Test Environment

- Date: 2026-09-27
- Runtime: `AAMAD_TARGET_RUNTIME=crewai`
- Python environment: repository venv at `/home/renan/projetos/crewai-curso/.venv`, Python 3.13.15
- Backend test surface: FastAPI `TestClient` against `backend.app.main:app`
- Browser test surface: shared workbench at `http://localhost:4173/`, configured for `http://localhost:8000`
- Test data: synthetic job and candidate profiles only

## Unit / Static Checks

| Check | AC Mapping | Result | Notes |
| --- | --- | --- | --- |
| Reviewed backend schemas and validation constraints in `backend/app/models.py` | AC-1.1, AC-2.2, AC-4.2, AC-6.2 | Pass | Pydantic models enforce required job fields, candidate text for text sources, max 10 candidates, decision labels, and export format enum. |
| Reviewed deterministic service flow in `backend/app/services.py` | AC-1.2, AC-3.1, AC-4.1, AC-4.2, AC-4.3 | Pass with limitations | Service creates criteria, extracts simple profile facts, evaluates each candidate with the same rubric, ranks by fit score, and persists runs. Extraction is keyword/simple text based. |
| Reviewed guardrail implementation in `backend/app/guardrails.py` | AC-3.3, AC-5.1, AC-5.3 | Fail | Guardrails scan extracted fields/evaluation outputs, but not source evidence snippets or raw candidate text, so protected-class terms in candidate material can pass. |
| Checked automated test availability | QA process | Gap | No `test*.py` files or configured frontend test runner were found in the MVP tree. |

## Integration / API Checks

Executed a focused FastAPI smoke script covering health, job creation, criteria update, run creation, decision save, Markdown export, JSON export, validation error handling, and protected-class guardrail behavior.

| Check | AC Mapping | Result | Observed Behavior |
| --- | --- | --- | --- |
| `GET /health` | SAD API health | Pass | Returned `200`, status `ok`, runtime `crewai`, database `ok`. |
| `POST /jobs` | AC-1.1, AC-1.2 | Pass | Returned `201` and generated criteria from supplied job fields. |
| `PUT /jobs/{job_id}/criteria` | AC-1.3, AC-1.4 | Pass | Returned `200`; edited required/preferred criteria were persisted for the run. |
| `POST /runs` with 2 pasted candidates | AC-2.1 text input, AC-2.2, AC-3.1, AC-4.1, AC-4.2, AC-4.3, AC-4.4 | Pass | Returned `201`, status `completed`, 2 profiles, 2 evaluations, ranked candidates, evidence snippets, gaps, confidence, interview prompts, and human-review notice. |
| `POST /runs/{run_id}/decisions` | AC-6.2 | Pass | Returned `200`; decision save endpoint accepted an `advance` label with notes. |
| `GET /runs/{run_id}/export?format=markdown` | AC-6.3, AC-6.4 | Partial | Returned `200` and Markdown with ranked recommendations and human-review notice. It did not include generated timestamp, explicit job criteria section, or saved recruiter decisions. |
| `GET /runs/{run_id}/export?format=json` | AC-6.3 | Pass with caveat | Returned `200` JSON export of run payload. Saved decisions are not included in run payload. |
| Invalid job request | Failure path | Pass | Too-short title/description returned FastAPI validation `422`. |
| Candidate text containing protected-class terms | AC-5.1 | Fail | Expected failed/blocked run, but API returned `201` with status `completed` and no guardrail errors. |

## Browser Smoke / Acceptance Checks

Executed the browser workflow in the shared page at `http://localhost:4173/`.

| Check | AC Mapping | Result | Observed Behavior |
| --- | --- | --- | --- |
| Load workbench | UX requirements | Pass | Page loaded as recruiter workbench, not a landing page, with backend URL, role intake, candidate inputs, comparison, evidence, and export areas. |
| Run analysis from default seeded data | AC-1.1, AC-2.1, AC-4.1, AC-4.2, AC-4.3 | Pass | Clicking **Run analysis** progressed through backend calls and completed with 2 analyzed candidates. |
| Ranked comparison render | AC-4.2, AC-4.3, AC-4.4, AC-6.1 | Pass | Alex Example ranked first with score 87 and medium confidence; Jordan Sample ranked second with score 37 and low confidence. Strengths and gaps were visible. |
| Evidence panel | AC-3.4, AC-6.1 | Pass | Selecting/viewing results showed source snippets, missing information, and interview prompts for the selected candidate. |
| Recruiter decision update | AC-6.2 | Pass | Changing Alex Example to `advance` triggered backend save and status changed to `Decision saved`. |
| Export text after decision change | AC-6.2, AC-6.3 | Partial | Frontend regenerated export text including the selected decision. This differs from backend Markdown export, which does not include saved decisions. |

## Acceptance Coverage

| Acceptance Criteria | Status | Evidence |
| --- | --- | --- |
| AC-1.1 Accept job description and optional fields | Pass | Backend `/jobs` and UI role intake accept title, description, required, and preferred criteria. |
| AC-1.2 Generate criteria rubric | Pass | Backend creates required/preferred criteria; UI sends edited criteria before analysis. |
| AC-1.3 User can edit criteria before analysis | Pass | UI criteria fields are editable and sent through `PUT /jobs/{job_id}/criteria`. |
| AC-1.4 Criteria edits stored with timestamp/user when auth exists | Partial | Criteria edits are persisted with timestamps; auth/user identity is deferred. |
| AC-2.1 Accept plain text and PDF inputs | Partial | Plain text paste works. PDF upload/parsing is not implemented in UI/API. |
| AC-2.2 Record source label | Pass | Candidate label/source IDs flow through profiles and evidence. |
| AC-2.3 Reject unsupported file types clearly | Not covered / Gap | No file upload endpoint or UI exists yet. |
| AC-2.4 Flag incomplete or low-confidence extraction | Partial | Short candidate text creates uncertainty flags; UI does not expose all risk flags prominently. |
| AC-3.1 Extract structured profile facts | Pass with limitations | Name, skills, education/projects/employers, links, and evidence are extracted by deterministic text heuristics. |
| AC-3.2 Important claims include source reference or uncertainty | Partial | Evidence snippets exist, but criteria matches use broad evidence references and not exact source spans. |
| AC-3.3 Do not infer protected-class attributes or use them for ranking | Partial | No explicit protected-class inference was observed, but protected-class terms in source evidence are not blocked. |
| AC-3.4 Inspect source snippets behind fit conclusions | Pass | Browser evidence panel displays source snippets. |
| AC-4.1 Evaluate all candidates against same rubric | Pass | Same required/preferred criteria used for both candidates. |
| AC-4.2 Produce strengths, gaps, risks, confidence, follow-up questions | Pass | API and UI display strengths, gaps, confidence, and prompts; risks exist in API output when generated. |
| AC-4.3 Rank with transparent rationale/evidence | Pass | Backend ranks candidates and includes rationale plus evidence snippets. |
| AC-4.4 Label recommendations as requiring human review | Pass | Human-review notice appears in API response and export area. |
| AC-5.1 Block/flag protected-class, unsupported, discriminatory language | Fail | Guardrail smoke with `age` and `religion` returned completed with no errors. |
| AC-5.2 Include compliance warning | Pass | Human-review/decision-support warning is present. |
| AC-5.3 Record guardrail results in audit log | Partial | Run audit payload records `guardrail_passed`; detailed findings are only present when detected. |
| AC-6.1 Review summaries, criteria fit, gaps, prompts | Pass | UI table and evidence panel support review. |
| AC-6.2 Mark candidates advance/hold/decline/needs more information | Pass | Browser decision change saved successfully. |
| AC-6.3 Export includes job criteria, summaries, rationale, timestamp | Partial | Export includes summaries/rationale but omits explicit job criteria, generated timestamp, and backend-saved decisions. |
| AC-6.4 Export excludes raw sensitive source content unless selected | Pass for backend Markdown | Backend Markdown export excludes raw source snippets by default. |

## Defects / Issues

| ID | Severity | Area | Description | Recommendation |
| --- | --- | --- | --- | --- |
| QA-001 | High | Compliance guardrails | Protected-class terms present in candidate source text/evidence are not blocked or flagged. The smoke input containing `age` and `religion` completed successfully. | Include raw candidate text or evidence snippets in guardrail review before final recommendation, and add regression tests for protected-class and automated-decision terms. |
| QA-002 | Medium | Export | Backend Markdown export does not include generated timestamp, explicit job criteria, or saved recruiter decisions, so AC-6.3 is only partially met. | Load job criteria and saved decisions during export generation; include `generated_at` and decision labels/notes in Markdown and JSON export. |
| QA-003 | Medium | Ingestion | PDF upload/parsing and unsupported-file rejection are not implemented in the UI/API despite P0 AC-2.1/AC-2.3. | Add upload endpoint/control or explicitly re-scope PDF support out of the current MVP acceptance gate. |
| QA-004 | Low | Frontend/runtime UX | Frontend uses synchronous `POST /runs` response instead of polling `GET /runs/{run_id}` and does not show granular phases beyond coarse status text. | Add polling/progress phase rendering before long-running or live CrewAI execution is enabled. |
| QA-005 | Low | Test automation | No automated test suite is present for backend services, guardrails, exports, or frontend integration. | Add focused pytest tests for API/service/guardrails and a small browser smoke test for the workbench. |

## Known Gaps

- Live CrewAI kickoff is scaffolded but not enabled; deterministic local analysis is the tested behavior.
- Candidate materials are pasted text only; PDF/DOCX parsing and file-size/type validation remain unwired.
- Authentication, authorization, RBAC, hosted rate limiting, encrypted storage, retention/deletion workflows, and ATS integrations remain deferred per SAD.
- Prompt Trace and Trace Log output under `project-context/2.build/logs` is not populated by deterministic local runs.
- Performance testing was not run; the tested local flow is synchronous and small-batch only.
- `*run-evals` was not executed because this request scoped smoke/acceptance QA and did not provide evaluation thresholds beyond the PRD targets.

## Assumptions

- The current MVP acceptance surface is the implemented local prototype, not deferred hosted, ATS, authentication, file-upload, or live CrewAI execution behavior.
- Synthetic candidate data is sufficient for smoke and acceptance checks at this stage.
- The existing browser page at `http://localhost:4173/` and local FastAPI backend at `http://localhost:8000` represent the current integrated build.

## Open Questions

- Should PDF upload support remain a P0 release gate, or should the MVP acceptance criteria be revised to mark it as deferred?
- Should backend exports be the source of truth for recruiter decisions, or should the frontend-generated export remain acceptable for the local demo?
- What curated compliance/evaluation dataset should be used for the required `*run-evals` pass before Deliver?

## Future Work

- Add automated regression tests for all P0 acceptance criteria, especially guardrail failure paths and export contents.
- Implement a small golden synthetic candidate dataset for ranking quality, evidence coverage, missing-information flags, and compliance false-negative checks.
- Add browser automation for the workbench happy path, missing-role validation, no-candidate validation, decision save, and export content.
- Add API tests for max candidate batch size, unsupported source types/files, nonexistent job/run IDs, JSON export, Markdown export, and audit event creation.
- Run a dedicated `*run-evals` pass before `@security.eng` and Deliver, using PRD metrics for validation pass rate, correction rate, guardrail false negatives, and monitoring recommendations.

## QA Recommendation

Do not move to security/deliver as a fully passing MVP until QA-001 is fixed or explicitly accepted as a known compliance risk. The main demo flow can be shown as a local prototype with the documented limitations.

## Audit

| Timestamp | Persona | Action | Runtime | Notes |
| --- | --- | --- | --- | --- |
| 2026-09-27 | qa-eng | *qa / *verify-flow | AAMAD_TARGET_RUNTIME=crewai | Reviewed PRD/SAD/build artifacts, ran API and browser smoke checks for role intake through export, logged acceptance coverage, defects, known gaps, and future work. |