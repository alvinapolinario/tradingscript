/**
 * Shared left navigation for Vantage advisory UIs.
 * Usage: <body data-nav="analyzer"> … <script src="/static/shell.js"></script>
 */
(function () {
  const ICONS = {
    grid: '<svg class="sb-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>',
    target: '<svg class="sb-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="1.2" fill="currentColor"/></svg>',
    signal: '<svg class="sb-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 19v-2"/><path d="M8.5 16.5a5 5 0 0 1 7 0"/><path d="M5.5 13.5a9 9 0 0 1 13 0"/><circle cx="12" cy="20" r="1" fill="currentColor"/></svg>',
    radar: '<svg class="sb-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="8"/><path d="M12 12 17 7"/><circle cx="12" cy="12" r="2" fill="currentColor"/></svg>',
    shapes: '<svg class="sb-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="m12 4 4 7H8l4-7Z"/><rect x="4" y="14" width="6" height="6" rx="1"/><circle cx="17" cy="17" r="3"/></svg>',
    search: '<svg class="sb-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4"/></svg>',
    flask: '<svg class="sb-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M9 3h6"/><path d="M10 3v6l-5.2 8.3A2 2 0 0 0 6.5 20h11a2 2 0 0 0 1.7-2.7L14 9V3"/></svg>',
    chart: '<svg class="sb-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 19h16"/><path d="M7 16V10"/><path d="M12 16V6"/><path d="M17 16v-4"/></svg>',
    calc: '<svg class="sb-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 7h8M8 11h2M12 11h2M16 11h0M8 15h2M12 15h2M16 15h0"/></svg>',
    book: '<svg class="sb-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21.5V5.5Z"/><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/></svg>',
    gear: '<svg class="sb-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="3"/><path d="M12 3.5v2.2M12 18.3v2.2M4.9 7.1l1.6 1.5M17.5 15.4l1.6 1.5M3.5 12h2.2M18.3 12h2.2M4.9 16.9l1.6-1.5M17.5 8.6l1.6-1.5"/></svg>',
  };

  const WORKSPACE = [
    { id: "monitor", href: "/monitor", label: "Market Overview", icon: "grid" },
    { id: "analyzer", href: "/analyzer", label: "Smart Analyzer", icon: "target" },
    { id: "signals", href: "/signals", label: "Signal Center", icon: "signal", badgeId: "sbRadarBadge" },
    { id: "radar", href: "/dashboard", label: "Opportunity Radar", icon: "radar" },
    { id: "patterns", href: "/patterns", label: "Pattern Strategy", icon: "shapes" },
    { id: "scanner", href: "/scanner", label: "Strategy Scanner", icon: "search" },
    { id: "lab", href: "/lab", label: "Strategy Lab", icon: "flask" },
  ];

  const TOOLS = [
    { id: "backtester", href: "/coming-soon?t=Backtester", label: "Backtester", icon: "chart" },
    { id: "risk", href: "/coming-soon?t=Risk%20Calculator", label: "Risk Calculator", icon: "calc" },
    { id: "journal", href: "/coming-soon?t=Trade%20Journal", label: "Trade Journal", icon: "book" },
    { id: "settings", href: "/coming-soon?t=Data%20%26%20Settings", label: "Data & Settings", icon: "gear" },
  ];

  function itemHtml(item, activeId) {
    let isActive = item.id === activeId;
    if (activeId === "dashboard" && item.id === "radar") isActive = true;
    if (activeId === "lab" && item.id === "lab") isActive = true;
    const badge = item.badgeId
      ? `<span class="sb-badge" id="${item.badgeId}" hidden>0</span>`
      : `<span class="sb-dot" aria-hidden="true"></span>`;
    return `<a class="sb-item${isActive ? " active" : ""}" href="${item.href}" data-nav-id="${item.id}">
      ${ICONS[item.icon] || ""}
      <span class="sb-label">${item.label}</span>
      ${badge}
    </a>`;
  }

  function section(label, items, activeId) {
    return `<div class="sb-section">
      <div class="sb-section-label">${label}</div>
      ${items.map((i) => itemHtml(i, activeId)).join("")}
    </div>`;
  }

  const activeId = (document.body.getAttribute("data-nav") || "").toLowerCase();
  const view = new URLSearchParams(location.search).get("view");
  const resolvedActive =
    activeId === "dashboard" && view === "lab" ? "lab" : activeId;
  document.body.classList.add("has-app-shell");

  const aside = document.createElement("aside");
  aside.className = "app-sidebar";
  aside.setAttribute("aria-label", "Primary");
  aside.innerHTML = `
    <div class="sb-brand">
      <div class="sb-mark" aria-hidden="true"></div>
      <div class="sb-brand-text">Vantage Desk<span>Advisory only</span></div>
    </div>
    ${section("Workspace", WORKSPACE, resolvedActive)}
    ${section("Tools", TOOLS, resolvedActive)}
    <div class="sb-foot">No auto-trading · decisions stay on this host</div>
  `;

  const backdrop = document.createElement("div");
  backdrop.className = "app-sidebar-backdrop";
  backdrop.addEventListener("click", () => document.body.classList.remove("app-shell-open"));

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "app-shell-toggle";
  toggle.setAttribute("aria-label", "Open menu");
  toggle.textContent = "☰";
  toggle.addEventListener("click", () => document.body.classList.toggle("app-shell-open"));

  document.body.prepend(backdrop);
  document.body.prepend(aside);
  document.body.prepend(toggle);

  // Opportunity Radar badge = pending accepted signals awaiting decision
  fetch("/api/v1/signals?limit=50")
    .then((r) => r.json())
    .then((j) => {
      const n = (j.items || []).filter((s) => (s.user_decision || "PENDING") === "PENDING").length;
      const el = document.getElementById("sbRadarBadge");
      if (!el) return;
      if (n > 0) {
        el.hidden = false;
        el.textContent = String(n > 9 ? "9+" : n);
      }
    })
    .catch(() => {});
})();
