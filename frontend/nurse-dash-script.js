// ==============================
// Quack & Assess Nurse Dashboard
// Frontend for QuackHacks2026_Triage repo
// ==============================

// If you run `uvicorn api:app --reload` from the repo root,
// your backend will be at this base URL.
const API_BASE = "http://127.0.0.1:8000";
const QUEUE_ENDPOINT = `${API_BASE}/api/queue`;

// Global cache of queue items returned by sort_patients_by_priority()
let currentQueue = [];

// ------------------------------------------------
// Utility helpers
// ------------------------------------------------

/**
 * Convert numeric priority into triage color label.
 * 3+ -> RED, 2 -> YELLOW, else GREEN
 */
function priorityLabel(numeric) {
  const n = Number(numeric || 0);
  if (n >= 3) return "RED";
  if (n === 2) return "YELLOW";
  return "GREEN";
}

/**
 * Returns CSS class string for a priority pill.
 */
function priorityClass(label) {
  if (label === "RED") return "status-pill status-red";
  if (label === "YELLOW") return "status-pill status-yellow";
  return "status-pill status-green";
}

/**
 * Compute approximate wait time in minutes from triage.lastUpdated → now.
 */
function computeWaitMinutes(triage) {
  if (!triage || !triage.lastUpdated) return "-";
  const updatedAt = new Date(triage.lastUpdated);
  if (Number.isNaN(updatedAt.getTime())) return "-";
  const now = new Date();
  const diffMs = now - updatedAt;
  return Math.max(0, Math.round(diffMs / 60000));
}

/**
 * Capitalize the first character in a string.
 */
function capitalize(str) {
  if (!str) return "";
  return str.charAt(0).toUpperCase() + str.slice(1);
}

// ------------------------------------------------
// Rendering: Next 5 Patients (center table + chart counts)
// ------------------------------------------------

function renderNextPatients() {
  const tbody = document.getElementById("next-patients-body");
  const waitingCountEl = document.getElementById("waiting-count");
  const admittedCountEl = document.getElementById("admitted-count");

  tbody.innerHTML = "";

  let waitingCount = 0;
  let admittedCount = 0;

  const topFive = currentQueue.slice(0, 5);

  topFive.forEach((item) => {
    const patient = item.patient || {};
    const triage = item.triagePriority || {};
    const numericPriority =
      item.numericPriority ??
      Number(triage.priorityLevel || 0); // handled as int in backend

    const status = triage.priorityStatus || "waiting";
    if (status === "admitted") {
      admittedCount += 1;
    } else {
      waitingCount += 1;
    }

    const label = priorityLabel(numericPriority);
    const waitMinutes = computeWaitMinutes(triage);

    const tr = document.createElement("tr");

    // Name
    const nameTd = document.createElement("td");
    nameTd.textContent = `${patient.firstName || ""} ${
      patient.lastName || ""
    }`.trim();

    // Wait time
    const wtTd = document.createElement("td");
    wtTd.textContent = waitMinutes;

    // Priority pill (RED / YELLOW / GREEN)
    const priorityTd = document.createElement("td");
    const pill = document.createElement("span");
    pill.className = priorityClass(label);
    pill.textContent = label;
    priorityTd.appendChild(pill);

    // Status chip (Waiting / Admitted)
    const statusTd = document.createElement("td");
    const chip = document.createElement("span");
    chip.className =
      "status-chip " + (status === "admitted" ? "admitted" : "waiting");
    chip.textContent = capitalize(status);
    statusTd.appendChild(chip);

    // ▶ button to open detail panel
    const actionTd = document.createElement("td");
    const btn = document.createElement("button");
    btn.className = "btn-icon";
    btn.innerHTML = "&#x25B6;"; // ▶
    btn.addEventListener("click", () => showPatientDetails(patient._id));
    actionTd.appendChild(btn);

    tr.appendChild(nameTd);
    tr.appendChild(wtTd);
    tr.appendChild(priorityTd);
    tr.appendChild(statusTd);
    tr.appendChild(actionTd);

    tbody.appendChild(tr);
  });

  waitingCountEl.textContent = `(${waitingCount})`;
  admittedCountEl.textContent = `(${admittedCount})`;
}

// ------------------------------------------------
// Rendering: Recent Admits (left sidebar)
// ------------------------------------------------

function renderRecentAdmits() {
  const list = document.getElementById("recent-admits-list");
  list.innerHTML = "";

  // For hackathon v1: just take top 6 in sorted queue.
  const items = currentQueue.slice(0, 6);

  if (!items.length) {
    const li = document.createElement("li");
    li.className = "list-item";
    li.textContent = "No recent admits.";
    list.appendChild(li);
    return;
  }

  items.forEach((item) => {
    const p = item.patient || {};
    const li = document.createElement("li");
    li.className = "list-item";
    li.textContent = `${p.lastName || ""}, ${p.firstName || ""}`.trim();
    list.appendChild(li);
  });
}

// ------------------------------------------------
// Rendering: Alerts (right sidebar)
// ------------------------------------------------

function addAlert(list, iconText, text) {
  const li = document.createElement("li");
  li.className = "alert-item";

  const icon = document.createElement("div");
  icon.className = "alert-icon";
  icon.textContent = iconText;

  const body = document.createElement("div");
  body.className = "alert-text";
  body.textContent = text;

  li.appendChild(icon);
  li.appendChild(body);
  list.appendChild(li);
}

function renderAlerts() {
  const list = document.getElementById("alerts-list");
  list.innerHTML = "";

  currentQueue.forEach((item) => {
    const patient = item.patient || {};
    const triage = item.triagePriority || {};
    const numericPriority =
      item.numericPriority ??
      Number(triage.priorityLevel || 0);

    const label = priorityLabel(numericPriority);
    const waitMin = computeWaitMinutes(triage);
    const fullName = `${patient.firstName || ""} ${
      patient.lastName || ""
    }`.trim();

    if (label === "RED") {
      addAlert(list, "!", `${fullName} is RED priority.`);
    }

    if (
      waitMin !== "-" &&
      waitMin >= 15 &&
      triage.priorityStatus !== "admitted"
    ) {
      addAlert(list, "⏱", `${fullName} has been waiting ${waitMin} minutes.`);
    }
  });

  if (!list.children.length) {
    addAlert(list, "✓", "No critical alerts. You're all caught up!");
  }
}

// ------------------------------------------------
// Rendering: Patient Details panel
// ------------------------------------------------

function showPatientDetails(patientId) {
  const detail = currentQueue.find(
    (item) => item.patient && item.patient._id === patientId
  );
  if (!detail) return;

  const p = detail.patient || {};
  const triage = detail.triagePriority || {};
  const notes = detail.keyNotes || [];

  // Basic identifiers
  document.getElementById("detail-name").textContent =
    `${p.firstName || ""} ${p.lastName || ""}`.trim() || "Unknown";
  document.getElementById("detail-dob").textContent = p.DOB || "—";
  document.getElementById("detail-phone").textContent = p.phoneNumber || "—";
  document.getElementById("detail-status").textContent = triage.priorityStatus
    ? capitalize(triage.priorityStatus)
    : "—";

  // Notes
  const notesList = document.getElementById("detail-notes");
  notesList.innerHTML = "";

  if (!notes.length) {
    const li = document.createElement("li");
    li.textContent = "No notes yet.";
    notesList.appendChild(li);
  } else {
    notes.forEach((n) => {
      const li = document.createElement("li");
      li.textContent = n.noteText || "";
      notesList.appendChild(li);
    });
  }

  // Full view (future enhancement – for now just logs)
  const fullBtn = document.getElementById("full-view-btn");
  fullBtn.onclick = () => {
    console.log("Open full view for patient:", patientId);
    // example for later:
    // window.location.href = `/patient.html?id=${encodeURIComponent(patientId)}`;
  };
}

// ------------------------------------------------
// Data fetching from FastAPI
// ------------------------------------------------

async function loadQueue() {
  try {
    const res = await fetch(QUEUE_ENDPOINT);
    if (!res.ok) {
      console.error("Failed to load triage queue:", res.status, res.statusText);
      return;
    }

    const data = await res.json();

    if (!Array.isArray(data)) {
      console.error("Unexpected queue response format:", data);
      return;
    }

    // Each item is { patient, keyNotes, triagePriority, numericPriority }
    currentQueue = data;

    renderNextPatients();
    renderRecentAdmits();
    renderAlerts();
  } catch (err) {
    console.error("Error fetching triage queue:", err);
  }
}

// ------------------------------------------------
// Init
// ------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
  loadQueue();

  // Optional: auto-refresh every 30s at the nurse station
  // setInterval(loadQueue, 30000);
});