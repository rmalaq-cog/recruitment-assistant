# System Architecture Document: Recruitment Assistant Application

## 1. MVP Architecture Philosophy & Principles

### MVP Design Principles

- Customer and operator feedback first: the system optimizes recruiter review speed while preserving human accountability for candidate decisions.
- Minimal viable agent set: the MVP uses three CrewAI application agents, Researcher, Evaluator, and Recommender, with compliance checks implemented as deterministic guardrails and review gates around agent outputs.
- Source-grounded and auditable by default: candidate claims, rankings, and exports must include source references, confidence, missing information, and run metadata.
- Reproducible orchestration: CrewAI runs sequentially with explicit task context chaining, schema validation, bounded retries, and no long-lived agent memory in MVP.
- Deployable local-first architecture: the Build phase should produce a local/demo deployment that can later be hardened for shared pilot use.

### Core vs Future Features

**MVP**:

- Recruiter workbench for job intake, candidate material entry or upload, analysis status, comparison, review decisions, and export.
- FastAPI backend exposing role, candidate, analysis, and export endpoints.
- CrewAI application crew with Researcher, Evaluator, and Recommender agents.
- Manual resume/profile text ingestion and PDF support where parser dependencies are available.
- SQLite-backed storage for job runs, candidate metadata, generated structured outputs, recruiter decisions, and audit events.
- Markdown and JSON export for shortlist handoff.

**Future Work**:

- Native ATS writeback/import, calendar scheduling, outreach automation, enterprise SSO/RBAC, configurable retention UI, adverse-impact dashboards, multi-region hosting, and private model deployment.
- Live web sourcing or public profile enrichment beyond explicitly approved URLs.
- Hierarchical CrewAI manager mode or autonomous delegation.

### Technical Architecture Decisions

- **Runtime**: `crewai`, resolved from the user request and PRD. The generated application must set or run with `AAMAD_TARGET_RUNTIME=crewai`.
- **Backend**: FastAPI is selected because the workflow needs typed request/response schemas, async-friendly long-running analysis endpoints, health checks, and clean OpenAPI contracts for the frontend.
- **Frontend**: a modern web recruiter workbench is selected over CLI because the PRD requires criteria editing, candidate comparison, evidence drilldown, review labels, and export controls.
- **Storage**: SQLite is included for MVP auditability. It is small enough for local/demo use while preserving the data needed to explain recommendation runs.
- **Streaming**: MVP uses non-streaming final analysis responses plus progress polling or server-sent events for long-running jobs. Token-level streaming is not required for the first build.
- **Compliance**: final candidate recommendations are decision-support artifacts only. The backend must label all recommendations as requiring human review and block final export if guardrails detect protected-class inference, discriminatory language, or unsupported rejection rationale.

## 2. Multi-Agent System Specification

### Agent Architecture Requirements

The MVP application crew contains three specialized CrewAI agents:

| Agent | Role | Goal | Tools | Output |
| --- | --- | --- | --- | --- |
| Researcher | Candidate research and extraction specialist | Extract structured candidate facts from supplied resumes, profile text, and approved links while preserving provenance. | Document parser, text extractor, source-reference tracker, optional approved URL fetcher. | `CandidateProfile` JSON with evidence snippets and uncertainty flags. |
| Evaluator | Candidate-job fit evaluator | Apply the same role rubric to every candidate and identify strengths, gaps, risks, follow-up questions, and confidence. | Criteria matcher, scoring rubric, schema validator. | `CandidateEvaluation` JSON per candidate. |
| Recommender | Recruiter shortlist synthesizer | Rank candidates for human review and produce a concise, explainable shortlist package. | Ranking formatter, compliance guardrail result reader, Markdown/JSON export formatter. | `ShortlistRecommendation` JSON and export-ready Markdown. |

Memory is disabled by default (`memory=False`) for reproducibility. Each run receives all required context from the API layer: job criteria, candidate records, prior task outputs, and user-requested options. Any future memory must be scoped to the current job run, stored under a project-controlled path, and redacted.

### Task / Turn Orchestration

1. **Validate Intake**: FastAPI validates job fields, candidate files/text, batch size, and allowed file types before invoking CrewAI.
2. **Research Candidates**: Researcher extracts normalized candidate profiles with source references. Failed or low-confidence extraction returns partial results and actionable errors.
3. **Evaluate Fit**: Evaluator receives the normalized job rubric and Researcher profiles through explicit task context. It applies required and preferred criteria uniformly across all candidates.
4. **Guardrail Review**: backend validators inspect generated profiles/evaluations for protected-class inference, unsupported claims, schema failures, and policy-sensitive wording. High-risk findings block final report generation.
5. **Recommend Shortlist**: Recommender consumes validated evaluations and guardrail results, then generates ranked recommendations, confidence, missing information, interview prompts, and human-review labels.
6. **Persist and Export**: backend stores run metadata, outputs, guardrail results, recruiter decisions, and export artifacts.

Expected data formats are Pydantic-compatible JSON objects for API responses and persisted records. Markdown is generated only for export/handoff views. Downstream tasks must not consume freeform prose when a structured schema is available.

Error handling requirements:

- Parsing, validation, model, guardrail, timeout, and export errors use a shared API error envelope.
- CrewAI task retries are bounded by `max_retry_limit >= 2`.
- Long-running runs support cancellation from the API layer.
- Batch jobs preserve successful candidate outputs when one candidate fails.

Performance budgets:

- P95 single-candidate analysis under 30 seconds after parsing.
- Batch of up to 10 candidates for one job completes within 2 minutes in MVP demo conditions.
- Crew-level `max_rpm` must be configured for provider budget stability.
- MVP agent `max_iter <= 12` unless a later SAD update records justification.

### Runtime-Conditional Configuration

#### crewai

- Crew composition: `RecruitmentCrew` with `researcher`, `evaluator`, and `recommender` agents.
- Process type: `Process.sequential` for deterministic dependency order.
- Required runtime files:
  - `backend/app/crew/config/agents.yaml`
  - `backend/app/crew/config/tasks.yaml`
  - `backend/app/crew/crew.py`
- Agent/task definitions must be externalized to YAML. Python code wires schemas, tools, callbacks, validation, and API invocation.
- `Task.context` must chain Researcher outputs into Evaluator tasks and Evaluator outputs plus guardrail results into Recommender tasks.
- Use `allow_delegation=false` for all MVP agents.
- Use `Task.guardrail` or equivalent post-task validators for schema and compliance checks.
- Use `kickoff_for_each` only if Build implements independent per-candidate analysis; deterministic merge keys must be candidate IDs.
- Prompt Trace and Trace Log should be emitted under `project-context/2.build/logs` with candidate personal data redacted where possible.

## 3. Frontend Architecture Specification

### Technology Stack

- Framework: React with Vite or Next.js App Router; Build may choose the simpler local scaffold, but route/component contracts should remain framework-neutral.
- Language: TypeScript.
- Styling: accessible component-based CSS or a lightweight UI library selected during Build; avoid hard dependency on an enterprise design system for MVP.
- State: local component state plus a small API client layer. Heavy global state is deferred unless the implementation proves it is needed.
- Validation: client-side form validation mirrors backend constraints but backend remains authoritative.

### Application Structure

- `/` Recruiter workbench with sections for role intake, candidate inputs, run status, comparison, shortlist review, and export.
- `/runs/:runId` saved run detail and review state.
- `/api-client` or equivalent module isolates HTTP calls from UI components.
- Components:
  - `RoleIntakeForm`
  - `CandidateInputPanel`
  - `AnalysisStatus`
  - `CandidateComparisonTable`
  - `EvidenceDrawer`
  - `ShortlistReviewPanel`
  - `ExportActions`

Responsive behavior prioritizes desktop/tablet document review. Core controls must remain usable on mobile, but dense comparison is optimized for wider screens. Accessibility target is WCAG 2.1 AA for form labels, keyboard navigation, focus states, table semantics, and error announcements.

### Interface Requirements

- Primary interaction surface is the recruiter workbench, supported by optional follow-up prompts after a run.
- Loading states distinguish queued, parsing, researching, evaluating, guardrail review, recommending, exporting, completed, failed, and canceled.
- Error states distinguish missing criteria, unsupported file type, parser failure, model failure, validation failure, compliance block, and export failure.
- Candidate comparison supports sorting, filtering, criteria-level drilldown, evidence display, confidence, missing information, and recruiter decisions: advance, hold, decline, needs more information.
- Future ATS, outreach, and hiring-manager comment features appear only as disabled placeholders when useful for navigation; they must not imply working integration in MVP.

## 4. Backend Architecture Specification

### API Architecture

FastAPI exposes the primary application boundary:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Health check for local and hosted deployment. |
| `POST` | `/jobs` | Create job intake and normalized criteria draft. |
| `PUT` | `/jobs/{job_id}/criteria` | Save recruiter-edited criteria before analysis. |
| `POST` | `/runs` | Start analysis for one job and candidate batch. |
| `GET` | `/runs/{run_id}` | Return run status, outputs, warnings, and errors. |
| `POST` | `/runs/{run_id}/decisions` | Save recruiter review labels and notes. |
| `GET` | `/runs/{run_id}/export` | Export reviewed shortlist as Markdown or JSON. |

Request schema highlights:

- `JobCreateRequest`: title, description, seniority, location, work model, must-have skills, nice-to-have skills, responsibilities, constraints.
- `CandidateInput`: candidate ID or label, pasted text or uploaded file reference, source type, optional approved URLs.
- `AnalysisRunRequest`: job ID, candidate inputs, analysis options, export preferences.

Response schema highlights:

- `AnalysisRunResponse`: run ID, status, timestamps, candidate count, progress phase, warnings.
- `CandidateProfile`: normalized facts, source references, uncertainty flags.
- `CandidateEvaluation`: criteria matches, strengths, gaps, risks, confidence, follow-up questions.
- `ShortlistRecommendation`: ranked candidates, rationale, missing information, human-review notice, guardrail summary.
- `ApiError`: code, message, detail, correlation ID, retryable flag.

Validation and controls:

- Enforce batch size limit of 10 candidates for MVP.
- Enforce file type and file size allowlists.
- Rate limiting is required for hosted/pilot deployment and may be disabled for local-only demo.
- Long-running analysis can be synchronous for very small local demos, but the preferred contract is job creation plus status polling or server-sent events.

### Data Architecture

SQLite stores MVP audit and workflow state:

- `jobs`: job intake, normalized criteria, edited criteria, timestamps.
- `candidates`: input metadata, source labels, parser status, file references.
- `analysis_runs`: run status, runtime version, model settings, token/cost estimates, timestamps.
- `candidate_profiles`: structured Researcher outputs and source-reference indexes.
- `candidate_evaluations`: Evaluator outputs and validation status.
- `recommendations`: Recommender outputs, ranking rationale, export status.
- `review_decisions`: recruiter decision labels and notes.
- `audit_events`: user/action/runtime events, guardrail results, correlation IDs.

Raw uploaded files should be stored outside the database in a local `storage/` directory for the demo, with metadata in SQLite. Shared/pilot deployments must use encrypted object storage and explicit retention/deletion controls.

### Runtime Integration Layer

- The API layer invokes a `RecruitmentCrewService` that builds CrewAI inputs from validated Pydantic models.
- Agent and task YAML files are loaded once per process and checked at startup for required IDs, tool references, `expected_output`, and task output paths.
- Runtime callbacks record task lifecycle events, retries, guardrail outcomes, model/runtime identifiers, and cost metadata.
- Prompt traces are redacted before persistence and must not include API keys or unnecessary raw candidate personal data.

### Authentication & Secrets

Local demo authentication may be disabled. Any shared/pilot deployment requires authenticated users and role-scoped access to candidate records.

Environment variable names:

- `AAMAD_TARGET_RUNTIME=crewai`
- `MODEL`
- `OPENAI_API_KEY`
- `OPENAI_API_BASE`
- `DATABASE_URL`
- `STORAGE_DIR`
- `CREWAI_STORAGE_DIR`
- `MAX_CANDIDATES_PER_RUN`
- `LOG_LEVEL`

No secret values may appear in repository artifacts, logs, Prompt Trace, or exported reports.

## 5. DevOps & Deployment Architecture

### CI/CD

Minimal MVP pipeline:

- Backend lint/type check where configured.
- Backend unit tests for schemas, parsing, guardrails, and crew service boundaries.
- Frontend lint/type check/build.
- API contract or integration smoke test for role intake through export.
- `aamad validate --phase define` and later phase validations as artifacts are added.

### Hosting

- Local/demo: FastAPI backend and frontend dev server run on localhost with SQLite and local storage.
- Pilot: containerized backend plus static frontend hosting, managed database, encrypted object storage, HTTPS, and authenticated access.
- Health endpoint: `/health` returns service status, runtime selection, database connectivity, and redacted model-provider readiness.

### Future Work

Infrastructure as code, multi-region deployment, advanced autoscaling, enterprise monitoring, and disaster recovery are deferred until pilot requirements justify them.

### Observability

- Structured application logs with correlation IDs and candidate data redaction.
- Audit events for run start/stop, criteria edits, guardrail results, recruiter decisions, and exports.
- Metrics for latency, error rate, validation pass rate, token/cost estimates, and guardrail blocks.
- Advanced APM and distributed tracing are future work for shared production use.

## 6. Data Flow & Integration Architecture

1. Recruiter enters job details and candidate materials in the web workbench.
2. Frontend validates obvious form issues and sends data or file references to FastAPI.
3. FastAPI validates schemas, stores intake metadata, and creates an analysis run.
4. Parser extracts text from accepted candidate files and stores source references.
5. `RecruitmentCrewService` invokes the sequential CrewAI crew.
6. Researcher creates candidate profiles with evidence snippets.
7. Evaluator maps profiles to the edited job criteria rubric.
8. Backend guardrails validate schema, evidence coverage, and compliance-sensitive language.
9. Recommender generates ranked shortlist output with rationale and human-review labels.
10. FastAPI persists outputs and returns status/results to the frontend.
11. Recruiter reviews, edits decision labels, and exports Markdown or JSON.

MVP external integrations are limited to the configured LLM provider and optional approved URL fetching. ATS, HRIS, calendar, email, background check, and assessment integrations are deferred.

Errors propagate through `ApiError` with user-visible messages. The frontend displays partial progress when available and gives rerun controls for corrected criteria, replaced files, or blocked compliance output.

## 7. Performance & Scalability Specifications

- MVP concurrency target: one recruiter running one job at a time with up to 10 candidates.
- P95 single-candidate analysis: under 30 seconds after parsing.
- Batch target: up to 10 candidates within 2 minutes in demo conditions.
- Operations exceeding 10 seconds must expose progress in the UI.
- Token and cost controls live in the runtime layer through max iteration, max execution time, max RPM, model selection, and logging.
- Scaling path: move analysis runs to a background queue, add worker replicas, replace SQLite with Postgres, and move file storage to encrypted object storage when concurrent pilot use is required.

## 8. Security & Compliance Architecture

- Local MVP may run without authentication only when used as a single-user demo. Shared environments require authentication, authorization, HTTPS, and per-user or per-team record scoping.
- Candidate materials and generated summaries are sensitive personal data. Logs must redact candidate personal data by default.
- Uploaded files must pass content type, extension, and size validation before parsing.
- Prompt injection risk is handled by separating candidate-provided text from system/task instructions and by requiring structured output validation.
- The system must not infer, store, rank by, or recommend based on protected-class attributes.
- Exports must include the human-review disclaimer and exclude raw sensitive source content unless explicitly selected by the recruiter.
- Shared/pilot deployments require encryption at rest, retention/deletion workflows, access logs, and legal review for employment, privacy, and AI decisioning laws in the launch region.

## 9. Testing & Quality Assurance Specifications

### MVP Test Expectations

- Unit tests for Pydantic schemas, file validation, parser adapters, guardrail rules, ranking formatter, and export formatter.
- Crew/task tests using synthetic candidate fixtures to verify Researcher, Evaluator, and Recommender output schemas.
- Integration test for role intake, candidate ingestion, analysis run, guardrail pass, review decision, and export.
- Failure-path tests for unsupported files, missing job criteria, malformed agent output, model failure, compliance block, and partial batch failure.
- Frontend smoke tests for role intake, upload/paste, progress display, comparison, decision labels, evidence drilldown, and export action.
- Security assessment before Deliver or any shared deployment.

### Runtime-Specific Checks

- `agents.yaml` and `tasks.yaml` include required agent/task IDs, role/goal/backstory, expected outputs, and task context dependencies.
- CrewAI process is sequential unless a later architecture update justifies a change.
- Agent `allow_delegation=false`, `max_iter <= 12`, bounded retries, and crew-level `max_rpm` are configured.
- Prompt Trace and Trace Log are written with redaction.
- Guardrail results are stored in `audit_events`.

### Evaluation Criteria

| ID | Dimension | Metric | Threshold | Grading Method | Source |
|----|-----------|--------|-----------|-----------------|--------|
| EC-001 | Accuracy | Structured output validation pass rate | >= 95% | Code-based schema validation over synthetic/golden candidate dataset | PRD Technical Metrics |
| EC-002 | Accuracy | Material factual correction rate | < 10% in pilot review | Human review comparing extracted claims to source materials | PRD Goals and Success Metrics |
| EC-003 | Safety | High-severity compliance guardrail false negatives | 0 known misses in curated evaluation set | Human/security review plus rule-based checks | PRD Technical Metrics and P0-F5 |
| EC-004 | Latency | P95 single-candidate analysis after parsing | < 30 seconds | Automated timing in integration/eval run | PRD Performance Requirements |
| EC-005 | Latency | Five-candidate demo time-to-first-shortlist | < 5 minutes median | Timed smoke test | PRD Goals and Success Metrics |
| EC-006 | Reliability | Batch run failure rate on MVP test dataset | < 5% | Automated integration tests with synthetic fixtures | PRD Technical Metrics |
| EC-007 | Cost | Token/cost tracking coverage | 100% of analysis runs record model and cost/token estimate when provider exposes it | Log/audit inspection | PRD Performance Requirements |
| EC-008 | UX | Recruiter task completion from intake to export | > 90% in usability testing | Human usability test | PRD User Experience Metrics |

`@qa.eng` implements this table via `*run-evals`, producing the golden dataset, graders, and `evals.md`.

## 10. MVP Launch & Feedback Strategy

- Launch target: local or course/demo MVP first, then limited pilot only after security and legal review.
- Pilot criteria: permissioned or synthetic candidate data, defined launch region, human reviewer accountable for each recommendation, and retention policy approved.
- Success metrics: time-to-shortlist reduction, summary acceptance rate, factual correction rate, recruiter trust, validation pass rate, latency, failure rate, and guardrail performance.
- Feedback loops: capture recruiter edits, rejected rationales, missing evidence reports, and export usefulness ratings.
- Iteration priorities after first deploy: improve evidence drilldown, reduce parsing failures, tune criteria extraction, expand export formats, and select the first ATS integration candidate.

## Implementation Guidance for AI Development Agents

1. `@project.mgr` scaffolds FastAPI backend, TypeScript frontend, SQLite storage, `.env.example`, and run/test commands according to this SAD.
2. `@backend.eng` implements CrewAI YAML configs, `RecruitmentCrewService`, schemas, parser adapters, guardrails, persistence, API endpoints, and logs.
3. `@frontend.eng` implements the recruiter workbench without embedding backend business logic in UI components.
4. `@integration.eng` wires frontend API client to backend contracts and validates end-to-end run behavior.
5. `@qa.eng` implements unit, integration, smoke, and evaluation checks using synthetic candidate data.
6. `@security.eng` reviews candidate-data handling, prompt injection boundaries, logging redaction, protected-class controls, and export behavior before Deliver.
7. `@devops.eng` packages local run instructions, CI, deployment notes, runbook, and user guide.

## Architecture Validation Checklist

- [x] PRD requirements mapped to architectural components.
- [x] Agents designed for the domain and selected runtime.
- [x] Frontend and backend contracts agree on schemas / streaming.
- [x] Secrets via env vars only.
- [x] MVP vs Future Work boundaries explicit.
- [x] Resolved `AAMAD_TARGET_RUNTIME` recorded in Audit.

## Sources

- PRD: `project-context/1.define/prd.md`, accessed 2026-09-26.
- MRD: `project-context/1.define/mrd.md`, referenced by PRD and available in Define phase.
- SAD template: `.cursor/templates/sad-template.md`, accessed 2026-09-26.
- System architect persona: `.github/agents/system-arch.agent.md`, accessed 2026-09-26.
- AAMAD core rules: `.cursor/rules/aamad-core.mdc`, accessed 2026-09-26.
- CrewAI adapter rules: `.cursor/rules/adapter-crewai.mdc`, accessed 2026-09-26.
- Environment example: `.env.example`, accessed 2026-09-26.
- User request, 2026-09-26: create SAD for recruitment assistant with CrewAI application crew, frontend, backend API, integrations, and `AAMAD_TARGET_RUNTIME=crewai` audit record.

## Assumptions

- `AAMAD_TARGET_RUNTIME` is resolved to `crewai` from the user request and PRD runtime selection; Build and validation commands should run with `AAMAD_TARGET_RUNTIME=crewai` when the shell environment does not already provide it.
- FastAPI is acceptable as the backend API choice because the user allowed FastAPI or Flask and the workflow benefits from typed schemas and OpenAPI.
- A web recruiter workbench is preferred over a CLI because the PRD requires comparison, review, evidence drilldown, and export workflows.
- SQLite is in MVP scope because auditability is a P0 requirement; production-grade persistence and encryption controls are deferred to pilot hardening.
- Public profile fetching is disabled by default and only allowed for explicitly approved URLs.
- Synthetic or permissioned candidate data will be used for automated tests and demos.

## Open Questions

- Which launch region defines the first legal and compliance baseline?
- Which exact LLM provider and model should be used for Build beyond the placeholder `MODEL` variable?
- What maximum upload file size should be enforced for MVP?
- Should DOCX parsing be included in the first Build pass or remain P1?
- What retention period should apply to stored candidate files and generated outputs in a shared pilot?
- Should the frontend use Vite or Next.js App Router for the actual scaffold?

## Audit

| Timestamp | Persona | Action | Runtime | Notes |
| --- | --- | --- | --- | --- |
| 2026-09-26 | system-arch | create-sad --mvp | crewai | Created SAD from PRD and local SAD template. Resolved and recorded `AAMAD_TARGET_RUNTIME=crewai`. Architecture selects FastAPI backend, web recruiter workbench, SQLite MVP audit store, and sequential CrewAI process with Researcher, Evaluator, and Recommender agents. Runtime controls: `memory=False`, `allow_delegation=false`, `max_iter <= 12`, bounded retries, crew-level `max_rpm`, redacted Prompt Trace and Trace Log. LLM configuration is environment-based through `MODEL`, `OPENAI_API_KEY`, and `OPENAI_API_BASE`; temperature and max token values remain Build-time configuration defaults to be recorded when implemented. |