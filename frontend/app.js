const state = {
  candidates: [],
  selectedCandidateId: null,
  results: [],
  runId: null,
  apiBaseUrl: localStorage.getItem("recruitmentAssistantApiBaseUrl") || "http://localhost:8000"
};

const candidateList = document.querySelector("#candidateList");
const candidateTemplate = document.querySelector("#candidateTemplate");
const statusDot = document.querySelector("#statusDot");
const statusText = document.querySelector("#statusText");
const comparisonRows = document.querySelector("#comparisonRows");
const comparisonMeta = document.querySelector("#comparisonMeta");
const evidenceMeta = document.querySelector("#evidenceMeta");
const evidenceContent = document.querySelector("#evidenceContent");
const exportOutput = document.querySelector("#exportOutput");
const apiBaseUrlInput = document.querySelector("#apiBaseUrl");

document.querySelector("#addCandidate").addEventListener("click", () => addCandidate());
document.querySelector("#runAnalysis").addEventListener("click", runAnalysis);
document.querySelector("#copyExport").addEventListener("click", copyExport);
apiBaseUrlInput.value = state.apiBaseUrl;
apiBaseUrlInput.addEventListener("change", () => {
  state.apiBaseUrl = apiBaseUrlInput.value.trim().replace(/\/+$/, "") || "http://localhost:8000";
  apiBaseUrlInput.value = state.apiBaseUrl;
  localStorage.setItem("recruitmentAssistantApiBaseUrl", state.apiBaseUrl);
});

addCandidate({
  label: "Alex Example",
  text: "Alex Example\nBackend engineer with Python, FastAPI, SQL, and Docker experience. Built APIs at Example Company. University degree in Computer Science."
});
addCandidate({
  label: "Jordan Sample",
  text: "Jordan Sample\nFull-stack developer with React, TypeScript, data analysis, and SQL experience. Implemented internal recruiting dashboards and collaborated with hiring teams."
});

function addCandidate(seed = {}) {
  const candidate = {
    id: crypto.randomUUID ? crypto.randomUUID() : String(Date.now()),
    label: seed.label || `Candidate ${state.candidates.length + 1}`,
    text: seed.text || ""
  };
  state.candidates.push(candidate);

  const node = candidateTemplate.content.firstElementChild.cloneNode(true);
  node.dataset.candidateId = candidate.id;
  node.querySelector(".candidate-label").value = candidate.label;
  node.querySelector(".candidate-text").value = candidate.text;
  node.querySelector(".candidate-label").addEventListener("input", (event) => {
    candidate.label = event.target.value;
  });
  node.querySelector(".candidate-text").addEventListener("input", (event) => {
    candidate.text = event.target.value;
  });
  node.querySelector(".remove-candidate").addEventListener("click", () => {
    state.candidates = state.candidates.filter((item) => item.id !== candidate.id);
    node.remove();
  });
  candidateList.appendChild(node);
}

async function runAnalysis() {
  const required = readLines("#requiredCriteria");
  const preferred = readLines("#preferredCriteria");
  const activeCandidates = state.candidates.filter((candidate) => candidate.label.trim() && candidate.text.trim());
  const roleTitle = document.querySelector("#roleTitle").value.trim();
  const jobDescription = document.querySelector("#jobDescription").value.trim();

  if (!roleTitle || !jobDescription) {
    setStatus("error", "Missing role details");
    return;
  }

  if (!activeCandidates.length) {
    setStatus("error", "No candidates");
    return;
  }

  setStatus("running", "Creating job");
  document.querySelector("#runAnalysis").disabled = true;
  try {
    const job = await requestJson("/jobs", {
      method: "POST",
      body: {
        title: roleTitle,
        description: jobDescription,
        must_have_skills: required,
        nice_to_have_skills: preferred
      }
    });

    setStatus("running", "Saving criteria");
    const updatedJob = await requestJson(`/jobs/${job.id}/criteria`, {
      method: "PUT",
      body: {
        criteria: {
          required,
          preferred,
          disqualifying: [],
          responsibilities: []
        }
      }
    });

    setStatus("running", "Analyzing");
    const run = await requestJson("/runs", {
      method: "POST",
      body: {
        job_id: updatedJob.id,
        candidates: activeCandidates.map((candidate) => ({
          id: candidate.id,
          label: candidate.label.trim(),
          source_type: "text",
          text: candidate.text.trim()
        })),
        options: {
          include_markdown_export: true,
          allow_public_url_fetch: false
        }
      }
    });

    state.runId = run.run_id;
    state.results = mapRunResults(run);
    state.selectedCandidateId = state.results[0]?.id || null;
    renderResults();
    await renderServerExport();
    setStatus(run.status === "completed" ? "complete" : "error", formatStatus(run.status));
  } catch (error) {
    setStatus("error", error.message || "Analysis failed");
  } finally {
    document.querySelector("#runAnalysis").disabled = false;
  }
}

function renderResults() {
  comparisonRows.innerHTML = "";
  comparisonMeta.textContent = `${state.results.length} candidate${state.results.length === 1 ? "" : "s"} analyzed`;

  state.results.forEach((result) => {
    const row = document.createElement("tr");
    row.className = result.id === state.selectedCandidateId ? "selected" : "";
    row.innerHTML = `
      <td>${result.rank}</td>
      <td><strong>${escapeHtml(result.label)}</strong></td>
      <td>
        <div class="fit-meter">
          <strong>${result.fitScore}</strong>
          <span class="fit-bar"><span style="width:${result.fitScore}%"></span></span>
        </div>
      </td>
      <td>${result.confidence}</td>
      <td>${renderPills(result.strengths, "pill")}</td>
      <td>${renderPills(result.gaps, "pill gap-pill")}</td>
      <td>
        <select aria-label="Decision for ${escapeHtml(result.label)}">
          <option value="advance">Advance</option>
          <option value="hold">Hold</option>
          <option value="decline">Decline</option>
          <option value="needs_more_information">Needs more information</option>
        </select>
      </td>
    `;
    row.querySelector("select").value = result.decision;
    row.querySelector("select").addEventListener("change", (event) => {
      result.decision = event.target.value;
      saveDecision(result).catch((error) => setStatus("error", error.message || "Decision save failed"));
      renderExport();
    });
    row.addEventListener("click", (event) => {
      if (event.target.tagName.toLowerCase() === "select") return;
      state.selectedCandidateId = result.id;
      renderResults();
    });
    comparisonRows.appendChild(row);
  });

  renderEvidence();
  renderExport();
}

function mapRunResults(run) {
  const profilesById = new Map(run.profiles.map((profile) => [profile.candidate_id, profile]));
  const evaluationsById = new Map(run.evaluations.map((evaluation) => [evaluation.candidate_id, evaluation]));
  const ranked = run.recommendation?.ranked_candidates || [];
  const rows = ranked.length
    ? ranked
    : run.evaluations.map((evaluation, index) => ({
        rank: index + 1,
        candidate_id: evaluation.candidate_id,
        label: profilesById.get(evaluation.candidate_id)?.label || evaluation.candidate_id,
        fit_score: evaluation.fit_score,
        confidence: evaluation.confidence,
        missing_information: evaluation.gaps,
        interview_prompts: evaluation.follow_up_questions
      }));

  return rows.map((candidate) => {
    const profile = profilesById.get(candidate.candidate_id);
    const evaluation = evaluationsById.get(candidate.candidate_id);
    return {
      id: candidate.candidate_id,
      label: candidate.label,
      rank: candidate.rank,
      fitScore: candidate.fit_score,
      confidence: candidate.confidence,
      strengths: evaluation?.strengths || [],
      gaps: candidate.missing_information || evaluation?.gaps || [],
      risks: evaluation?.risks || [],
      evidence: (profile?.evidence || []).map((item) => item.snippet),
      interviewPrompts: candidate.interview_prompts || evaluation?.follow_up_questions || [],
      decision: "needs_more_information"
    };
  });
}

async function renderServerExport() {
  if (!state.runId) {
    renderExport();
    return;
  }
  exportOutput.value = await requestText(`/runs/${state.runId}/export?format=markdown`);
}

function renderEvidence() {
  const result = state.results.find((item) => item.id === state.selectedCandidateId);
  if (!result) {
    evidenceMeta.textContent = "Select a row";
    evidenceContent.className = "evidence-content empty-state";
    evidenceContent.textContent = "Run an analysis to inspect source snippets, risks, and interview prompts.";
    return;
  }

  evidenceMeta.textContent = result.label;
  evidenceContent.className = "evidence-content";
  evidenceContent.innerHTML = `
    <section class="evidence-block">
      <h3>Source snippets</h3>
      <ul>${result.evidence.map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>No snippets found.</li>"}</ul>
    </section>
    <section class="evidence-block">
      <h3>Missing information</h3>
      <ul>${result.gaps.map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>None identified.</li>"}</ul>
    </section>
    <section class="evidence-block">
      <h3>Interview prompts</h3>
      <ul>${result.interviewPrompts.map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>None generated.</li>"}</ul>
    </section>
  `;
}

function renderExport() {
  if (!state.results.length) {
    exportOutput.value = "";
    return;
  }

  const roleTitle = document.querySelector("#roleTitle").value.trim();
  const lines = [
    `# Shortlist: ${roleTitle}`,
    "",
    "Recommendations are decision-support outputs and require recruiter review before any candidate disposition.",
    ""
  ];

  state.results.forEach((result) => {
    lines.push(
      `## ${result.rank}. ${result.label}`,
      `Fit: ${result.fitScore}`,
      `Confidence: ${result.confidence}`,
      `Decision: ${result.decision.replaceAll("_", " ")}`,
      `Strengths: ${result.strengths.join(", ") || "None identified"}`,
      `Gaps: ${result.gaps.join(", ") || "None identified"}`,
      `Interview prompts: ${result.interviewPrompts.join("; ") || "None generated"}`,
      ""
    );
  });

  exportOutput.value = lines.join("\n");
}

function renderPills(items, className) {
  if (!items.length) return "<span class=\"pill gap-pill\">None</span>";
  return `<div class="pill-list">${items.map((item) => `<span class="${className}">${escapeHtml(item)}</span>`).join("")}</div>`;
}

function readLines(selector) {
  return document.querySelector(selector).value.split("\n").map((line) => line.trim()).filter(Boolean);
}

function setStatus(kind, text) {
  statusDot.className = `status-dot ${kind}`;
  statusText.textContent = text;
}

async function copyExport() {
  if (!exportOutput.value) return;
  await navigator.clipboard.writeText(exportOutput.value);
  setStatus("complete", "Export copied");
}

async function saveDecision(result) {
  if (!state.runId) return;
  await requestJson(`/runs/${state.runId}/decisions`, {
    method: "POST",
    body: {
      decisions: [{ candidate_id: result.id, label: result.decision }]
    }
  });
  setStatus("complete", "Decision saved");
}

async function requestJson(path, options = {}) {
  const response = await fetch(`${state.apiBaseUrl}${path}`, {
    method: options.method || "GET",
    headers: { "Content-Type": "application/json" },
    body: options.body ? JSON.stringify(options.body) : undefined
  });
  if (!response.ok) {
    throw new Error(await readApiError(response));
  }
  return response.json();
}

async function requestText(path) {
  const response = await fetch(`${state.apiBaseUrl}${path}`);
  if (!response.ok) {
    throw new Error(await readApiError(response));
  }
  return response.text();
}

async function readApiError(response) {
  try {
    const payload = await response.json();
    return payload.message || `API request failed with ${response.status}`;
  } catch {
    return `API request failed with ${response.status}`;
  }
}

function formatStatus(status) {
  const text = status.replaceAll("_", " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}