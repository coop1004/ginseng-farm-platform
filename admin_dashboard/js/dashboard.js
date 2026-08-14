let charts = {};
let map = null;
let mapMarkers = [];
let currentFarms = [];

const typeColors = {
  "병해": "#c62828",
  "해충": "#ef6c00",
  "생리장애": "#1565c0",
};

function fmtDate(d) {
  if (!d) return "-";
  return d;
}

function riskBadgeClass(level) {
  if (level === "높음") return "badge badge-high";
  if (level === "보통") return "badge badge-mid";
  return "badge badge-low";
}

function typeBadgeClass(type) {
  return `badge badge-type-${type}`;
}

function showToast(message, isError = false) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.remove("hidden", "error");
  if (isError) toast.classList.add("error");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => toast.classList.add("hidden"), 3200);
}

function setConnStatus(state, text) {
  const el = document.getElementById("connStatus");
  el.className = `conn-status conn-${state}`;
  el.textContent = text;
}

// ---------- Navigation ----------
function initNav() {
  const navItems = document.querySelectorAll(".nav-item");
  const titles = {
    overview: "종합 현황",
    map: "지역별 발생 지도",
    farms: "농가 모니터링",
    feed: "실시간 진단 피드",
    notifications: "처방 알림 이력",
  };
  navItems.forEach((item) => {
    item.addEventListener("click", (e) => {
      e.preventDefault();
      const section = item.dataset.section;
      navItems.forEach((i) => i.classList.remove("active"));
      item.classList.add("active");
      document.querySelectorAll(".section").forEach((s) => s.classList.add("hidden"));
      document.getElementById(section).classList.remove("hidden");
      document.getElementById("pageTitle").textContent = titles[section];
      if (section === "map" && map) {
        setTimeout(() => map.invalidateSize(), 100);
      }
    });
  });
}

// ---------- Overview ----------
function renderSummary(summary) {
  document.getElementById("statFarms").textContent = summary.total_farms;
  document.getElementById("statWorkLogs").textContent = summary.total_work_logs;
  document.getElementById("statDiagnoses").textContent = summary.total_diagnoses;
  const acc = summary.ai_vs_actual.accuracy_percent;
  document.getElementById("statAccuracy").textContent = acc !== null ? `${acc}%` : "데이터 부족";

  renderTypeChart(summary.diagnoses_by_type);
  renderMonthlyChart(summary.monthly_diagnoses);
  renderTopPestChart(summary.top_pests);
  renderAiAccuracyChart(summary.ai_vs_actual);
}

function renderTypeChart(byType) {
  const ctx = document.getElementById("typeChart");
  const labels = Object.keys(byType);
  const data = Object.values(byType);
  if (charts.type) charts.type.destroy();
  charts.type = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [
        {
          data,
          backgroundColor: labels.map((l) => typeColors[l] || "#999"),
          borderWidth: 0,
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } } },
    },
  });
}

function renderMonthlyChart(monthly) {
  const ctx = document.getElementById("monthlyChart");
  if (charts.monthly) charts.monthly.destroy();
  charts.monthly = new Chart(ctx, {
    type: "line",
    data: {
      labels: monthly.map((m) => m.month),
      datasets: [
        {
          label: "발생 건수",
          data: monthly.map((m) => m.count),
          borderColor: "#2e7d32",
          backgroundColor: "rgba(46,125,50,0.12)",
          fill: true,
          tension: 0.3,
          pointRadius: 3,
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
    },
  });
}

function renderTopPestChart(topPests) {
  const ctx = document.getElementById("topPestChart");
  if (charts.top) charts.top.destroy();
  charts.top = new Chart(ctx, {
    type: "bar",
    data: {
      labels: topPests.map((p) => p.name),
      datasets: [
        {
          label: "발생 건수",
          data: topPests.map((p) => p.count),
          backgroundColor: "#ef6c00",
          borderRadius: 6,
        },
      ],
    },
    options: {
      indexAxis: "y",
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
    },
  });
}

function renderAiAccuracyChart(aiVsActual) {
  const ctx = document.getElementById("aiAccuracyChart");
  if (charts.ai) charts.ai.destroy();
  const note = document.getElementById("aiAccuracyNote");
  if (aiVsActual.total_feedback === 0) {
    note.textContent = "아직 농가 확인 피드백 데이터가 없습니다.";
  } else {
    note.textContent = `총 ${aiVsActual.total_feedback}건의 농가 피드백 중 ${aiVsActual.correct}건 일치 (정확도 ${aiVsActual.accuracy_percent}%)`;
  }
  charts.ai = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["AI 예측 일치", "AI 예측 불일치"],
      datasets: [
        {
          data: [aiVsActual.correct, aiVsActual.incorrect],
          backgroundColor: ["#2e7d32", "#c62828"],
          borderWidth: 0,
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } } },
    },
  });
}

// ---------- Map & Regional stats ----------
function renderMap(regionalStats) {
  if (!map) {
    map = L.map("koreaMap").setView([36.35, 127.8], 7);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);
  }
  mapMarkers.forEach((m) => map.removeLayer(m));
  mapMarkers = [];

  regionalStats.forEach((r) => {
    if (r.latitude == null || r.longitude == null) return;
    const radius = 8 + Math.min(r.total, 20) * 2.2;
    const marker = L.circleMarker([r.latitude, r.longitude], {
      radius,
      fillColor: "#ef6c00",
      color: "#c25700",
      weight: 1.5,
      fillOpacity: 0.55,
    }).addTo(map);
    marker.bindPopup(
      `<b>${r.region}</b><br/>총 발생: ${r.total}건<br/>주요 병해충: ${r.top_issue || "-"}`
    );
    mapMarkers.push(marker);
  });
}

function renderRegionTable(regionalStats) {
  const tbody = document.querySelector("#regionTable tbody");
  tbody.innerHTML = "";
  regionalStats.forEach((r) => {
    const typeStr = Object.entries(r.by_type)
      .map(([t, c]) => `${t} ${c}`)
      .join(" · ");
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${r.region}</strong></td>
      <td>${r.total}건</td>
      <td>${r.top_issue || "-"}</td>
      <td>${typeStr}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ---------- Farms table ----------
function renderFarmsTable(farms) {
  currentFarms = farms;
  const tbody = document.querySelector("#farmsTable tbody");
  tbody.innerHTML = "";
  farms.forEach((f) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${f.farm_name}</strong></td>
      <td>${f.household_name || "-"}</td>
      <td>${f.region || "-"}</td>
      <td>${f.facility_type}</td>
      <td>${f.cultivation_year}년근</td>
      <td>${f.last_diagnosis ? `${f.last_diagnosis.name} <span class="${typeBadgeClass(f.last_diagnosis.type)}">${f.last_diagnosis.type}</span>` : "-"}</td>
      <td>${fmtDate(f.last_work_log_date)}</td>
      <td>${f.diagnosis_count_30d}건</td>
      <td><span class="${riskBadgeClass(f.risk_level)}">${f.risk_level}</span></td>
      <td><button class="btn btn-primary btn-sm" data-farm-id="${f.farm_id}" data-farm-name="${f.farm_name}">처방 알림</button></td>
    `;
    tbody.appendChild(tr);
  });

  tbody.querySelectorAll("button[data-farm-id]").forEach((btn) => {
    btn.addEventListener("click", () => openNotifyModal(btn.dataset.farmId, btn.dataset.farmName));
  });
}

// ---------- Feed ----------
function timeAgo(iso) {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "방금 전";
  if (mins < 60) return `${mins}분 전`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}시간 전`;
  return `${Math.floor(hrs / 24)}일 전`;
}

function renderFeed(feed) {
  const list = document.getElementById("feedList");
  list.innerHTML = "";
  if (feed.length === 0) {
    list.innerHTML = `<div class="feed-item">아직 등록된 진단 내역이 없습니다.</div>`;
    return;
  }
  feed.forEach((item) => {
    const div = document.createElement("div");
    div.className = "feed-item";
    div.innerHTML = `
      <div class="feed-dot" style="background:${typeColors[item.diagnosis_type] || "#999"}"></div>
      <div class="feed-main">
        <div class="feed-title">${item.farm_name || "농가"} · ${item.ai_disease_name || "진단 결과 없음"}</div>
        <div class="feed-sub">${item.region || "-"} · ${item.diagnosis_type} · 발생일 ${fmtDate(item.occurrence_date)}</div>
      </div>
      <div class="feed-confidence">${item.confidence != null ? Math.round(item.confidence * 100) + "%" : ""}</div>
      <div class="feed-time">${timeAgo(item.created_at)}</div>
    `;
    list.appendChild(div);
  });
}

// ---------- Notifications ----------
function renderNotifications(notifications) {
  const tbody = document.querySelector("#notificationsTable tbody");
  tbody.innerHTML = "";
  if (notifications.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5">발송된 알림이 없습니다.</td></tr>`;
    return;
  }
  notifications.forEach((n) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${new Date(n.created_at).toLocaleString("ko-KR")}</td>
      <td>${n.farm_name || "-"}</td>
      <td>${n.title}</td>
      <td>${n.recommended_product || "-"}</td>
      <td><span class="badge badge-low">${n.status}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

// ---------- Modal ----------
let modalFarmId = null;

function openNotifyModal(farmId, farmName) {
  modalFarmId = farmId;
  document.getElementById("modalFarmName").textContent = `대상 농가: ${farmName}`;
  document.getElementById("modalTitle").value = "";
  document.getElementById("modalProduct").value = "";
  document.getElementById("modalMessage").value = "";
  document.getElementById("notifyModal").classList.remove("hidden");
}

function closeNotifyModal() {
  document.getElementById("notifyModal").classList.add("hidden");
  modalFarmId = null;
}

async function submitNotify() {
  const title = document.getElementById("modalTitle").value.trim();
  const message = document.getElementById("modalMessage").value.trim();
  const product = document.getElementById("modalProduct").value.trim();
  if (!title || !message) {
    showToast("제목과 메시지를 입력해주세요.", true);
    return;
  }
  try {
    await Api.sendNotification({
      farm_id: Number(modalFarmId),
      title,
      message,
      recommended_product: product || null,
      sent_by: "관리자",
    });
    showToast("처방 알림이 전송되었습니다.");
    closeNotifyModal();
    loadNotifications();
  } catch (e) {
    showToast(e.message, true);
  }
}

// ---------- Load & bootstrap ----------
async function loadAll() {
  try {
    await Api.health();
    setConnStatus("ok", `연결됨: ${Api.getBaseUrl()}`);
  } catch (e) {
    setConnStatus("error", "서버 연결 실패 (백엔드 실행 여부 확인)");
    showToast("API 서버에 연결할 수 없습니다. 좌측 하단에서 주소를 확인하세요.", true);
    return;
  }

  try {
    const [summary, farms, regional, feed, notifications] = await Promise.all([
      Api.getStatsSummary(),
      Api.getFarmsOverview(),
      Api.getRegionalStats(),
      Api.getFeed(30),
      Api.getNotifications(),
    ]);
    renderSummary(summary);
    renderFarmsTable(farms);
    renderMap(regional);
    renderRegionTable(regional);
    renderFeed(feed);
    renderNotifications(notifications);
  } catch (e) {
    showToast(`데이터 로드 실패: ${e.message}`, true);
  }
}

function loadNotifications() {
  Api.getNotifications().then(renderNotifications).catch((e) => showToast(e.message, true));
}

function init() {
  document.getElementById("todayLabel").textContent = new Date().toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  });
  document.getElementById("apiBaseInput").value = Api.getBaseUrl();

  initNav();

  document.getElementById("refreshBtn").addEventListener("click", loadAll);
  document.getElementById("apiBaseSave").addEventListener("click", () => {
    const val = document.getElementById("apiBaseInput").value.trim();
    if (val) {
      Api.setBaseUrl(val);
      loadAll();
    }
  });
  document.getElementById("modalCancel").addEventListener("click", closeNotifyModal);
  document.getElementById("modalSend").addEventListener("click", submitNotify);
  document.getElementById("notifyModal").addEventListener("click", (e) => {
    if (e.target.id === "notifyModal") closeNotifyModal();
  });

  loadAll();
}

document.addEventListener("DOMContentLoaded", init);
