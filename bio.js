(() => {
  "use strict";

  const page = document.querySelector("[data-bio-page]");
  if (!page) return;

  // Each [data-tabs] wrapper owns its own tabs and panels.
  page.querySelectorAll("[data-tabs]").forEach((group) => {
    const tabs = [...group.querySelectorAll("[data-tab]")];
    const panels = [...group.querySelectorAll("[data-panel]")];
    if (!tabs.length) return;

    const activateTab = (tab, moveFocus = false) => {
      const selected = tab.dataset.tab;
      tabs.forEach((candidate) => {
        const active = candidate === tab;
        candidate.setAttribute("aria-selected", String(active));
        candidate.tabIndex = active ? 0 : -1;
      });
      panels.forEach((panel) => {
        panel.hidden = panel.dataset.panel !== selected;
      });
      if (moveFocus) tab.focus();
    };

    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => activateTab(tab));
      tab.addEventListener("keydown", (event) => {
        let nextIndex = null;
        if (event.key === "ArrowRight" || event.key === "ArrowDown") {
          nextIndex = (index + 1) % tabs.length;
        } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
          nextIndex = (index - 1 + tabs.length) % tabs.length;
        } else if (event.key === "Home") {
          nextIndex = 0;
        } else if (event.key === "End") {
          nextIndex = tabs.length - 1;
        }
        if (nextIndex !== null) {
          event.preventDefault();
          activateTab(tabs[nextIndex], true);
        }
      });
    });
  });

  const fallbackCopy = (text) => {
    const input = document.createElement("textarea");
    input.value = text;
    input.setAttribute("readonly", "");
    input.style.position = "fixed";
    input.style.opacity = "0";
    document.body.appendChild(input);
    input.select();
    const copied = document.execCommand("copy");
    input.remove();
    if (!copied) throw new Error("Copy command was rejected");
  };

  page.querySelectorAll("[data-copy-bio]").forEach((button) => {
    button.addEventListener("click", async () => {
      const key = button.dataset.copyBio;
      const panel = page.querySelector(`[data-panel="${key}"]`);
      const source = panel?.querySelector("[data-bio-copy]");
      const status = page.querySelector(`[data-copy-status="${key}"]`);
      if (!source || !status) return;

      const text = source.innerText.replace(/\s+/g, " ").trim();
      try {
        if (navigator.clipboard?.writeText) {
          await navigator.clipboard.writeText(text);
        } else {
          fallbackCopy(text);
        }
        button.textContent = "Copied";
        status.textContent = "Biography copied to clipboard.";
      } catch {
        status.textContent = "Copy was blocked; select the text manually.";
      }
      window.setTimeout(() => {
        button.textContent = "Copy text";
        status.textContent = "";
      }, 2200);
    });
  });

  const numberFormatter = new Intl.NumberFormat("en-US");

  const formatMetricDate = (isoDate) => {
    const value = new Date(`${isoDate}T12:00:00Z`);
    if (Number.isNaN(value.getTime())) return isoDate;
    return new Intl.DateTimeFormat("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    }).format(value);
  };

  fetch("bio-metrics.json", { cache: "no-store" })
    .then((response) => {
      if (!response.ok) throw new Error(`Metric request returned ${response.status}`);
      return response.json();
    })
    .then((metrics) => {
      const citations = Number(metrics.citations);
      const hIndex = Number(metrics.h_index);
      if (!Number.isInteger(citations) || citations < 1000) throw new Error("Invalid citation count");

      page.querySelectorAll('[data-metric="citations"]').forEach((element) => {
        element.textContent = numberFormatter.format(citations);
      });
      const citationLink = page.querySelector(".metric-card-link");
      citationLink?.setAttribute(
        "aria-label",
        `${numberFormatter.format(citations)} Google Scholar citations; open profile`,
      );
      if (Number.isInteger(hIndex)) {
        page.querySelectorAll('[data-metric="h_index"]').forEach((element) => {
          element.textContent = numberFormatter.format(hIndex);
        });
      }
      page.querySelectorAll("[data-metric-date]").forEach((element) => {
        element.dateTime = metrics.as_of;
        element.textContent = formatMetricDate(metrics.as_of);
      });
      page.dataset.metricsState = "live";
    })
    .catch(() => {
      page.dataset.metricsState = "cached";
    });
})();
