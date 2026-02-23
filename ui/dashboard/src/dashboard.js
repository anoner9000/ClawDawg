import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart,
  DoughnutController,
  Legend,
  LinearScale,
  Tooltip,
} from "chart.js";
import * as echarts from "echarts/core";
import { PieChart } from "echarts/charts";
import { LegendComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { formatHex, oklch } from "culori";
import gsap from "gsap";
import { createIcons, icons } from "lucide";
import lottie from "lottie-web";
import { animate, stagger } from "motion";

Chart.register(
  DoughnutController,
  ArcElement,
  BarElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Legend,
);
echarts.use([PieChart, TooltipComponent, LegendComponent, CanvasRenderer]);

const chartMap = new WeakMap();
const echartMap = new WeakMap();

function setupVisualStack(scope = document) {
  const root = document.documentElement;
  if (!root.dataset.vfxInit) {
    root.dataset.vfxInit = "1";
    const neon = formatHex(oklch({ mode: "oklch", l: 0.78, c: 0.19, h: 150 }));
    root.style.setProperty("--vfx-neon", neon);
    if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      gsap.from(".site-header", { y: -14, opacity: 0, duration: 0.45, ease: "power2.out" });
      gsap.to(".site-header", { boxShadow: "0 10px 24px color-mix(in srgb, var(--vfx-neon) 30%, transparent 70%)", duration: 1.6, yoyo: true, repeat: -1 });
    }
  }

  if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    const targets = [...scope.querySelectorAll(".panel-section, .intel-card, .overview-card")].filter((el) => el.dataset.vfxBound !== "1");
    if (targets.length) {
      targets.forEach((el) => { el.dataset.vfxBound = "1"; });
      animate(targets, { opacity: [0, 1], transform: ["translateY(10px)", "translateY(0px)"] }, { duration: 0.35, delay: stagger(0.03), easing: "ease-out" });
    }
  }

  scope.querySelectorAll("[data-lottie-json]").forEach((el) => {
    if (el.dataset.lottieBound === "1") return;
    const path = (el.dataset.lottieJson || "").trim();
    if (!path) return;
    el.dataset.lottieBound = "1";
    lottie.loadAnimation({
      container: el,
      renderer: "svg",
      loop: true,
      autoplay: true,
      path,
    });
  });
}

function emitServerAudit(payload) {
  const eventType = String(payload?.event_type || "").trim();
  if (!eventType) return;
  fetch("/actions/ui-audit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    keepalive: true,
  }).catch(() => {});
}

function renderRingCharts(scope = document) {
  scope.querySelectorAll("[data-ring-chart]").forEach((container) => {
    const canvas = container.querySelector("canvas");
    if (!canvas) return;

    const value = Number(container.dataset.value || "0");
    const tone = container.dataset.tone === "gold" ? "#d7a12c" : "#006a79";
    const remainder = Math.max(0, 100 - value);

    const old = chartMap.get(canvas);
    if (old) old.destroy();

    const chart = new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: ["value", "remainder"],
        datasets: [
          {
            data: [value, remainder],
            backgroundColor: [tone, "#e3ddd0"],
            borderWidth: 0,
            cutout: "74%",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
      },
    });
    chartMap.set(canvas, chart);
  });
}

function renderSparkline(scope = document) {
  scope.querySelectorAll("[data-sparkline]").forEach((canvas) => {
    const old = chartMap.get(canvas);
    if (old) old.destroy();

    const values = (canvas.dataset.values || "")
      .split(",")
      .map((n) => Number(n.trim()))
      .filter((n) => Number.isFinite(n));
    if (values.length === 0) return;

    const chart = new Chart(canvas, {
      type: "bar",
      data: {
        labels: values.map((_, idx) => `${idx + 1}`),
        datasets: [
          {
            data: values,
            borderRadius: 4,
            backgroundColor: ["#2d8e58", "#be8a24", "#bd4f40", "#7c918b"],
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { display: false },
          y: { display: false, beginAtZero: true },
        },
      },
    });
    chartMap.set(canvas, chart);
  });
}

function renderStateMix(scope = document) {
  scope.querySelectorAll("[data-state-mix]").forEach((el) => {
    const raw = el.dataset.stateMix || "[]";
    let rows = [];
    try {
      rows = JSON.parse(raw);
    } catch {
      rows = [];
    }
    if (!Array.isArray(rows) || rows.length === 0) return;

    const old = echartMap.get(el);
    if (old) old.dispose();

    const toneColor = {
      ok: "#2d8e58",
      warn: "#be8a24",
      err: "#bd4f40",
      muted: "#7c918b",
    };

    const chart = echarts.init(el, null, { renderer: "canvas" });
    chart.setOption({
      tooltip: { trigger: "item" },
      legend: { bottom: 0, icon: "roundRect" },
      series: [
        {
          type: "pie",
          radius: ["56%", "78%"],
          label: { formatter: "{d}%" },
          data: rows.map((r) => ({
            value: r.value,
            name: r.label,
            itemStyle: { color: toneColor[r.tone] || toneColor.muted },
          })),
        },
      ],
    });

    echartMap.set(el, chart);
  });
}

function renderIcons(scope = document) {
  createIcons({ icons, attrs: { "stroke-width": 1.8 }, root: scope });
}

function setupThemeToggle() {
  const root = document.documentElement;
  const key = "openclaw_ui_theme";
  const saved = localStorage.getItem(key);
  const preferred = saved || "day";
  root.setAttribute("data-theme", preferred);

  const toggles = document.querySelectorAll("#theme-toggle, #theme-toggle-fab");
  if (!toggles.length) return;

  const updateLabels = () => {
    const cur = root.getAttribute("data-theme") || "day";
    const next = cur === "night" ? "Day" : "Night";
    toggles.forEach((t) => {
      const span = t.querySelector("span");
      if (span) span.textContent = `${next} Mode`;
    });
  };

  toggles.forEach((toggle) => {
    if (toggle.dataset.bound === "1") return;
    toggle.dataset.bound = "1";
    toggle.addEventListener("click", () => {
      const cur = root.getAttribute("data-theme") || "day";
      const next = cur === "night" ? "day" : "night";
      root.setAttribute("data-theme", next);
      localStorage.setItem(key, next);
      updateLabels();
    });
  });

  updateLabels();
}

function legacyThemeToggle() {
  const root = document.documentElement;
  const toggle = document.querySelector("#theme-toggle");
  if (!toggle) return;
  toggle.addEventListener("click", () => {
    const cur = root.getAttribute("data-theme") || "day";
    const next = cur === "night" ? "day" : "night";
    root.setAttribute("data-theme", next);
    localStorage.setItem("openclaw_ui_theme", next);
  });
}

function setupTaskDrawer(scope = document) {
  const shell = document.querySelector("#task-drawer-shell");
  const content = document.querySelector("#task-drawer-content");
  if (!shell || !content) return;

  scope.querySelectorAll(".open-task-drawer").forEach((btn) => {
    if (btn.dataset.bound === "1") return;
    btn.dataset.bound = "1";
    btn.addEventListener("click", async () => {
      const taskId = btn.dataset.taskId;
      if (!taskId) return;
      shell.classList.remove("hidden");
      content.innerHTML = "<p class='muted'>Loading task details...</p>";
      try {
        const res = await fetch(`/partials/task-drawer?task_id=${encodeURIComponent(taskId)}`);
        content.innerHTML = await res.text();
        boot(content);
      } catch {
        content.innerHTML = "<p class='error'>Failed to load task details.</p>";
      }
    });
  });

  shell.querySelectorAll("[data-close-drawer='1']").forEach((el) => {
    if (el.dataset.bound === "1") return;
    el.dataset.bound = "1";
    el.addEventListener("click", () => shell.classList.add("hidden"));
  });
}

function setupCommandPalette() {
  const palette = document.querySelector("#command-palette");
  const input = document.querySelector("#command-palette-input");
  const list = document.querySelector("#command-palette-list");
  const opener = document.querySelector("#open-command-palette");
  if (!palette || !input || !list) return;

  const open = () => {
    palette.classList.remove("hidden");
    input.focus();
    input.select();
  };
  const close = () => palette.classList.add("hidden");

  const emitPaletteAudit = (commandId, result, reason = "") => {
    const key = "openclaw_ui_command_audit";
    let rows = [];
    try {
      rows = JSON.parse(localStorage.getItem(key) || "[]");
    } catch {
      rows = [];
    }
    rows.push({
      ts: new Date().toISOString(),
      type: result === "ok" ? "UI_COMMAND_EXECUTED" : "UI_COMMAND_DENIED",
      command_id: commandId || "unknown",
      result,
      reason,
    });
    if (rows.length > 200) rows = rows.slice(-200);
    localStorage.setItem(key, JSON.stringify(rows));
    emitServerAudit({
      event_type: result === "ok" ? "UI_COMMAND_EXECUTED" : "UI_COMMAND_DENIED",
      result,
      reason,
      action_id: String(commandId || "unknown"),
    });
  };

  const runCommand = (cmd) => {
    if (!cmd) return;
    const view = document.querySelector("#view-preset");
    const commandHandlers = {
      "nav-home": () => { location.href = "/"; },
      "nav-agents": () => { location.href = "/agents"; },
      "nav-tasks": () => { location.href = "/tasks"; },
      "nav-chat": () => { location.href = "/chat"; },
      "toggle-theme": () => {
        const btn = document.querySelector("#theme-toggle-fab") || document.querySelector("#theme-toggle");
        if (btn) btn.click();
      },
      "view-ops": () => {
        if (!view) return;
        view.value = "ops";
        view.dispatchEvent(new Event("change"));
      },
      "view-chat": () => {
        if (!view) return;
        view.value = "chat";
        view.dispatchEvent(new Event("change"));
      },
      "view-incident": () => {
        if (!view) return;
        view.value = "incident";
        view.dispatchEvent(new Event("change"));
      },
      "view-review": () => {
        if (!view) return;
        view.value = "review";
        view.dispatchEvent(new Event("change"));
      },
    };

    const handler = commandHandlers[cmd];
    if (!handler) {
      emitPaletteAudit(cmd, "denied", "unknown_command");
      return;
    }

    try {
      handler();
      emitPaletteAudit(cmd, "ok");
      close();
    } catch {
      emitPaletteAudit(cmd, "denied", "execution_error");
    }
  };

  if (!document.body.dataset.paletteBound) {
    document.body.dataset.paletteBound = "1";
    document.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        open();
      } else if (e.key === "Escape") {
        close();
      }
    });
  }

  if (opener && opener.dataset.bound !== "1") {
    opener.dataset.bound = "1";
    opener.addEventListener("click", open);
  }

  palette.querySelectorAll("[data-close-palette='1']").forEach((el) => {
    if (el.dataset.bound === "1") return;
    el.dataset.bound = "1";
    el.addEventListener("click", close);
  });

  if (list.dataset.bound !== "1") {
    list.dataset.bound = "1";
    list.addEventListener("click", (e) => {
      const li = e.target.closest("li[data-cmd]");
      if (!li) return;
      runCommand(li.dataset.cmd);
    });
  }

  if (input.dataset.bound !== "1") {
    input.dataset.bound = "1";
    input.addEventListener("input", () => {
      const q = input.value.trim().toLowerCase();
      list.querySelectorAll("li[data-cmd]").forEach((li) => {
        li.style.display = li.textContent.toLowerCase().includes(q) ? "" : "none";
      });
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const first = list.querySelector("li[data-cmd]:not([style*='display: none'])");
        if (first) runCommand(first.dataset.cmd);
      }
    });
  }
}

function setupSavedViews() {
  const select = document.querySelector("#view-preset");
  const root = document.querySelector(".home-v4");
  if (!select || !root) return;
  const key = "openclaw_saved_view";
  const allowedViews = new Set(["ops", "chat", "incident", "review"]);
  const auditKey = "openclaw_ui_view_audit";
  const emitViewAudit = (viewId, result, reason = "") => {
    let rows = [];
    try {
      rows = JSON.parse(localStorage.getItem(auditKey) || "[]");
    } catch {
      rows = [];
    }
    rows.push({
      ts: new Date().toISOString(),
      type: result === "ok" ? "UI_VIEW_APPLIED" : "UI_VIEW_DENIED",
      view_id: viewId || "unknown",
      result,
      reason,
    });
    if (rows.length > 200) rows = rows.slice(-200);
    localStorage.setItem(auditKey, JSON.stringify(rows));
    emitServerAudit({
      event_type: result === "ok" ? "UI_VIEW_APPLIED" : "UI_VIEW_DENIED",
      result,
      reason,
      action_id: String(viewId || "unknown"),
    });
  };

  const apply = (val, opts = {}) => {
    const emit = opts.emit !== false;
    const next = allowedViews.has(val) ? val : "ops";
    if (!allowedViews.has(val) && emit) emitViewAudit(val, "denied", "invalid_view");
    const prev = root.dataset.view || "";
    if (prev === next) {
      localStorage.setItem(key, next);
      return;
    }
    root.dataset.view = next;
    localStorage.setItem(key, root.dataset.view);
    if (emit) emitViewAudit(next, "ok");
  };
  if (select.dataset.bound !== "1") {
    select.dataset.bound = "1";
    select.addEventListener("change", () => apply(select.value, { emit: true }));
  }
  const savedRaw = localStorage.getItem(key) || select.value;
  const saved = allowedViews.has(savedRaw) ? savedRaw : "ops";
  select.value = saved;
  apply(saved, { emit: false });
}

function setupQuickActionAudit(scope = document) {
  const key = "openclaw_ui_quick_action_audit";
  const emit = (actionId, kind, result, reason = "") => {
    let rows = [];
    try {
      rows = JSON.parse(localStorage.getItem(key) || "[]");
    } catch {
      rows = [];
    }
    rows.push({
      ts: new Date().toISOString(),
      type: result === "ok" ? "UI_QUICK_ACTION_EXECUTED" : "UI_QUICK_ACTION_DENIED",
      action_id: actionId || "unknown",
      kind: kind || "unknown",
      result,
      reason,
    });
    if (rows.length > 200) rows = rows.slice(-200);
    localStorage.setItem(key, JSON.stringify(rows));
    emitServerAudit({
      event_type: result === "ok" ? "UI_QUICK_ACTION_EXECUTED" : "UI_QUICK_ACTION_DENIED",
      result,
      reason,
      action_id: String(actionId || "unknown"),
      detail: String(kind || "unknown"),
    });
  };

  scope.querySelectorAll("[data-action-id]").forEach((el) => {
    if (el.dataset.auditBound === "1") return;
    el.dataset.auditBound = "1";
    el.addEventListener("click", () => {
      const actionId = el.dataset.actionId || "unknown";
      const kind = el.dataset.actionKind || "unknown";
      const disabled = el.matches(":disabled") || el.classList.contains("qa-btn-disabled");
      if (disabled) {
        emit(actionId, kind, "denied", "policy_disabled");
      } else {
        emit(actionId, kind, "ok");
      }
    });
  });
}

function renderAgentGraph(scope = document) {
  scope.querySelectorAll("#agent-graph").forEach((el) => {
    let edges = [];
    try {
      edges = JSON.parse(el.dataset.graphEdges || "[]");
    } catch {
      edges = [];
    }
    if (!Array.isArray(edges) || edges.length === 0) {
      el.innerHTML = "<p class='muted'>No interaction edges yet.</p>";
      return;
    }
    const sanitizeToken = (v) => {
      const s = String(v || "").trim();
      return /^[A-Za-z0-9_.:-]{1,32}$/.test(s) ? s : "agent";
    };
    const safeEdges = edges.slice(0, 24).map((e) => ({
      source: sanitizeToken(e.source),
      target: sanitizeToken(e.target),
      count: Math.max(1, Math.min(999, Number(e.count) || 1)),
    })).filter((e) => e.source && e.target);

    const nodes = [...new Set(safeEdges.flatMap((e) => [e.source, e.target]))].slice(0, 24);
    const cx = 200;
    const cy = 130;
    const r = 96;
    const pos = new Map();
    nodes.forEach((n, i) => {
      const a = (Math.PI * 2 * i) / Math.max(nodes.length, 1);
      pos.set(n, { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) });
    });
    const lines = safeEdges.map((e) => {
      const s = pos.get(e.source);
      const t = pos.get(e.target);
      if (!s || !t) return "";
      const w = Math.max(1, Math.min(6, Number(e.count) || 1));
      return `<line x1="${s.x}" y1="${s.y}" x2="${t.x}" y2="${t.y}" stroke="#2aa1b2" stroke-width="${w}" opacity="0.65" />`;
    }).join("");
    const circles = nodes.map((n) => {
      const p = pos.get(n);
      return `<g><circle cx="${p.x}" cy="${p.y}" r="16" fill="#f6efe3" stroke="#2b808d" /><text x="${p.x}" y="${p.y + 4}" text-anchor="middle" font-size="8">${sanitizeToken(n).slice(0, 6)}</text></g>`;
    }).join("");
    el.innerHTML = `<svg viewBox="0 0 400 260" width="100%" height="260">${lines}${circles}</svg>`;
  });
}

function setupAlertActions(scope = document) {
  const now = Date.now();
  scope.querySelectorAll(".alert-item").forEach((item) => {
    const id = item.dataset.alertId;
    if (!id) return;
    const snoozeUntil = Number(localStorage.getItem(`alert_snooze_${id}`) || "0");
    if (snoozeUntil > now) item.style.display = "none";
  });
  scope.querySelectorAll(".alert-ack, .alert-snooze").forEach((btn) => {
    if (btn.dataset.bound === "1") return;
    btn.dataset.bound = "1";
    btn.addEventListener("click", () => {
      const item = btn.closest(".alert-item");
      if (!item) return;
      const id = item.dataset.alertId || "";
      if (btn.classList.contains("alert-snooze")) {
        localStorage.setItem(`alert_snooze_${id}`, String(Date.now() + 10 * 60 * 1000));
      }
      item.style.display = "none";
    });
  });
}

function setupChangeViewer(scope = document) {
  const el = scope.querySelector("#change-viewer");
  if (!el) return;
  let metrics = {};
  try {
    metrics = JSON.parse(el.dataset.metrics || "{}");
  } catch {
    metrics = {};
  }
  const key = "openclaw_change_metrics";
  const prev = JSON.parse(localStorage.getItem(key) || "{}");
  const delta = Object.keys(metrics).map((k) => {
    const cur = Number(metrics[k] || 0);
    const old = Number(prev[k] || 0);
    const d = cur - old;
    return `${k}:${d >= 0 ? "+" : ""}${d}`;
  }).join(" | ");
  const row = el.querySelector("#change-delta");
  if (row) row.textContent = `Delta: ${delta || "n/a"}`;
  localStorage.setItem(key, JSON.stringify(metrics));
}

function setupNotificationRules(scope = document) {
  const enabled = scope.querySelector("#notify-enabled");
  const stale = scope.querySelector("#notify-stale-min");
  if (!enabled || !stale) return;
  const ek = "notify_enabled";
  const sk = "notify_stale_min";
  const ck = "notify_cooldown_sec";
  const lk = "notify_last_alert";
  const ak = "openclaw_ui_notify_audit";
  const emitAudit = (type, result, reason = "", detail = "") => {
    let rows = [];
    try {
      rows = JSON.parse(localStorage.getItem(ak) || "[]");
    } catch {
      rows = [];
    }
    rows.push({
      ts: new Date().toISOString(),
      type,
      result,
      reason,
      detail,
    });
    if (rows.length > 200) rows = rows.slice(-200);
    localStorage.setItem(ak, JSON.stringify(rows));
    emitServerAudit({
      event_type: String(type || ""),
      result,
      reason,
      detail,
      action_id: "notification_rules",
    });
  };

  const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));
  enabled.checked = localStorage.getItem(ek) === "1";
  stale.value = String(clamp(Number(localStorage.getItem(sk) || stale.value || "15"), 5, 180));
  const cooldownSec = clamp(Number(localStorage.getItem(ck) || "60"), 15, 3600);
  localStorage.setItem(ck, String(cooldownSec));
  if (enabled.dataset.bound !== "1") {
    enabled.dataset.bound = "1";
    enabled.addEventListener("change", async () => {
      localStorage.setItem(ek, enabled.checked ? "1" : "0");
      emitAudit("UI_NOTIFY_RULE_UPDATED", "ok", "", `enabled=${enabled.checked ? "1" : "0"}`);
      if (enabled.checked && Notification && Notification.permission === "default") {
        await Notification.requestPermission();
        emitAudit("UI_NOTIFY_RULE_UPDATED", "ok", "", `permission=${Notification.permission}`);
      }
    });
  }
  if (stale.dataset.bound !== "1") {
    stale.dataset.bound = "1";
    stale.addEventListener("change", () => {
      const val = clamp(Number(stale.value || "15"), 5, 180);
      stale.value = String(val);
      localStorage.setItem(sk, String(val));
      emitAudit("UI_NOTIFY_RULE_UPDATED", "ok", "", `stale_min=${val}`);
    });
  }

  if (!enabled.checked) return;
  const threshold = clamp(Number(stale.value || "15"), 5, 180);
  const cooldownMs = clamp(Number(localStorage.getItem(ck) || "60"), 15, 3600) * 1000;
  const chips = document.querySelectorAll(".sla-chip[data-age-min]");
  let hottest = null;
  chips.forEach((chip) => {
    const age = Number(chip.dataset.ageMin);
    if (Number.isFinite(age) && age >= threshold) {
      const agent = chip.dataset.agent || "agent";
      if (!hottest || age > hottest.age) hottest = { agent, age };
    }
  });
  if (!hottest) {
    emitAudit("UI_NOTIFICATION_BLOCKED", "denied", "no_matching_rule");
    return;
  }
  const last = Number(localStorage.getItem(lk) || "0");
  if (Date.now() - last < cooldownMs) {
    emitAudit("UI_NOTIFICATION_BLOCKED", "denied", "cooldown_active");
    return;
  }
  if (!("Notification" in window)) {
    emitAudit("UI_NOTIFICATION_BLOCKED", "denied", "notification_unsupported");
    return;
  }
  if (Notification && Notification.permission === "granted") {
    new Notification("OpenClaw Alert", { body: `${hottest.agent} stale for ${hottest.age} minutes.` });
    localStorage.setItem(lk, String(Date.now()));
    emitAudit("UI_NOTIFICATION_SENT", "ok", "", `${hottest.agent}:${hottest.age}`);
  } else {
    emitAudit("UI_NOTIFICATION_BLOCKED", "denied", `permission_${Notification.permission || "unknown"}`);
  }
}

function setupGovernedHistoryFilters(scope = document) {
  const resultSel = scope.querySelector("#gov-filter-result") || document.querySelector("#gov-filter-result");
  const reasonSel = scope.querySelector("#gov-filter-reason") || document.querySelector("#gov-filter-reason");
  const table = scope.querySelector("#governed-history-table") || document.querySelector("#governed-history-table");
  if (!resultSel || !reasonSel || !table) return;

  const rk = "openclaw_governed_filter_result";
  const kk = "openclaw_governed_filter_reason";
  const apply = () => {
    const rv = (resultSel.value || "").trim();
    const kv = (reasonSel.value || "").trim();
    table.querySelectorAll("tbody tr[data-governed-result]").forEach((tr) => {
      const rowR = tr.dataset.governedResult || "";
      const rowK = tr.dataset.governedReason || "";
      const okR = !rv || rowR === rv;
      const okK = !kv || rowK === kv;
      tr.style.display = okR && okK ? "" : "none";
    });
  };

  if (resultSel.dataset.bound !== "1") {
    resultSel.dataset.bound = "1";
    resultSel.addEventListener("change", () => {
      localStorage.setItem(rk, resultSel.value || "");
      apply();
    });
  }
  if (reasonSel.dataset.bound !== "1") {
    reasonSel.dataset.bound = "1";
    reasonSel.addEventListener("change", () => {
      localStorage.setItem(kk, reasonSel.value || "");
      apply();
    });
  }

  const savedR = localStorage.getItem(rk) || "";
  const savedK = localStorage.getItem(kk) || "";
  if ([...resultSel.options].some((o) => o.value === savedR)) resultSel.value = savedR;
  if ([...reasonSel.options].some((o) => o.value === savedK)) reasonSel.value = savedK;
  apply();
}

function boot(scope = document) {
  const steps = [
    setupVisualStack,
    renderRingCharts,
    renderSparkline,
    renderStateMix,
    renderIcons,
    setupThemeToggle,
    setupTaskDrawer,
    setupCommandPalette,
    setupSavedViews,
    setupQuickActionAudit,
    renderAgentGraph,
    setupAlertActions,
    setupChangeViewer,
    setupNotificationRules,
    setupGovernedHistoryFilters,
  ];
  steps.forEach((fn) => {
    try {
      fn(scope);
    } catch (err) {
      console.error(`dashboard boot step failed: ${fn.name}`, err);
    }
  });
}

boot(document);
document.addEventListener("htmx:afterSwap", (evt) => {
  const target = evt.detail?.target;
  if (!target) return;
  boot(target);
});
