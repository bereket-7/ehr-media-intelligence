/**
 * EHR Media Intelligence Platform - Frontend Application Client
 * Milestone 0: Foundation, Health Check & State Architecture
 */

document.addEventListener("DOMContentLoaded", () => {
  const statusIndicator = document.getElementById("status-indicator");
  const statusText = document.getElementById("status-text");
  const liveRegion = document.getElementById("live-region");
  const searchForm = document.getElementById("search-form");
  const clearFiltersBtn = document.getElementById("clear-filters-btn");
  const detailModal = document.getElementById("detail-modal");
  const modalCloseBtn = document.getElementById("modal-close-btn");

  let lastActiveElement = null;

  // Announce messages to screen readers
  function announce(message) {
    if (liveRegion) {
      liveRegion.textContent = "";
      setTimeout(() => {
        liveRegion.textContent = message;
      }, 50);
    }
  }

  // Health check probe
  async function checkHealth() {
    try {
      const response = await fetch("/health");
      if (response.ok) {
        const data = await response.json();
        if (statusIndicator && statusText) {
          statusIndicator.className = "w-2 h-2 rounded-full bg-emerald-500";
          statusText.textContent = `API Ready (v${data.version || "0.1.0"})`;
        }
        announce("Connected to EHR Media Intelligence API service.");
      } else {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (err) {
      if (statusIndicator && statusText) {
        statusIndicator.className = "w-2 h-2 rounded-full bg-amber-500";
        statusText.textContent = "API Unreachable";
      }
      announce("Warning: Could not connect to the API service.");
    }
  }

  // Clear filters handler
  if (clearFiltersBtn) {
    clearFiltersBtn.addEventListener("click", () => {
      const resourceSelect = document.getElementById("filter-resource-type");
      const dateFrom = document.getElementById("filter-date-from");
      const dateTo = document.getElementById("filter-date-to");
      if (resourceSelect) resourceSelect.value = "";
      if (dateFrom) dateFrom.value = "";
      if (dateTo) dateTo.value = "";
      announce("Filters reset.");
    });
  }

  // Search submission placeholder
  if (searchForm) {
    searchForm.addEventListener("submit", (e) => {
      e.preventDefault();
      announce("Milestone 0 active: Search functionality will be enabled in Milestone 4.");
    });
  }

  // Modal helpers
  window.openModal = function (title, contentHtml) {
    lastActiveElement = document.activeElement;
    const modalTitle = document.getElementById("modal-title");
    const modalContent = document.getElementById("modal-content");
    if (modalTitle) modalTitle.textContent = title;
    if (modalContent) modalContent.innerHTML = contentHtml;
    if (detailModal) {
      detailModal.classList.remove("hidden");
      if (modalCloseBtn) modalCloseBtn.focus();
    }
    announce(`Opened details for ${title}`);
  };

  window.closeModal = function () {
    if (detailModal) {
      detailModal.classList.add("hidden");
      if (lastActiveElement) {
        lastActiveElement.focus();
      }
    }
    announce("Closed details modal.");
  };

  if (modalCloseBtn) {
    modalCloseBtn.addEventListener("click", window.closeModal);
  }

  // Close modal on Escape
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && detailModal && !detailModal.classList.contains("hidden")) {
      window.closeModal();
    }
  });

  // Run initial health probe
  checkHealth();
});
