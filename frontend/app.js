const state = {
  candidates: [],
  selectedCandidateId: null,
  results: []
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

document.querySelector("#addCandidate").addEventListener("click", () => addCandidate());
document.querySelector("#runAnalysis").addEventListener("click", runAnalysis);
document.querySelector("#copyExport").addEventListener("click", copyExport);

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

function runAnalysis() {
  const required = readLines("#requiredCriteria");
  const preferred = readLines("#preferredCriteria");
  const activeCandidates = state.candidates.filter((candidate) => candidate.label.trim() && candidate.text.trim());

  if (!document.querySelector("#roleTitle").value.trim() || !document.querySelector("#jobDescription").value.trim()) {
    setStatus("error", "Missing role details");
    return;
  }

  if (!activeCandidates.length) {
    setStatus("error", "No candidates");
    return;
  }

  setStatus("running", "Analyzing");
  window.setTimeout(() => {
    state.results = activeCandidates
      .map((candidate) => analyzeCandidate(candidate, required, preferred))
      .sort((left, right) => right.fitScore - left.fitScore)
      .map((result, index) => ({ ...result, rank: index + 1 }));
    state.selectedCandidateId = state.results[0]?.id || null;
    renderResults();
    setStatus("complete", "Completed");
  }, 250);
}

function analyzeCandidate(candidate, required, preferred) {
  const searchable = candidate.text.toLowerCase();
  const requiredMatches = required.filter((criterion) => matchesCriterion(searchable, criterion));
  const preferredMatches = preferred.filter((criterion) => matchesCriterion(searchable, criterion));
  const requiredGaps = required.filter((criterion) => !requiredMatches.includes(criterion));
  const preferredGaps = preferred.filter((criterion) => !preferredMatches.includes(criterion));
  const totalWeight = Math.max(required.length * 2 + preferred.length, 1);
  const fitScore = Math.round(((requiredMatches.length * 2 + preferredMatches.length) / totalWeight) * 100);
  const snippets = candidate.text
    .split(/(?<=[.!?])\s+|\n+/)
    .map((part) => part.trim())
    .filter(Boolean)
    .slice(0, 4);

  return {
    id: candidate.id,
    label: candidate.label,
    rank: 0,
    fitScore,
    confidence: fitScore >= 75 ? "high" : fitScore >= 45 ? "medium" : "low",
    strengths: [...requiredMatches, ...preferredMatches],
    gaps: [...requiredGaps, ...preferredGaps],
    evidence: snippets,
    interviewPrompts: [...requiredGaps, ...preferredGaps]
      .slice(0, 3)
      .map((gap) => `Describe recent hands-on experience with ${gap}.`),
    decision: "needs_more_information"
  };
}

function matchesCriterion(searchable, criterion) {
  const terms = criterion.toLowerCase().match(/[a-z0-9+#.]{3,}/g) || [];
  return terms.some((term) => searchable.includes(term));
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

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}