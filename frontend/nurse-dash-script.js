// ==============================
// Quack & Assess Nurse Dashboard
// ==============================

// Base URL of your FastAPI backend
const API_BASE = "http://127.0.0.1:8000";
const QUEUE_ENDPOINT = `${API_BASE}/api/queue`;
const ADMITTED_ENDPOINT = `${API_BASE}/api/queue/admitted`;
const PATIENTS_ENDPOINT = `${API_BASE}/api/patients`;

// Will hold whatever /api/queue returns
let currentQueue = [];
let selectedPatientId = null;

// ---------- Helpers ----------

// Convert numeric priority to label (RED/YELLOW/GREEN)
function priorityLabel(n) {
  const num = Number(n || 0);
  if (num >= 70) return "RED";
  if (num >= 40) return "YELLOW";
  return "GREEN";
}

function priorityClass(label) {
  if (label === "RED") return "status-pill status-red";
  if (label === "YELLOW") return "status-pill status-yellow";
  return "status-pill status-green";
}

function capitalize(str) {
  if (!str) return "";
  return str.charAt(0).toUpperCase() + str.slice(1);
}

function normalizeStatus(status) {
  return String(status || "waiting").trim().toLowerCase();
}

function getQueueCounts() {
  let waiting = 0;
  let admitted = 0;

  currentQueue.forEach((item) => {
    const status = normalizeStatus(item.triagePriority?.priorityStatus);
    if (status === "admitted") {
      admitted += 1;
    } else {
      waiting += 1;
    }
  });

  return { waiting, admitted, total: waiting + admitted };
}

// ---------- Rendering: Patient flow ----------

function renderPatientFlow() {
  const waitingCount = document.getElementById("waiting-count");
  const admittedCount = document.getElementById("admitted-count");
  const patientTotal = document.getElementById("patient-total");
  const donut = document.getElementById("patient-flow-donut");

  if (!waitingCount || !admittedCount || !patientTotal || !donut) {
    console.warn("Patient flow chart elements missing.");
    return;
  }

  const { waiting, admitted, total } = getQueueCounts();
  const waitingAngle = total ? Math.round((waiting / total) * 360) : 360;

  waitingCount.textContent = `(${waiting})`;
  admittedCount.textContent = `(${admitted})`;
  patientTotal.textContent = String(total);

  if (!total) {
    donut.style.background = "conic-gradient(var(--border-light) 0 360deg)";
    return;
  }

  donut.style.background = `conic-gradient(
    var(--waiting) 0deg ${waitingAngle}deg,
    var(--admitted) ${waitingAngle}deg 360deg
  )`;
}

// ---------- Rendering: Next 5 patients table ----------

function renderNextPatients() {
  const tbody = document.getElementById("next-patients-body");
  if (!tbody) {
    console.warn("Missing element #next-patients-body");
    return;
  }

  tbody.innerHTML = "";

  const topFive = currentQueue.slice(0, 5);

  topFive.forEach((item) => {
    const p = item.patient || {};
    const t = item.triagePriority || {};
    const numeric = item.numericPriority ?? t.priorityLevel ?? 0;

    const label = priorityLabel(numeric);
    const status = t.priorityStatus || "Waiting";

    const tr = document.createElement("tr");

    const nameTd = document.createElement("td");
    nameTd.textContent = `${p.firstName || ""} ${p.lastName || ""}`.trim();

    const waitTd = document.createElement("td");
    waitTd.textContent = "--";

    const priorityTd = document.createElement("td");
    const pill = document.createElement("span");
    pill.className = priorityClass(label);
    pill.textContent = label;
    priorityTd.appendChild(pill);

    const statusTd = document.createElement("td");
    statusTd.textContent = capitalize(status);

    const actionTd = document.createElement("td");
    const btn = document.createElement("button");
    btn.className = "btn-icon";
    btn.innerHTML = "&#x25B6;";
    btn.addEventListener("click", () => {
      showPatientDetails(p._id);
    });
    actionTd.appendChild(btn);

    tr.appendChild(nameTd);
    tr.appendChild(waitTd);
    tr.appendChild(priorityTd);
    tr.appendChild(statusTd);
    tr.appendChild(actionTd);

    tbody.appendChild(tr);
  });
}

// ---------- Rendering: Recent admits (left panel) ----------

function renderRecentAdmits() {
  const list = document.getElementById("recent-admits-list");
  if (!list) {
    console.warn("Missing element #recent-admits-list");
    return;
  }
  list.innerHTML = "";

  const items = currentQueue
    .filter((item) => normalizeStatus(item.triagePriority?.priorityStatus) === "admitted")
    .slice(0, 6);

  if (!items.length) {
    const li = document.createElement("li");
    li.textContent = "No recent admits.";
    list.appendChild(li);
    return;
  }

  items.forEach((item) => {
    const p = item.patient || {};
    const li = document.createElement("li");
    li.textContent = `${p.lastName || ""}, ${p.firstName || ""}`.trim();
    list.appendChild(li);
  });
}

// ---------- Rendering: Alerts (right panel) ----------

function addAlert(text, icon = "!") {
  const list = document.getElementById("alerts-list");
  if (!list) return;

  const li = document.createElement("li");
  li.className = "alert-item";

  const iconDiv = document.createElement("div");
  iconDiv.className = "alert-icon";
  iconDiv.textContent = icon;

  const textDiv = document.createElement("div");
  textDiv.className = "alert-text";
  textDiv.textContent = text;

  li.appendChild(iconDiv);
  li.appendChild(textDiv);
  list.appendChild(li);
}

function renderAlerts() {
  const list = document.getElementById("alerts-list");
  if (!list) {
    console.warn("Missing element #alerts-list");
    return;
  }
  list.innerHTML = "";

  currentQueue.forEach((item) => {
    const p = item.patient || {};
    const t = item.triagePriority || {};
    const numeric = item.numericPriority ?? t.priorityLevel ?? 0;
    const label = priorityLabel(numeric);

    if (label === "RED") {
      addAlert(
        `${p.firstName || ""} ${p.lastName || ""} is RED priority.`,
        "!"
      );
    }
  });

  if (!list.children.length) {
    addAlert("No critical alerts. You're all caught up.", "OK");
  }
}

// ---------- Rendering: Patient detail panel ----------

function clearPatientDetails() {
  const panelName = document.getElementById("detail-name");
  const panelDob = document.getElementById("detail-dob");
  const panelPhone = document.getElementById("detail-phone");
  const panelStatus = document.getElementById("detail-status");
  const panelNotes = document.getElementById("detail-notes");
  const admitBtn = document.getElementById("admit-patient-btn");
  const removeBtn = document.getElementById("remove-admitted-btn");

  if (
    !panelName || !panelDob || !panelPhone || !panelStatus || !panelNotes ||
    !admitBtn || !removeBtn
  ) {
    return;
  }

  panelName.textContent = "Select a patient";
  panelDob.textContent = "--";
  panelPhone.textContent = "--";
  panelStatus.textContent = "--";
  panelNotes.innerHTML = "";

  const li = document.createElement("li");
  li.textContent = "No notes yet.";
  panelNotes.appendChild(li);

  admitBtn.classList.add("hidden");
  removeBtn.classList.add("hidden");
}

function showPatientDetails(patientId) {
  const panelName = document.getElementById("detail-name");
  const panelDob = document.getElementById("detail-dob");
  const panelPhone = document.getElementById("detail-phone");
  const panelStatus = document.getElementById("detail-status");
  const panelNotes = document.getElementById("detail-notes");
  const admitBtn = document.getElementById("admit-patient-btn");
  const removeBtn = document.getElementById("remove-admitted-btn");

  if (
    !panelName || !panelDob || !panelPhone || !panelStatus || !panelNotes ||
    !admitBtn || !removeBtn
  ) {
    console.warn("Detail panel elements missing, skipping render.");
    return;
  }

  const entry = currentQueue.find(
    (item) => item.patient && item.patient._id === patientId
  );
  if (!entry) {
    console.warn("No patient found for id", patientId);
    return;
  }

  selectedPatientId = patientId;

  const p = entry.patient || {};
  const t = entry.triagePriority || {};
  const notes = entry.keyNotes || [];
  const status = normalizeStatus(t.priorityStatus);

  panelName.textContent = `${p.firstName || ""} ${p.lastName || ""}`.trim();
  panelDob.textContent = p.DOB || "--";
  panelPhone.textContent = p.phoneNumber || "--";
  panelStatus.textContent = t.priorityStatus || "--";

  panelNotes.innerHTML = "";
  if (!notes.length) {
    const li = document.createElement("li");
    li.textContent = "No notes yet.";
    panelNotes.appendChild(li);
  } else {
    notes.forEach((n) => {
      const li = document.createElement("li");
      li.textContent = n.noteText || "";
      panelNotes.appendChild(li);
    });
  }

  if (status === "admitted") {
    admitBtn.classList.add("hidden");
    removeBtn.classList.remove("hidden");
  } else {
    admitBtn.classList.remove("hidden");
    removeBtn.classList.add("hidden");
  }
}

async function admitSelectedPatient() {
  if (!selectedPatientId) {
    return;
  }

  const entry = currentQueue.find(
    (item) => item.patient && item.patient._id === selectedPatientId
  );

  if (!entry || normalizeStatus(entry.triagePriority?.priorityStatus) === "admitted") {
    return;
  }

  const nurseName = document.getElementById("nurse-name")?.textContent?.trim() || null;
  const priorityLevel = Number(
    entry.numericPriority ?? entry.triagePriority?.priorityLevel ?? 0
  );

  try {
    const res = await fetch(`${PATIENTS_ENDPOINT}/${selectedPatientId}/priority`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        priorityLevel,
        priorityStatus: "admitted",
        reason: "Admitted for treatment",
        assignedNurse: nurseName,
      }),
    });

    if (!res.ok) {
      console.error("Failed to admit patient:", res.status, await res.text());
      return;
    }

    await loadQueue();
  } catch (err) {
    console.error("Error admitting patient:", err);
  }
}

async function removeSelectedAdmittedPatient() {
  if (!selectedPatientId) {
    return;
  }

  const entry = currentQueue.find(
    (item) => item.patient && item.patient._id === selectedPatientId
  );

  if (!entry || normalizeStatus(entry.triagePriority?.priorityStatus) !== "admitted") {
    return;
  }

  try {
    const res = await fetch(`${ADMITTED_ENDPOINT}/${selectedPatientId}`, {
      method: "DELETE",
    });

    if (!res.ok) {
      console.error("Failed to remove admitted patient:", res.status, await res.text());
      return;
    }

    currentQueue = currentQueue.filter(
      (item) => !(item.patient && item.patient._id === selectedPatientId)
    );
    selectedPatientId = null;

    clearPatientDetails();
    renderPatientFlow();
    renderNextPatients();
    renderRecentAdmits();
    renderAlerts();
  } catch (err) {
    console.error("Error removing admitted patient:", err);
  }
}

// ---------- Fetch data from backend ----------

async function loadQueue() {
  try {
    console.log("Fetching queue from:", QUEUE_ENDPOINT);
    const res = await fetch(QUEUE_ENDPOINT);
    console.log("Status:", res.status);

    if (!res.ok) {
      console.error("Failed to load queue:", res.status, await res.text());
      return;
    }

    const data = await res.json();
    console.log("Queue data:", data);

    if (!Array.isArray(data)) {
      console.error("Queue response is not an array:", data);
      return;
    }

    currentQueue = data;

    renderPatientFlow();
    renderNextPatients();
    renderRecentAdmits();
    renderAlerts();

    if (selectedPatientId) {
      const selectedEntry = currentQueue.find(
        (item) => item.patient && item.patient._id === selectedPatientId
      );

      if (selectedEntry) {
        showPatientDetails(selectedPatientId);
      } else {
        selectedPatientId = null;
        clearPatientDetails();
      }
    }
  } catch (err) {
    console.error("Error fetching queue:", err);
  }
}

// ---------- Initialize on page load ----------

document.addEventListener("DOMContentLoaded", () => {
  const admitBtn = document.getElementById("admit-patient-btn");
  const removeBtn = document.getElementById("remove-admitted-btn");
  if (admitBtn) {
    admitBtn.addEventListener("click", admitSelectedPatient);
  }
  if (removeBtn) {
    removeBtn.addEventListener("click", removeSelectedAdmittedPatient);
  }

  clearPatientDetails();
  loadQueue();
});
