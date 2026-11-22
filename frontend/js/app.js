/**
 * EHR Media Intelligence Platform - Comprehensive Frontend Client
 * Connects directly to backend API endpoints (Milestones 1-4).
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements - Navigation & Shell
  const statusIndicator = document.getElementById("status-indicator");
  const statusText = document.getElementById("status-text");
  const liveRegion = document.getElementById("live-region");

  const metricPatients = document.getElementById("metric-patients");
  const metricRecords = document.getElementById("metric-records");
  const metricVectors = document.getElementById("metric-vectors");
  const metricEmbedding = document.getElementById("metric-embedding");

  // Navigation Tabs
  const navTabs = {
    search: { btn: document.getElementById("nav-search-btn"), view: document.getElementById("view-search") },
    patients: { btn: document.getElementById("nav-patients-btn"), view: document.getElementById("view-patients") },
    ingest: { btn: document.getElementById("nav-ingest-btn"), view: document.getElementById("view-ingest") },
    fhir: { btn: document.getElementById("nav-fhir-btn"), view: document.getElementById("view-fhir") },
  };

  // Search Elements
  const searchForm = document.getElementById("search-form");
  const searchInput = document.getElementById("search-input");
  const searchSubmitBtn = document.getElementById("search-submit-btn");
  const clearFiltersBtn = document.getElementById("clear-filters-btn");
  const filterResourceType = document.getElementById("filter-resource-type");
  const filterDateFrom = document.getElementById("filter-date-from");
  const filterDateTo = document.getElementById("filter-date-to");
  const filterPatientId = document.getElementById("filter-patient-id");
  const resultsContainer = document.getElementById("results-container");
  const resultsCountBadge = document.getElementById("results-count-badge");
  const resultsMetadata = document.getElementById("results-metadata");
  const suggestionChips = document.querySelectorAll(".suggestion-chip");

  // Patient Directory Elements
  const patientsTableContainer = document.getElementById("patients-table-container");
  const refreshPatientsBtn = document.getElementById("refresh-patients-btn");

  // Ingest Elements
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");
  const ingestResultsContainer = document.getElementById("ingest-results-container");

  // FHIR Explorer Elements
  const fhirResourceSelect = document.getElementById("fhir-resource-select");
  const fhirIdInput = document.getElementById("fhir-id-input");
  const fhirFetchBtn = document.getElementById("fhir-fetch-btn");
  const fhirOutputContainer = document.getElementById("fhir-output-container");
  const fhirOutputTitle = document.getElementById("fhir-output-title");
  const fhirJsonCode = document.getElementById("fhir-json-code");
  const fhirCopyBtn = document.getElementById("fhir-copy-btn");

  // Modal Elements
  const detailModal = document.getElementById("detail-modal");
  const modalCloseBtn = document.getElementById("modal-close-btn");
  const modalTitle = document.getElementById("modal-title");
  const modalSubtitle = document.getElementById("modal-subtitle");
  const modalIdBadge = document.getElementById("modal-id-badge");
  const modalContent = document.getElementById("modal-content");
  const modalTabSummary = document.getElementById("modal-tab-summary");
  const modalTabRecords = document.getElementById("modal-tab-records");
  const modalTabBundle = document.getElementById("modal-tab-bundle");

  let activePatient = null;
  let activeModalTab = "summary";
  let lastActiveElement = null;

  // -------------------------------------------------------------------------
  // Screen Reader Announcer
  // -------------------------------------------------------------------------
  function announce(message) {
    if (liveRegion) {
      liveRegion.textContent = "";
      setTimeout(() => {
        liveRegion.textContent = message;
      }, 50);
    }
  }

  // -------------------------------------------------------------------------
  // Navigation Routing
  // -------------------------------------------------------------------------
  function switchTab(targetKey) {
    Object.keys(navTabs).forEach((key) => {
      const tab = navTabs[key];
      if (key === targetKey) {
        tab.btn.className = "nav-tab px-3 py-1.5 text-xs font-semibold rounded-md transition-colors bg-teal-50 text-teal-800 border border-teal-200";
        tab.btn.setAttribute("aria-current", "page");
        tab.view.classList.remove("hidden");
      } else {
        tab.btn.className = "nav-tab px-3 py-1.5 text-xs font-medium rounded-md transition-colors text-slate-600 hover:text-slate-900 hover:bg-slate-100";
        tab.btn.removeAttribute("aria-current");
        tab.view.classList.add("hidden");
      }
    });

    if (targetKey === "patients") {
      loadPatients();
    }
    announce(`Switched to ${targetKey} section.`);
  }

  Object.keys(navTabs).forEach((key) => {
    navTabs[key].btn.addEventListener("click", () => switchTab(key));
  });

  // -------------------------------------------------------------------------
  // Live System Health & Metrics
  // -------------------------------------------------------------------------
  async function loadSystemStats() {
    try {
      const resp = await fetch("/api/v1/stats");
      if (resp.ok) {
        const stats = await resp.json();
        if (metricPatients) metricPatients.textContent = stats.total_patients;
        if (metricRecords) metricRecords.textContent = stats.total_records;
        if (metricVectors) metricVectors.textContent = stats.total_vectors;
        if (metricEmbedding) metricEmbedding.textContent = stats.embedding_model;
        if (statusIndicator && statusText) {
          statusIndicator.className = "w-2 h-2 rounded-full bg-emerald-500 animate-pulse";
          statusText.textContent = `API Ready (${stats.vector_store_type})`;
        }
      } else {
        throw new Error(`HTTP ${resp.status}`);
      }
    } catch (err) {
      if (statusIndicator && statusText) {
        statusIndicator.className = "w-2 h-2 rounded-full bg-amber-500";
        statusText.textContent = "API Offline";
      }
    }
  }

  // -------------------------------------------------------------------------
  // Semantic Search Implementation
  // -------------------------------------------------------------------------
  suggestionChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const query = chip.getAttribute("data-query");
      if (searchInput && query) {
        searchInput.value = query;
        searchForm.dispatchEvent(new Event("submit"));
      }
    });
  });

  if (clearFiltersBtn) {
    clearFiltersBtn.addEventListener("click", () => {
      if (filterResourceType) filterResourceType.value = "";
      if (filterDateFrom) filterDateFrom.value = "";
      if (filterDateTo) filterDateTo.value = "";
      if (filterPatientId) filterPatientId.value = "";
      announce("Search filters reset.");
    });
  }

  if (searchForm) {
    searchForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const query = searchInput.value.trim();
      if (!query) {
        announce("Please enter a valid search query.");
        return;
      }

      // Validate date ranges
      const dateFrom = filterDateFrom.value || null;
      const dateTo = filterDateTo.value || null;
      if (dateFrom && dateTo && dateFrom > dateTo) {
        alert("Validation error: Start date cannot occur after end date.");
        return;
      }

      const filters = {};
      if (filterResourceType.value) filters.resource_type = filterResourceType.value;
      if (dateFrom) filters.date_from = dateFrom;
      if (dateTo) filters.date_to = dateTo;
      if (filterPatientId.value.trim()) filters.patient_id = filterPatientId.value.trim();

      const payload = {
        query: query,
        top_k: 5,
        filters: Object.keys(filters).length > 0 ? filters : null,
      };

      // Loading state
      searchSubmitBtn.disabled = true;
      searchSubmitBtn.textContent = "Searching...";
      resultsContainer.innerHTML = `
        <div class="bg-white rounded-xl border border-slate-200 p-8 text-center space-y-3">
          <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-teal-700"></div>
          <p class="text-xs text-slate-500">Vectorizing query and executing semantic nearest-neighbor search...</p>
        </div>
      `;
      announce("Searching records...");

      try {
        const resp = await fetch("/api/v1/search", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!resp.ok) {
          const errData = await resp.json().catch(() => ({}));
          throw new Error(errData.detail || `Server returned error ${resp.status}`);
        }

        const data = await resp.json();
        renderSearchResults(data);
      } catch (err) {
        resultsContainer.innerHTML = `
          <div class="bg-red-50 border border-red-200 rounded-xl p-5 text-red-800 text-xs">
            <h4 class="font-semibold text-sm mb-1">Search Error</h4>
            <p>${escapeHtml(err.message)}</p>
            <button type="button" onclick="document.getElementById('search-form').dispatchEvent(new Event('submit'))" class="mt-3 px-3 py-1 bg-red-100 hover:bg-red-200 text-red-900 rounded font-medium">
              Retry Query
            </button>
          </div>
        `;
        announce(`Search failed: ${err.message}`);
      } finally {
        searchSubmitBtn.disabled = false;
        searchSubmitBtn.textContent = "Search";
      }
    });
  }

  function renderSearchResults(data) {
    resultsCountBadge.textContent = `${data.total_results} record${data.total_results === 1 ? "" : "s"}`;
    resultsMetadata.textContent = `Latency: ${data.search_latency_ms} ms`;

    if (data.results.length === 0) {
      resultsContainer.innerHTML = `
        <div class="bg-white rounded-xl border border-slate-200 p-8 text-center">
          <div class="w-10 h-10 rounded-full bg-slate-100 text-slate-400 mx-auto flex items-center justify-center mb-2">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
          </div>
          <h4 class="text-xs font-semibold text-slate-800">No matching clinical records found</h4>
          <p class="text-xs text-slate-500 max-w-sm mx-auto mt-1">
            Try adjusting your query or resetting resource/date filters to broaden the semantic search window.
          </p>
        </div>
      `;
      announce("No matching records found.");
      return;
    }

    let cardsHtml = "";
    data.results.forEach((item) => {
      const typeBadgeColor = item.resource_type === "DiagnosticReport"
        ? "bg-purple-50 text-purple-700 border-purple-200"
        : "bg-blue-50 text-blue-700 border-blue-200";

      const simPct = Math.round(item.similarity_score * 100);

      cardsHtml += `
        <article class="bg-white rounded-xl border border-slate-200 p-4 sm:p-5 shadow-sm hover:border-slate-300 transition-all flex flex-col justify-between">
          <div>
            <div class="flex flex-wrap items-start justify-between gap-2 mb-2">
              <div class="flex items-center gap-2">
                <span class="px-2 py-0.5 rounded text-xs font-bold bg-slate-100 text-slate-700 border border-slate-200">#${item.rank}</span>
                <h4 class="text-sm font-semibold text-slate-900 leading-snug">${escapeHtml(item.title)}</h4>
              </div>
              <div class="flex items-center gap-2">
                <span class="px-2 py-0.5 rounded text-[11px] font-medium border ${typeBadgeColor}">
                  ${escapeHtml(item.resource_type)}
                </span>
                <span class="badge-similarity px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200" title="Cosine similarity: ${item.similarity_score}">
                  Sim: ${item.similarity_score}
                </span>
              </div>
            </div>

            <!-- Metadata info -->
            <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500 mb-3">
              <span><strong>Patient:</strong> <span class="font-mono text-slate-700">${escapeHtml(item.patient_id)}</span></span>
              <span><strong>Date:</strong> ${item.record_date ? escapeHtml(item.record_date) : "Undated"}</span>
              <span><strong>Type:</strong> ${escapeHtml(item.record_type)}</span>
              ${item.fhir_resource_id ? `<span class="hidden sm:inline"><strong>FHIR:</strong> <span class="font-mono">${escapeHtml(item.fhir_resource_id)}</span></span>` : ""}
            </div>

            <!-- Grounded Excerpt -->
            <div class="bg-slate-50 rounded-lg p-3 text-xs text-slate-700 border border-slate-100 leading-relaxed font-mono">
              "${escapeHtml(item.excerpt)}"
            </div>
          </div>

          <!-- Card Actions -->
          <div class="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
            <span class="text-[11px] text-slate-400">Source: ${escapeHtml(item.source_reference || "Ingested Record")}</span>
            <div class="flex items-center gap-2">
              <button
                type="button"
                onclick="window.viewPatientDetails('${escapeJs(item.patient_id)}')"
                class="px-3 py-1 bg-teal-50 hover:bg-teal-100 text-teal-800 font-medium rounded border border-teal-200 transition-colors"
              >
                View Patient &amp; AI Summary &rarr;
              </button>
            </div>
          </div>
        </article>
      `;
    });

    resultsContainer.innerHTML = cardsHtml;
    announce(`Found ${data.total_results} relevant records.`);
  }

  // -------------------------------------------------------------------------
  // Patient Directory Implementation
  // -------------------------------------------------------------------------
  async function loadPatients() {
    patientsTableContainer.innerHTML = `
      <div class="text-center py-8 text-xs text-slate-500">
        <div class="inline-block animate-spin rounded-full h-5 w-5 border-b-2 border-teal-700 mb-2"></div>
        <p>Loading registered patients...</p>
      </div>
    `;

    try {
      const resp = await fetch("/api/v1/patients");
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const patients = await resp.json();

      if (patients.length === 0) {
        patientsTableContainer.innerHTML = `
          <div class="text-center py-10 bg-slate-50 rounded-lg border border-dashed border-slate-200">
            <p class="text-xs text-slate-500">No patients registered in the database yet.</p>
            <button type="button" onclick="window.switchTab('ingest')" class="mt-2 text-xs font-medium text-teal-700 underline">
              Upload synthetic records to get started &rarr;
            </button>
          </div>
        `;
        return;
      }

      let tableHtml = `
        <table class="min-w-full divide-y divide-slate-200 text-left text-xs">
          <thead class="bg-slate-50 font-semibold text-slate-700">
            <tr>
              <th scope="col" class="py-2.5 px-3">Patient Name</th>
              <th scope="col" class="py-2.5 px-3">MRN</th>
              <th scope="col" class="py-2.5 px-3">Gender / DOB</th>
              <th scope="col" class="py-2.5 px-3">Status</th>
              <th scope="col" class="py-2.5 px-3 text-center">Records</th>
              <th scope="col" class="py-2.5 px-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 bg-white">
      `;

      patients.forEach((p) => {
        tableHtml += `
          <tr class="hover:bg-slate-50 transition-colors">
            <td class="py-2.5 px-3 font-medium text-slate-900">${escapeHtml(p.display_name)}</td>
            <td class="py-2.5 px-3 font-mono text-slate-600">${escapeHtml(p.mrn_normalized || "None")}</td>
            <td class="py-2.5 px-3 text-slate-600">${escapeHtml(p.gender)} &bull; ${escapeHtml(p.dob || "Unknown")}</td>
            <td class="py-2.5 px-3">
              <span class="px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                ${escapeHtml(p.identity_status)}
              </span>
            </td>
            <td class="py-2.5 px-3 text-center font-mono font-semibold text-slate-700">${p.record_count}</td>
            <td class="py-2.5 px-3 text-right">
              <button
                type="button"
                onclick="window.viewPatientDetails('${escapeJs(p.patient_key)}')"
                class="px-2.5 py-1 text-xs font-medium text-teal-800 bg-teal-50 hover:bg-teal-100 rounded border border-teal-200 transition-colors"
              >
                View Summary &rarr;
              </button>
            </td>
          </tr>
        `;
      });

      tableHtml += `</tbody></table>`;
      patientsTableContainer.innerHTML = tableHtml;
      announce(`Loaded ${patients.length} patients.`);
    } catch (err) {
      patientsTableContainer.innerHTML = `
        <div class="bg-red-50 text-red-700 p-4 rounded-lg text-xs border border-red-200">
          Failed to load patients list: ${escapeHtml(err.message)}
        </div>
      `;
    }
  }

  if (refreshPatientsBtn) {
    refreshPatientsBtn.addEventListener("click", loadPatients);
  }

  // -------------------------------------------------------------------------
  // Patient Details & AI Summary Modal
  // -------------------------------------------------------------------------
  window.viewPatientDetails = async function (patientId) {
    activePatient = patientId;
    activeModalTab = "summary";
    lastActiveElement = document.activeElement;

    modalTitle.textContent = "Loading Patient Information...";
    modalSubtitle.textContent = patientId;
    modalIdBadge.textContent = patientId;
    modalContent.innerHTML = `
      <div class="py-12 text-center space-y-3">
        <div class="inline-block animate-spin rounded-full h-7 w-7 border-b-2 border-teal-700"></div>
        <p class="text-xs text-slate-500">Retrieving patient records, summary, and FHIR resources...</p>
      </div>
    `;

    detailModal.classList.remove("hidden");
    if (modalCloseBtn) modalCloseBtn.focus();

    updateModalTabHeaders();
    await loadModalContent();
  };

  function updateModalTabHeaders() {
    [
      { btn: modalTabSummary, id: "summary" },
      { btn: modalTabRecords, id: "records" },
      { btn: modalTabBundle, id: "bundle" },
    ].forEach(({ btn, id }) => {
      if (id === activeModalTab) {
        btn.className = "py-2.5 border-b-2 border-teal-700 text-teal-800 font-semibold";
      } else {
        btn.className = "py-2.5 border-b-2 border-transparent text-slate-500 hover:text-slate-800";
      }
    });
  }

  modalTabSummary.addEventListener("click", () => {
    activeModalTab = "summary";
    updateModalTabHeaders();
    loadModalContent();
  });

  modalTabRecords.addEventListener("click", () => {
    activeModalTab = "records";
    updateModalTabHeaders();
    loadModalContent();
  });

  modalTabBundle.addEventListener("click", () => {
    activeModalTab = "bundle";
    updateModalTabHeaders();
    loadModalContent();
  });

  async function loadModalContent(forceRefresh = false) {
    if (!activePatient) return;

    if (activeModalTab === "summary") {
      modalContent.innerHTML = `<div class="py-8 text-center text-slate-500"><div class="inline-block animate-spin rounded-full h-5 w-5 border-b-2 border-teal-700 mb-2"></div><p>Generating evidence-grounded clinical summary...</p></div>`;
      try {
        const url = `/api/v1/patients/${encodeURIComponent(activePatient)}/summary${forceRefresh ? "?force_refresh=true" : ""}`;
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const summary = await resp.json();

        modalTitle.textContent = summary.patient_name || "Patient Summary";
        modalSubtitle.textContent = `MRN: ${summary.mrn || "Unknown"} | Generated: ${new Date(summary.generated_at).toLocaleString()}`;

        const isAI = summary.is_ai_generated;
        const badgeClass = isAI
          ? "bg-purple-50 text-purple-800 border-purple-200"
          : "bg-blue-50 text-blue-800 border-blue-200";

        const badgeLabel = isAI
          ? `AI-Generated (${summary.provider} / ${summary.model})`
          : `Deterministic Offline Fallback (${summary.provider})`;

        let diagnosesHtml = summary.key_diagnoses.length > 0
          ? summary.key_diagnoses.map((d) => `<li class="font-medium text-slate-800">${escapeHtml(d)}</li>`).join("")
          : `<li class="text-slate-400 italic">None explicitly documented</li>`;

        let findingsHtml = summary.key_findings.length > 0
          ? summary.key_findings.map((f) => `<li>${escapeHtml(f)}</li>`).join("")
          : `<li class="text-slate-400 italic">No specific findings extracted</li>`;

        let anomaliesHtml = summary.flagged_anomalies.length > 0
          ? summary.flagged_anomalies.map((a) => `<span class="inline-block px-2 py-0.5 bg-amber-50 text-amber-900 border border-amber-200 rounded text-[11px] font-mono mr-1.5 mb-1.5">${escapeHtml(a)}</span>`).join("")
          : `<span class="text-slate-400 italic">No out-of-range anomalies flagged</span>`;

        modalContent.innerHTML = `
          <!-- Generation Provenance Banner -->
          <div class="flex items-center justify-between p-3 rounded-lg border ${badgeClass}">
            <div class="flex items-center gap-2">
              <span class="w-2 h-2 rounded-full ${isAI ? "bg-purple-600" : "bg-blue-600"}"></span>
              <span class="font-medium">${badgeLabel}</span>
              ${summary.cache_status === "hit" ? `<span class="text-[10px] bg-white/70 px-1.5 py-0.2 rounded border">Cached</span>` : ""}
            </div>
            <button
              type="button"
              onclick="window.loadModalContent(true)"
              class="px-2.5 py-1 text-[11px] font-medium bg-white hover:bg-slate-50 text-slate-700 rounded border border-slate-300 transition-colors"
            >
              Regenerate &#x21bb;
            </button>
          </div>

          <!-- Narrative Synthesis -->
          <div class="bg-slate-50 p-4 rounded-xl border border-slate-200">
            <h4 class="text-xs font-semibold text-slate-900 mb-1">Clinical Narrative Summary (${summary.word_count} words)</h4>
            <p class="text-xs text-slate-800 leading-relaxed">${escapeHtml(summary.narrative_summary)}</p>
          </div>

          <!-- Structured Evidence Sections -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="border border-slate-200 rounded-lg p-3">
              <h5 class="font-semibold text-slate-800 mb-1.5 text-xs">Chief Concern</h5>
              <p class="text-slate-700">${escapeHtml(summary.chief_concern)}</p>
            </div>
            <div class="border border-slate-200 rounded-lg p-3">
              <h5 class="font-semibold text-slate-800 mb-1.5 text-xs">Documented Diagnoses</h5>
              <ul class="list-disc pl-4 space-y-1 text-slate-700">${diagnosesHtml}</ul>
            </div>
          </div>

          <!-- Findings & Flagged Anomalies -->
          <div class="border border-slate-200 rounded-lg p-3">
            <h5 class="font-semibold text-slate-800 mb-1 text-xs">Flagged Laboratory &amp; Imaging Anomalies</h5>
            <div class="mt-1">${anomaliesHtml}</div>
          </div>

          <div class="border border-slate-200 rounded-lg p-3">
            <h5 class="font-semibold text-slate-800 mb-1.5 text-xs">Notable Findings &amp; Observations</h5>
            <ul class="list-disc pl-4 space-y-1 text-slate-700">${findingsHtml}</ul>
          </div>

          <!-- Limitations / Confidence -->
          ${summary.confidence_or_limitations ? `
            <div class="border border-slate-100 bg-slate-50/50 rounded-lg p-3 text-slate-600">
              <strong class="font-medium text-slate-700">Source Boundaries &amp; Limitations:</strong>
              ${escapeHtml(summary.confidence_or_limitations)}
            </div>
          ` : ""}

          <!-- Mandatory Clinical Disclaimer -->
          <div class="bg-amber-50 border border-amber-200 text-amber-900 p-3 rounded-lg text-[11px] leading-tight">
            <strong>ADVISORY DISCLAIMER:</strong> ${escapeHtml(summary.disclaimer)}
          </div>
        `;
      } catch (err) {
        modalContent.innerHTML = `
          <div class="bg-red-50 text-red-800 p-4 rounded-lg text-xs border border-red-200">
            Failed to generate summary: ${escapeHtml(err.message)}
          </div>
        `;
      }
    } else if (activeModalTab === "records") {
      modalContent.innerHTML = `<div class="py-8 text-center text-slate-500"><div class="inline-block animate-spin rounded-full h-5 w-5 border-b-2 border-teal-700 mb-2"></div><p>Loading linked media records...</p></div>`;
      try {
        const resp = await fetch(`/api/v1/patients/${encodeURIComponent(activePatient)}/records`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const records = await resp.json();

        if (records.length === 0) {
          modalContent.innerHTML = `<p class="text-center py-8 text-slate-400">No media records linked to this patient.</p>`;
          return;
        }

        let html = `<div class="space-y-3">`;
        records.forEach((r) => {
          html += `
            <div class="border border-slate-200 rounded-lg p-3 bg-white">
              <div class="flex items-center justify-between mb-1">
                <span class="font-semibold text-slate-900">${escapeHtml(r.title)}</span>
                <span class="font-mono text-slate-500 text-[11px]">${r.record_date || "Undated"}</span>
              </div>
              <p class="font-mono text-xs text-slate-700 bg-slate-50 p-2 rounded border border-slate-100 mt-2">${escapeHtml(r.text)}</p>
            </div>
          `;
        });
        html += `</div>`;
        modalContent.innerHTML = html;
      } catch (err) {
        modalContent.innerHTML = `<div class="bg-red-50 text-red-800 p-4 rounded-lg text-xs">Failed to load records: ${escapeHtml(err.message)}</div>`;
      }
    } else if (activeModalTab === "bundle") {
      modalContent.innerHTML = `<div class="py-8 text-center text-slate-500"><div class="inline-block animate-spin rounded-full h-5 w-5 border-b-2 border-teal-700 mb-2"></div><p>Retrieving FHIR R4 Bundle...</p></div>`;
      try {
        const resp = await fetch(`/api/v1/patients/${encodeURIComponent(activePatient)}/bundle`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();

        modalContent.innerHTML = `
          <div class="flex items-center justify-between mb-2">
            <span class="font-mono text-xs text-teal-800 font-semibold">FHIR R4 Bundle (${data.resource_count} resources &bull; Status: ${escapeHtml(data.validation_status)})</span>
            <button
              type="button"
              onclick="navigator.clipboard.writeText(document.getElementById('bundle-raw-json').textContent); alert('Copied FHIR Bundle JSON to clipboard!');"
              class="px-2.5 py-1 text-xs bg-slate-100 hover:bg-slate-200 rounded border border-slate-300 font-medium"
            >
              Copy Bundle JSON
            </button>
          </div>
          <pre id="bundle-raw-json" class="json-viewer bg-slate-900 text-slate-200 p-3 rounded-lg overflow-x-auto max-h-96 text-xs">${escapeHtml(JSON.stringify(data.bundle, null, 2))}</pre>
        `;
      } catch (err) {
        modalContent.innerHTML = `<div class="bg-red-50 text-red-800 p-4 rounded-lg text-xs">Failed to load FHIR Bundle: ${escapeHtml(err.message)}</div>`;
      }
    }
  }
  window.loadModalContent = loadModalContent;

  window.closeModal = function () {
    if (detailModal) {
      detailModal.classList.add("hidden");
      if (lastActiveElement) {
        lastActiveElement.focus();
      }
    }
  };

  if (modalCloseBtn) {
    modalCloseBtn.addEventListener("click", window.closeModal);
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && detailModal && !detailModal.classList.contains("hidden")) {
      window.closeModal();
    }
  });

  // -------------------------------------------------------------------------
  // Ingest & File Upload Implementation
  // -------------------------------------------------------------------------
  if (dropzone && fileInput) {
    dropzone.addEventListener("click", () => fileInput.click());

    ["dragenter", "dragover"].forEach((eventName) => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropzone.classList.add("border-teal-600", "bg-teal-50/50");
      });
    });

    ["dragleave", "drop"].forEach((eventName) => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropzone.classList.remove("border-teal-600", "bg-teal-50/50");
      });
    });

    dropzone.addEventListener("drop", (e) => {
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        uploadFile(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener("change", () => {
      if (fileInput.files && fileInput.files.length > 0) {
        uploadFile(fileInput.files[0]);
      }
    });
  }

  async function uploadFile(file) {
    if (!file) return;

    ingestResultsContainer.classList.remove("hidden");
    ingestResultsContainer.innerHTML = `
      <div class="bg-slate-50 border border-slate-200 p-6 rounded-xl text-center space-y-2">
        <div class="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-teal-700"></div>
        <p class="text-xs font-medium text-slate-800">Processing file: ${escapeHtml(file.name)}</p>
        <p class="text-[11px] text-slate-500">Parsing syntax, normalizing clinical entities, resolving identities, generating FHIR R4, and indexing vectors...</p>
      </div>
    `;

    const formData = new FormData();
    formData.append("file", file);

    try {
      const resp = await fetch("/api/v1/ingest", {
        method: "POST",
        body: formData,
      });

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || `Server returned error ${resp.status}`);
      }

      const result = await resp.json();
      renderIngestResults(result, file.name);
      loadSystemStats();
    } catch (err) {
      ingestResultsContainer.innerHTML = `
        <div class="bg-red-50 border border-red-200 text-red-800 p-4 rounded-xl text-xs">
          <h4 class="font-bold mb-1">Ingestion Error</h4>
          <p>${escapeHtml(err.message)}</p>
        </div>
      `;
    }
  }

  function renderIngestResults(result, filename) {
    let auditRows = "";
    (result.audit_log || []).slice(0, 8).forEach((entry) => {
      auditRows += `
        <tr class="hover:bg-slate-50">
          <td class="py-1.5 px-2 font-mono text-[11px] text-slate-700">${escapeHtml(entry.action)}</td>
          <td class="py-1.5 px-2 text-slate-600">${escapeHtml(entry.field)}</td>
          <td class="py-1.5 px-2 text-slate-500 max-w-xs truncate" title="${escapeHtml(entry.reason)}">${escapeHtml(entry.reason)}</td>
        </tr>
      `;
    });

    ingestResultsContainer.innerHTML = `
      <div class="bg-white border border-slate-200 p-5 rounded-xl shadow-sm space-y-4">
        <div class="flex items-center justify-between pb-3 border-b border-slate-100">
          <h4 class="text-xs font-semibold text-slate-900">Ingestion Complete: ${escapeHtml(filename)}</h4>
          <span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-800">Success</span>
        </div>

        <!-- Metrics Grid -->
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
          <div class="bg-emerald-50 border border-emerald-200 p-3 rounded-lg">
            <span class="text-lg font-bold text-emerald-800">${result.accepted}</span>
            <p class="text-[11px] font-medium text-emerald-700">Accepted</p>
          </div>
          <div class="bg-blue-50 border border-blue-200 p-3 rounded-lg">
            <span class="text-lg font-bold text-blue-800">${result.duplicates}</span>
            <p class="text-[11px] font-medium text-blue-700">Suppressed Dups</p>
          </div>
          <div class="bg-amber-50 border border-amber-200 p-3 rounded-lg">
            <span class="text-lg font-bold text-amber-800">${result.quarantined}</span>
            <p class="text-[11px] font-medium text-amber-700">Quarantined</p>
          </div>
          <div class="bg-rose-50 border border-rose-200 p-3 rounded-lg">
            <span class="text-lg font-bold text-rose-800">${result.rejected}</span>
            <p class="text-[11px] font-medium text-rose-700">Rejected</p>
          </div>
        </div>

        <!-- Warnings & Quarantines -->
        ${result.warnings && result.warnings.length > 0 ? `
          <div class="bg-amber-50/60 border border-amber-200 rounded-lg p-3 text-[11px] text-amber-900">
            <strong class="font-semibold block mb-1">Warnings / Identity Resolution Notices:</strong>
            <ul class="list-disc pl-4 space-y-0.5">
              ${result.warnings.map((w) => `<li>${escapeHtml(w)}</li>`).join("")}
            </ul>
          </div>
        ` : ""}

        <!-- Audit Log Summary -->
        ${auditRows ? `
          <div>
            <h5 class="text-xs font-semibold text-slate-800 mb-1.5">Transformation Audit Trail</h5>
            <div class="overflow-x-auto border border-slate-200 rounded-lg">
              <table class="min-w-full divide-y divide-slate-100 text-xs">
                <thead class="bg-slate-50 text-slate-600 font-medium">
                  <tr>
                    <th class="py-1 px-2 text-left">Action</th>
                    <th class="py-1 px-2 text-left">Field</th>
                    <th class="py-1 px-2 text-left">Reason</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-100 bg-white">${auditRows}</tbody>
              </table>
            </div>
          </div>
        ` : ""}
      </div>
    `;
    announce(`Ingested ${result.accepted} records successfully.`);
  }

  // -------------------------------------------------------------------------
  // FHIR Explorer Implementation
  // -------------------------------------------------------------------------
  if (fhirFetchBtn) {
    fhirFetchBtn.addEventListener("click", async () => {
      const resourceType = fhirResourceSelect.value;
      const resourceId = fhirIdInput.value.trim();
      if (!resourceId) {
        alert("Please enter a Resource ID or Patient MRN.");
        return;
      }

      fhirOutputContainer.classList.remove("hidden");
      fhirJsonCode.textContent = "Loading FHIR data from server...";

      let url = "";
      if (resourceType === "Bundle") {
        url = `/api/v1/patients/${encodeURIComponent(resourceId)}/bundle`;
      } else {
        url = `/api/v1/fhir/${encodeURIComponent(resourceType)}/${encodeURIComponent(resourceId)}`;
      }

      try {
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}: Resource not found or unavailable.`);
        const data = await resp.json();
        fhirOutputTitle.textContent = `${resourceType} &bull; ${resourceId}`;
        fhirJsonCode.textContent = JSON.stringify(data, null, 2);
        announce(`Fetched ${resourceType} resource.`);
      } catch (err) {
        fhirJsonCode.textContent = `Error: ${err.message}`;
      }
    });
  }

  if (fhirCopyBtn) {
    fhirCopyBtn.addEventListener("click", () => {
      const code = fhirJsonCode.textContent;
      if (code) {
        navigator.clipboard.writeText(code);
        alert("Copied FHIR resource JSON to clipboard!");
      }
    });
  }

  // -------------------------------------------------------------------------
  // String & HTML Sanitization Helpers
  // -------------------------------------------------------------------------
  function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function escapeJs(str) {
    if (str === null || str === undefined) return "";
    return String(str).replace(/'/g, "\\'");
  }

  // -------------------------------------------------------------------------
  // Initialize Application
  // -------------------------------------------------------------------------
  loadSystemStats();
  switchTab("search");
});
