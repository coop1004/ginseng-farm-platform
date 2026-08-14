let charts = {};
let map = null;
let mapMarkers = [];
let currentFarms = [];
let currentHouseholds = [];

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
  document.getElementById("statHouseholds").textContent = summary.total_households ?? "-";
  document.getElementById("statFarmsSub").textContent =
    summary.total_farms != null ? `· 농장 ${summary.total_farms}개` : "";
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

// ---------- Farms / Households ----------

// 농장(필지) 목록을 농가 단위로 집계한다. 농가와 농장이 많아져도 목록 화면은
// 농가 수만큼만 보여주고, 개별 농장은 클릭해서 들어간 상세 화면에서 본다.
function aggregateHouseholds(farms) {
  const map = new Map();
  farms.forEach((f) => {
    if (!map.has(f.household_id)) {
      map.set(f.household_id, {
        household_id: f.household_id,
        household_name: f.household_name || "-",
        farm_count: 0,
        regions: new Set(),
        diagnosis_count_30d: 0,
        last_diagnosis: null,
        last_work_log_date: null,
      });
    }
    const h = map.get(f.household_id);
    h.farm_count += 1;
    if (f.region) h.regions.add(f.region);
    h.diagnosis_count_30d += f.diagnosis_count_30d;
    if (f.last_diagnosis && (!h.last_diagnosis || f.last_diagnosis.date > h.last_diagnosis.date)) {
      h.last_diagnosis = f.last_diagnosis;
    }
    if (f.last_work_log_date && (!h.last_work_log_date || f.last_work_log_date > h.last_work_log_date)) {
      h.last_work_log_date = f.last_work_log_date;
    }
  });

  const result = Array.from(map.values()).map((h) => ({
    ...h,
    regions: Array.from(h.regions),
    risk_level: h.diagnosis_count_30d >= 3 ? "높음" : h.diagnosis_count_30d >= 1 ? "보통" : "낮음",
  }));
  result.sort((a, b) => b.diagnosis_count_30d - a.diagnosis_count_30d);
  return result;
}

function renderHouseholdsTable(farms) {
  currentFarms = farms;
  currentHouseholds = aggregateHouseholds(farms);
  backToHouseholdList();

  const tbody = document.querySelector("#householdsTable tbody");
  tbody.innerHTML = "";
  currentHouseholds.forEach((h) => {
    const tr = document.createElement("tr");
    tr.className = "clickable-row";
    tr.innerHTML = `
      <td><strong>${h.household_name}</strong></td>
      <td>${h.farm_count}개</td>
      <td>${h.regions.join(", ") || "-"}</td>
      <td>${h.last_diagnosis ? `${h.last_diagnosis.name} <span class="${typeBadgeClass(h.last_diagnosis.type)}">${h.last_diagnosis.type}</span>` : "-"}</td>
      <td>${fmtDate(h.last_work_log_date)}</td>
      <td>${h.diagnosis_count_30d}건</td>
      <td><span class="${riskBadgeClass(h.risk_level)}">${h.risk_level}</span></td>
    `;
    tr.addEventListener("click", () => showHouseholdDetail(h.household_id));
    tbody.appendChild(tr);
  });
}

function showHouseholdDetail(householdId) {
  const household = currentHouseholds.find((h) => h.household_id === householdId);
  if (!household) return;

  document.getElementById("householdListPanel").classList.add("hidden");
  document.getElementById("householdDetailPanel").classList.remove("hidden");
  document.getElementById("householdDetailTitle").textContent = `${household.household_name} · 농장 목록`;

  const farms = currentFarms.filter((f) => f.household_id === householdId);
  const tbody = document.querySelector("#householdFarmsTable tbody");
  tbody.innerHTML = "";
  farms.forEach((f) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${f.farm_name}</strong></td>
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

function backToHouseholdList() {
  document.getElementById("householdDetailPanel").classList.add("hidden");
  document.getElementById("householdListPanel").classList.remove("hidden");
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
    if (e.isAuthError) {
      closeNotifyModal();
      showLoginScreen();
      return;
    }
    showToast(e.message, true);
  }
}

// ---------- Auth ----------
function showLoginScreen() {
  document.getElementById("loginScreen").classList.remove("hidden");
  document.getElementById("appShell").classList.add("hidden");
}

function showAppShell() {
  document.getElementById("loginScreen").classList.add("hidden");
  document.getElementById("appShell").classList.remove("hidden");
}

async function handleLoginSubmit(e) {
  e.preventDefault();
  const username = document.getElementById("loginUsername").value.trim();
  const password = document.getElementById("loginPassword").value;
  const errorBox = document.getElementById("loginError");
  errorBox.classList.add("hidden");
  if (!username || !password) return;

  try {
    const resp = await Api.login(username, password);
    Api.setToken(resp.access_token);
    showAppShell();
    loadAll();
  } catch (err) {
    errorBox.textContent = "아이디 또는 비밀번호가 올바르지 않습니다.";
    errorBox.classList.remove("hidden");
  }
}

function handleLogout() {
  Api.setToken(null);
  showLoginScreen();
  document.getElementById("loginPassword").value = "";
}

// ---------- Account management ----------
async function openAccountModal() {
  document.getElementById("pwCurrent").value = "";
  document.getElementById("pwNew").value = "";
  document.getElementById("adminNewName").value = "";
  document.getElementById("adminNewUsername").value = "";
  document.getElementById("adminNewPassword").value = "";
  document.getElementById("accountModal").classList.remove("hidden");
  try {
    const me = await Api.getMe();
    document.getElementById("accountMeLabel").textContent = `현재 로그인: ${me.name} (${me.username})`;
  } catch (e) {
    // 조회 실패해도 모달 자체는 그대로 사용 가능하도록 무시
  }
  loadAdminList();
}

function closeAccountModal() {
  document.getElementById("accountModal").classList.add("hidden");
}

function loadAdminList() {
  Api.listAdmins()
    .then((admins) => {
      const ul = document.getElementById("adminListUl");
      ul.innerHTML = "";
      admins.forEach((a) => {
        const li = document.createElement("li");
        li.textContent = `${a.name} (${a.username})`;
        ul.appendChild(li);
      });
    })
    .catch(() => {});
}

async function submitChangePassword() {
  const current = document.getElementById("pwCurrent").value;
  const next = document.getElementById("pwNew").value;
  if (!current || !next) {
    showToast("현재 비밀번호와 새 비밀번호를 모두 입력해주세요.", true);
    return;
  }
  if (next.length < 8) {
    showToast("새 비밀번호는 8자 이상이어야 합니다.", true);
    return;
  }
  try {
    await Api.changePassword(current, next);
    showToast("비밀번호가 변경되었습니다.");
    document.getElementById("pwCurrent").value = "";
    document.getElementById("pwNew").value = "";
  } catch (e) {
    if (e.isAuthError) {
      closeAccountModal();
      showLoginScreen();
      return;
    }
    showToast(e.message, true);
  }
}

async function submitAddAdmin() {
  const name = document.getElementById("adminNewName").value.trim();
  const username = document.getElementById("adminNewUsername").value.trim();
  const password = document.getElementById("adminNewPassword").value;
  if (!name || !username || !password) {
    showToast("이름, 아이디, 초기 비밀번호를 모두 입력해주세요.", true);
    return;
  }
  if (password.length < 8) {
    showToast("초기 비밀번호는 8자 이상이어야 합니다.", true);
    return;
  }
  try {
    await Api.registerAdmin(username, password, name);
    showToast(`${name} 관리자 계정이 추가되었습니다.`);
    document.getElementById("adminNewName").value = "";
    document.getElementById("adminNewUsername").value = "";
    document.getElementById("adminNewPassword").value = "";
    loadAdminList();
  } catch (e) {
    if (e.isAuthError) {
      closeAccountModal();
      showLoginScreen();
      return;
    }
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
    renderHouseholdsTable(farms);
    renderMap(regional);
    renderRegionTable(regional);
    renderFeed(feed);
    renderNotifications(notifications);
  } catch (e) {
    if (e.isAuthError) {
      showLoginScreen();
      return;
    }
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

  document.getElementById("backToHouseholds").addEventListener("click", backToHouseholdList);
  document.getElementById("statFarmsCard").addEventListener("click", () => {
    document.querySelector('.nav-item[data-section="farms"]').click();
  });

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

  document.getElementById("loginForm").addEventListener("submit", handleLoginSubmit);
  document.getElementById("logoutBtn").addEventListener("click", handleLogout);

  document.getElementById("accountBtn").addEventListener("click", openAccountModal);
  document.getElementById("accountClose").addEventListener("click", closeAccountModal);
  document.getElementById("accountModal").addEventListener("click", (e) => {
    if (e.target.id === "accountModal") closeAccountModal();
  });
  document.getElementById("pwSubmit").addEventListener("click", submitChangePassword);
  document.getElementById("adminAddSubmit").addEventListener("click", submitAddAdmin);

  if (Api.isLoggedIn()) {
    showAppShell();
    loadAll();
  } else {
    showLoginScreen();
  }
}

document.addEventListener("DOMContentLoaded", init);
