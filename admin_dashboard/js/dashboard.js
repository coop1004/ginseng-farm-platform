let charts = {};
let map = null;
let mapMarkers = [];
// currentFarms는 기상 데이터 화면의 농장 선택과 처방알림 브로드캐스트의 농장 직접선택
// 체크리스트가 쓰는 "항상 전체 품목" 목록이다 - 농가 모니터링 화면의 품목 필터와는
// 의도적으로 분리한다(이번 작업 범위가 농가 모니터링/실시간 피드로 한정되어 있어서,
// 대시보드에서 고른 품목 필터가 알림 발송 대상 같은 다른 기능에 조용히 영향을 주면 안 됨).
let currentFarms = [];
// 농가 모니터링 화면(목록 + 농가 상세 드릴다운) 전용 - 품목 필터가 적용된 농장 목록.
let currentHouseholdScreenFarms = [];
let currentHouseholds = [];

// ---------- 공용 품목(작물) 선택 상태 ----------
// 종합현황/지역별발생현황/컨설턴트 활동현황/농가 참여도현황/병해충 사진 관리가 전부 이 값
// 하나를 공유한다 - 화면(탭)을 옮겨도, 새로고침해도 마지막 선택이 유지되도록 localStorage에
// 저장한다. localStorage에 값이 아예 없는 최초 방문에만 "인삼"을 기본값으로 맞추고,
// 사용자가 명시적으로 "전체"(빈 문자열)를 고른 뒤에는 그 선택을 그대로 존중한다
// (getItem이 null이면 "한 번도 고른 적 없음", ""이면 "전체를 명시적으로 골랐음"으로 구분).
const CROP_STORAGE_KEY = "adminSelectedCropId";
const _storedCropId = localStorage.getItem(CROP_STORAGE_KEY);
let globalSelectedCropId = _storedCropId || "";
let globalCropDefaultResolved = _storedCropId !== null;

function getSelectedCropId() {
  return globalSelectedCropId;
}

function setSelectedCropId(value) {
  globalSelectedCropId = value || "";
  localStorage.setItem(CROP_STORAGE_KEY, globalSelectedCropId);
  document.querySelectorAll(".crop-select-global").forEach((sel) => {
    if (sel.value !== globalSelectedCropId) sel.value = globalSelectedCropId;
  });
}

function ensureCropDefault(crops) {
  if (globalCropDefaultResolved) return;
  globalCropDefaultResolved = true;
  const ginseng = crops.find((c) => c.name_kr === "인삼");
  if (ginseng) {
    globalSelectedCropId = String(ginseng.id);
    localStorage.setItem(CROP_STORAGE_KEY, globalSelectedCropId);
  }
}

// 화면마다 있는 품목 선택 <select> 하나를 공용 상태로 채운다. 실제 데이터 재조회(reload)는
// 호출부에서 change 리스너로 직접 트리거한다 - 이 함수는 select의 옵션/선택값만 맞춘다.
function populateCropSelect(selectEl) {
  return ensureCropsLoaded().then((crops) => {
    ensureCropDefault(crops);
    selectEl.classList.add("crop-select-global");
    selectEl.innerHTML =
      `<option value="">전체</option>` +
      crops.map((c) => `<option value="${c.id}">${c.icon_emoji || ""} ${c.name_kr}</option>`).join("");
    selectEl.value = globalSelectedCropId;
    return crops;
  });
}

// "바탕화면에 바로가기" — 크롬/엣지/안드로이드는 이 이벤트를 잡아뒀다가 버튼 클릭 시
// prompt()로 설치창을 띄운다. 이벤트가 오기 전에 버튼을 누르면(iOS Safari처럼 이
// 이벤트 자체가 없는 브라우저 포함) 수동 설치 방법을 안내한다.
let deferredInstallPrompt = null;
window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  deferredInstallPrompt = e;
});

async function handleInstallClick() {
  if (deferredInstallPrompt) {
    deferredInstallPrompt.prompt();
    await deferredInstallPrompt.userChoice;
    deferredInstallPrompt = null;
    return;
  }
  const ua = navigator.userAgent;
  const isIOS = /iphone|ipad|ipod/i.test(ua);
  const msg = isIOS
    ? 'Safari 하단(또는 상단) 공유 아이콘을 누른 뒤 "홈 화면에 추가"를 선택해주세요.'
    : '이미 설치되어 있거나, 이 브라우저는 자동 설치를 지원하지 않습니다. 크롬이라면 주소창 오른쪽의 설치 아이콘(⊕) 또는 우측 상단 메뉴(⋮) → "앱 설치"를 확인해주세요.';
  alert(msg);
}

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
    participation: "농가 참여도 현황",
    feed: "실시간 진단 피드",
    photos: "병해충 사진 관리",
    weather: "기상 데이터",
    reference: "병해충·자재 자료",
    notifications: "처방 알림 이력",
    "consultant-activity": "컨설턴트 활동현황",
    community: "커뮤니티 신고 검수",
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
      // 화면(탭)을 옮겨도 공용 품목 선택이 유지되므로, 다시 들어올 때마다 그 화면의
      // 데이터를 지금 선택된 품목 기준으로 다시 불러온다 - 그래야 다른 화면에서 품목을
      // 바꾼 뒤 이 화면으로 돌아왔을 때도(select 표시값만 바뀌고 실제 데이터는 그대로인)
      // 불일치가 생기지 않는다.
      if (section === "overview") {
        reloadStatsSummary();
        loadConsultantActivitySummary();
      }
      if (section === "map") {
        loadRegionalStats(currentRegionalCropFilterValue());
      }
      if (section === "map" && map) {
        setTimeout(() => map.invalidateSize(), 100);
      }
      if (section === "map" && charts.regionCrop) {
        setTimeout(() => charts.regionCrop.resize(), 100);
      }
      if (section === "weather" && charts.weather) {
        setTimeout(() => charts.weather.resize(), 100);
      }
      if (section === "community") {
        loadCommunityReports();
      }
      if (section === "participation") {
        loadParticipationOrganizations().then(loadParticipationPage);
      }
      if (section === "consultant-activity") {
        loadConsultantActivityPage();
      }
      if (section === "photos") {
        loadPhotosDiagnoses();
      }
      if (section === "farms") {
        loadHouseholdsScreen();
      }
      if (section === "feed") {
        loadFeedScreen();
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

  const wr = summary.weather_reliability;
  if (wr) {
    document.getElementById("statWeatherReal").textContent = wr.real_count;
    document.getElementById("statWeatherFallback").textContent = wr.current_fallback_count;
    document.getElementById("statWeatherDemo").textContent = wr.demo_count + wr.unavailable_count;
    document.getElementById("statWeatherNote").textContent =
      wr.total_diagnoses > 0
        ? `전체 진단 ${wr.total_diagnoses}건 중 실측 날씨는 ${wr.real_count}건입니다. (위치 정보 없어 미기록 ${wr.unavailable_count}건 포함)`
        : "아직 진단 기록이 없습니다.";
  }

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
      `<b>${r.region}</b><br/>총 발생: ${r.total_display}<br/>주요 병해충: ${r.top_issue || "-"}<br/><a href="#" data-region-drilldown="${r.region}">병해충류별 보기 →</a>`
    );
    marker.on("popupopen", () => {
      const link = document.querySelector(`[data-region-drilldown="${CSS.escape(r.region)}"]`);
      if (link) {
        link.addEventListener("click", (e) => {
          e.preventDefault();
          openRegionBreakdownModal(r.region);
        });
      }
    });
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
    const cropStr = Object.entries(r.by_crop || {})
      .map(([c, n]) => `${c} ${n}`)
      .join(" · ");
    const tr = document.createElement("tr");
    tr.className = "clickable-row";
    tr.innerHTML = `
      <td><strong>${r.region}</strong></td>
      <td>${r.total_display}</td>
      <td>${r.top_issue || "-"}</td>
      <td>${typeStr}</td>
      <td>${cropStr || "-"}</td>
    `;
    tr.addEventListener("click", () => openRegionBreakdownModal(r.region));
    tbody.appendChild(tr);
  });
}

const cropChartColors = {
  "인삼": "#2e7d32",
  "고추": "#c62828",
  "배추": "#1565c0",
};

function renderRegionCropChart(regionalStats) {
  const ctx = document.getElementById("regionCropChart");
  const regions = regionalStats.map((r) => r.region);
  const crops = [...new Set(regionalStats.flatMap((r) => Object.keys(r.by_crop || {})))].sort();

  const datasets = crops.map((crop) => ({
    label: crop,
    data: regionalStats.map((r) => (r.by_crop || {})[crop] || 0),
    backgroundColor: cropChartColors[crop] || "#8d6e63",
    borderRadius: 5,
  }));

  if (charts.regionCrop) charts.regionCrop.destroy();
  charts.regionCrop = new Chart(ctx, {
    type: "bar",
    data: { labels: regions, datasets },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } } },
      scales: {
        x: { stacked: false },
        y: { beginAtZero: true, ticks: { precision: 0 } },
      },
    },
  });
}

// 지역별 발생 지도/차트/표를 특정 작물로 좁혀서 다시 불러온다. cropId가 falsy면(전체 작물
// 선택) 필터 없이 전체를 보여준다 - 기존 동작과 동일.
// 종합현황/지역별발생현황 화면 전용 기간 필터 상태. 컨설턴트 활동현황(consultantActivityState)과
// 같은 패턴이지만, 기본값이 "all"(전체 기간)이라 필터를 건드리지 않으면 이번 작업 이전과
// 동일한 화면이 나온다(회귀 없음). 지역x병해충류 증감 추이(regional-stats/breakdown)는 이
// 상태와 무관하게 항상 최근 7일 고정으로 별도 동작한다.
let statsSummaryPeriodState = { period: "all", startDate: null, endDate: null };
let regionalStatsPeriodState = { period: "all", startDate: null, endDate: null };

function loadRegionalStats(cropId) {
  const { period, startDate, endDate } = regionalStatsPeriodState;
  return Api.getRegionalStats(cropId || undefined, { period, startDate, endDate })
    .then((regional) => {
      renderMap(regional);
      renderRegionTable(regional);
      renderRegionCropChart(regional);
    })
    .catch((e) => showToast(`지역 통계 로드 실패: ${e.message}`, true));
}

function currentRegionalCropFilterValue() {
  const select = document.getElementById("regionalCropFilter");
  return select ? select.value : "";
}

function reloadStatsSummary() {
  const { period, startDate, endDate } = statsSummaryPeriodState;
  return Api.getStatsSummary({ period, startDate, endDate, cropId: getSelectedCropId() })
    .then(renderSummary)
    .catch((e) => showToast(`종합 현황 로드 실패: ${e.message}`, true));
}

// ---------- 지역 발생 현황 드릴다운: 지역 -> 병해충류별(+증감) -> 진단 목록 -> 상세/알림 ----------
let regionBreakdownContext = { region: null, pestName: null };

function trendBadgeHtml(item) {
  if (item.suppressed || item.trend_direction == null) return "-";
  if (item.trend_direction === "up") return `<span class="trend-badge trend-up">▲ 증가(+${item.change})</span>`;
  if (item.trend_direction === "down") return `<span class="trend-badge trend-down">▼ 감소(${item.change})</span>`;
  return `<span class="trend-badge trend-flat">- 변동없음</span>`;
}

function openRegionBreakdownModal(region) {
  regionBreakdownContext = { region, pestName: null };
  document.getElementById("regionBreakdownTitle").textContent = `${region} · 병해충류별 발생 현황`;
  document.getElementById("regionBreakdownListView").classList.remove("hidden");
  document.getElementById("regionBreakdownDiagnosisView").classList.add("hidden");
  document.getElementById("regionBreakdownModal").classList.remove("hidden");
  loadRegionBreakdownList(region);
}

function closeRegionBreakdownModal() {
  document.getElementById("regionBreakdownModal").classList.add("hidden");
}

function loadRegionBreakdownList(region) {
  const tbody = document.querySelector("#regionBreakdownTable tbody");
  tbody.innerHTML = `<tr><td colspan="4">불러오는 중…</td></tr>`;
  Api.getRegionalBreakdown(region, getSelectedCropId())
    .then((items) => {
      if (items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4">발생 기록이 없습니다.</td></tr>`;
        return;
      }
      tbody.innerHTML = "";
      items.forEach((item) => {
        const tr = document.createElement("tr");
        tr.className = "clickable-row";
        tr.innerHTML = `
          <td><strong>${item.name}</strong></td>
          <td><span class="${typeBadgeClass(item.diagnosis_type)}">${item.diagnosis_type}</span></td>
          <td>${item.total_display}</td>
          <td>${trendBadgeHtml(item)}</td>
        `;
        tr.addEventListener("click", () => openRegionBreakdownDiagnosisList(region, item.name));
        tbody.appendChild(tr);
      });
    })
    .catch((e) => {
      if (e.isAuthError) {
        closeRegionBreakdownModal();
        showLoginScreen();
        return;
      }
      tbody.innerHTML = `<tr><td colspan="4">불러오지 못했습니다: ${e.message}</td></tr>`;
    });
}

function openRegionBreakdownDiagnosisList(region, pestName) {
  regionBreakdownContext = { region, pestName };
  document.getElementById("regionBreakdownListView").classList.add("hidden");
  document.getElementById("regionBreakdownDiagnosisView").classList.remove("hidden");
  document.getElementById("regionBreakdownDiagnosisSub").textContent = `${region} · ${pestName}`;

  const tbody = document.querySelector("#regionBreakdownDiagnosisTable tbody");
  tbody.innerHTML = `<tr><td colspan="4">불러오는 중…</td></tr>`;
  Api.getAdminDiagnoses({ region, pest_name: pestName, crop_id: getSelectedCropId() })
    .then((list) => {
      if (list.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4">진단 기록이 없습니다.</td></tr>`;
        return;
      }
      tbody.innerHTML = "";
      list.forEach((d) => {
        const tr = document.createElement("tr");
        tr.className = "clickable-row";
        tr.innerHTML = `
          <td>${d.household_name || "-"}</td>
          <td>${d.farm_name || "-"}</td>
          <td>${fmtDate(d.occurrence_date)}</td>
          <td><span class="${typeBadgeClass(d.diagnosis_type)}">${d.diagnosis_type}</span></td>
        `;
        tr.addEventListener("click", () => openDiagnosisDetailModal(d.id));
        tbody.appendChild(tr);
      });
    })
    .catch((e) => {
      if (e.isAuthError) {
        closeRegionBreakdownModal();
        showLoginScreen();
        return;
      }
      tbody.innerHTML = `<tr><td colspan="4">불러오지 못했습니다: ${e.message}</td></tr>`;
    });
}

function backToRegionBreakdownList() {
  document.getElementById("regionBreakdownDiagnosisView").classList.add("hidden");
  document.getElementById("regionBreakdownListView").classList.remove("hidden");
}

function notifyFromRegionBreakdown() {
  const { region, pestName } = regionBreakdownContext;
  if (!region) return;
  closeRegionBreakdownModal();
  openBroadcastModal({
    region,
    title: pestName ? `${pestName} 예찰·방제 안내` : `${region} 병해충 예찰 안내`,
    message: pestName
      ? `[${region}] 최근 ${pestName} 발생이 확인되고 있습니다. 예찰 및 방제에 참고 부탁드립니다.`
      : `[${region}] 병해충 예찰 정보를 안내드립니다.`,
  });
}

function populateRegionalCropFilter() {
  return populateCropSelect(document.getElementById("regionalCropFilter"));
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
        household_status: f.household_status || "active",
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

function householdStatusBadgeHtml(status) {
  if (status === "withdrawn") return ' <span class="status-badge status-탈퇴">탈퇴</span>';
  if (status === "suspended") return ' <span class="status-badge status-정지">정지</span>';
  return "";
}

function renderHouseholdsTable(farms) {
  currentHouseholdScreenFarms = farms;
  currentHouseholds = aggregateHouseholds(farms);
  backToHouseholdList();

  const tbody = document.querySelector("#householdsTable tbody");
  tbody.innerHTML = "";
  currentHouseholds.forEach((h) => {
    const tr = document.createElement("tr");
    tr.className = "clickable-row";
    tr.innerHTML = `
      <td><strong>${h.household_name}</strong>${householdStatusBadgeHtml(h.household_status)}</td>
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

function loadHouseholdsScreen() {
  return Api.getFarmsOverview(getSelectedCropId())
    .then(renderHouseholdsTable)
    .catch((e) => {
      if (e.isAuthError) {
        showLoginScreen();
        return;
      }
      showToast(`농가 모니터링을 불러오지 못했습니다: ${e.message}`, true);
    });
}

function showHouseholdDetail(householdId) {
  const household = currentHouseholds.find((h) => h.household_id === householdId);
  if (!household) return;

  document.getElementById("householdListPanel").classList.add("hidden");
  document.getElementById("householdDetailPanel").classList.remove("hidden");
  document.getElementById("householdDetailTitle").textContent = `${household.household_name} · 농장 목록`;

  renderHouseholdAccountInfo(householdId);
  renderHouseholdCrops(householdId);
  renderHouseholdConsultants(householdId, household.household_status);

  const farms = currentHouseholdScreenFarms.filter((f) => f.household_id === householdId);
  const tbody = document.querySelector("#householdFarmsTable tbody");
  tbody.innerHTML = "";
  farms.forEach((f) => {
    const tr = document.createElement("tr");
    if (f.last_diagnosis) tr.className = "household-farm-row-clickable";
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
    if (f.last_diagnosis) {
      tr.addEventListener("click", (e) => {
        if (e.target.closest("button")) return;
        openDiagnosisDetailModal(f.last_diagnosis.id);
      });
    }
    tbody.appendChild(tr);
  });

  tbody.querySelectorAll("button[data-farm-id]").forEach((btn) => {
    btn.addEventListener("click", () => openNotifyModal(btn.dataset.farmId, btn.dataset.farmName));
  });
}

// ---------- 계정 관리(비밀번호 초기화 / 정보 수정) - 농가·컨설턴트 공용 ----------
// 농가 본인·컨설턴트 본인은 비밀번호를 잊거나 정보가 틀려도 스스로 고칠 화면이 없어,
// 관리자가 대신 처리해주는 최소 기능. editInfoContext에 지금 어떤 대상(농가명/대표자/
// 컨설턴트)을 고치는 중인지 저장해두고, 저장 성공 시 그 화면을 새로고침하는 콜백을 같이 둔다.
let editInfoContext = null;

function openEditInfoModal(kind, id, currentName, currentPhone, showPhone, title, onSuccess) {
  editInfoContext = { kind, id, onSuccess };
  document.getElementById("editInfoTitle").textContent = title;
  document.getElementById("editInfoName").value = currentName || "";
  document.getElementById("editInfoPhone").value = currentPhone || "";
  document.getElementById("editInfoPhoneLabel").classList.toggle("hidden", !showPhone);
  document.getElementById("editInfoPhone").classList.toggle("hidden", !showPhone);
  document.getElementById("editInfoModal").classList.remove("hidden");
}

function closeEditInfoModal() {
  document.getElementById("editInfoModal").classList.add("hidden");
  editInfoContext = null;
}

async function submitEditInfo() {
  if (!editInfoContext) return;
  const kind = editInfoContext.kind;
  const name = document.getElementById("editInfoName").value.trim();
  const phone = document.getElementById("editInfoPhone").value.trim();
  if (!name) {
    showToast("이름을 입력해주세요.", true);
    return;
  }
  try {
    if (kind === "household") {
      await Api.updateHousehold(editInfoContext.id, { name });
    } else if (kind === "user") {
      await Api.updateHouseholdUser(editInfoContext.id, { name, phone });
    } else if (kind === "consultant") {
      await Api.updateConsultant(editInfoContext.id, { name, phone });
    } else if (kind === "consultant-household") {
      // 컨설턴트 본인이 담당 농가 정보를 직접 수정하는 경로 - ConsultantApi(컨설턴트
      // 토큰)를 쓴다는 것만 관리자 경로와 다르고 모달/흐름은 그대로 재사용한다.
      await ConsultantApi.updateHousehold(editInfoContext.id, { name });
    } else if (kind === "consultant-user") {
      await ConsultantApi.updateHouseholdUser(editInfoContext.id, { name, phone });
    }
    showToast("정보가 수정되었습니다.");
    const onSuccess = editInfoContext.onSuccess;
    closeEditInfoModal();
    if (onSuccess) onSuccess();
  } catch (e) {
    if (e.isAuthError) {
      closeEditInfoModal();
      if (kind === "consultant-household" || kind === "consultant-user") handleConsultantLogout();
      else showLoginScreen();
      return;
    }
    showToast(e.message, true);
  }
}

function openTempPasswordModal(password) {
  document.getElementById("tempPasswordValue").value = password;
  document.getElementById("tempPasswordModal").classList.remove("hidden");
}

function closeTempPasswordModal() {
  document.getElementById("tempPasswordModal").classList.add("hidden");
  document.getElementById("tempPasswordValue").value = "";
}

async function resetHouseholdUserPasswordFlow(userId) {
  if (!confirm("비밀번호를 초기화하시겠습니까? 기존 비밀번호는 더 이상 사용할 수 없습니다.")) return;
  try {
    const result = await Api.resetHouseholdUserPassword(userId);
    openTempPasswordModal(result.temp_password);
  } catch (e) {
    if (e.isAuthError) {
      showLoginScreen();
      return;
    }
    showToast(e.message, true);
  }
}

async function resetConsultantPasswordFlow(consultantId) {
  if (!confirm("비밀번호를 초기화하시겠습니까? 기존 비밀번호는 더 이상 사용할 수 없습니다.")) return;
  try {
    const result = await Api.resetConsultantPassword(consultantId);
    openTempPasswordModal(result.temp_password);
  } catch (e) {
    if (e.isAuthError) {
      showLoginScreen();
      return;
    }
    showToast(e.message, true);
  }
}

const HOUSEHOLD_STATUS_LABEL = { active: "정상", suspended: "정지됨", withdrawn: "탈퇴 처리됨" };

async function suspendHouseholdFlow(householdId, refresh) {
  if (!confirm("이 농가 계정을 정지하시겠습니까?\n로그인만 즉시 차단되고 기존 데이터는 전혀 바뀌지 않습니다. 언제든 해제할 수 있습니다.")) return;
  try {
    await Api.suspendHousehold(householdId);
    showToast("계정이 정지되었습니다.");
    refresh();
  } catch (e) {
    if (e.isAuthError) {
      showLoginScreen();
      return;
    }
    showToast(e.message, true);
  }
}

async function reactivateHouseholdFlow(householdId, refresh) {
  if (!confirm("정지를 해제하시겠습니까? 즉시 다시 로그인할 수 있게 됩니다.")) return;
  try {
    await Api.reactivateHousehold(householdId);
    showToast("정지가 해제되었습니다.");
    refresh();
  } catch (e) {
    if (e.isAuthError) {
      showLoginScreen();
      return;
    }
    showToast(e.message, true);
  }
}

async function withdrawHouseholdFlow(householdId, householdName, refresh) {
  const warned = confirm(
    `"${householdName}" 농가를 탈퇴 처리하시겠습니까?\n\n` +
      "⚠ 이 작업은 되돌릴 수 없습니다.\n" +
      "- 로그인이 즉시 차단됩니다\n" +
      "- 농가명·대표자 이름/전화번호가 익명화됩니다\n" +
      "- 진단·작업일지 기록은 삭제되지 않고 그대로 보존됩니다(단, 익명화로 인해 더 이상 특정 개인을 가리키지 않게 됩니다)\n" +
      "- 컨설턴트 배정·처방 알림 발송 대상에서 제외됩니다"
  );
  if (!warned) return;
  const typed = prompt('정말 진행하려면 아래 입력창에 "탈퇴"를 입력해주세요.');
  if (typed !== "탈퇴") {
    showToast("입력값이 일치하지 않아 취소되었습니다.", true);
    return;
  }
  try {
    await Api.withdrawHousehold(householdId);
    showToast("탈퇴 처리되었습니다.");
    refresh();
    renderHouseholdConsultants(householdId, "withdrawn");
  } catch (e) {
    if (e.isAuthError) {
      showLoginScreen();
      return;
    }
    showToast(e.message, true);
  }
}

async function renderHouseholdAccountInfo(householdId) {
  const container = document.getElementById("householdAccountInfo");
  container.innerHTML = "불러오는 중…";
  try {
    const detail = await Api.getHouseholdDetail(householdId);
    const refresh = () => renderHouseholdAccountInfo(householdId);
    const isWithdrawn = detail.status === "withdrawn";
    const isSuspended = detail.status === "suspended";

    const memberRows = isWithdrawn
      ? ""
      : detail.members
          .map(
            (m) => `
      <div class="account-info-row">
        <span>${m.name} · ${m.phone}</span>
        <button class="btn btn-ghost btn-sm" data-edit-user="${m.id}">정보 수정</button>
        <button class="btn btn-ghost btn-sm" data-reset-user="${m.id}">비밀번호 초기화</button>
      </div>`
          )
          .join("");

    const statusLine = `
      <div class="account-info-row">
        <span><strong>${detail.name}</strong> (농가명) · 가입코드 ${detail.join_code}${householdStatusBadgeHtml(detail.status)}</span>
        ${isWithdrawn ? "" : '<button class="btn btn-ghost btn-sm" id="editHouseholdNameBtn">정보 수정</button>'}
      </div>`;

    const actionRow = `
      <div class="account-info-row">
        <span>계정 상태: ${HOUSEHOLD_STATUS_LABEL[detail.status] || detail.status}</span>
        <span>
          ${
            isWithdrawn
              ? ""
              : isSuspended
                ? '<button class="btn btn-ghost btn-sm" id="reactivateHouseholdBtn">정지 해제</button>'
                : '<button class="btn btn-ghost btn-sm" id="suspendHouseholdBtn">계정 정지</button>'
          }
          ${isWithdrawn ? "" : '<button class="admin-delete-btn" id="withdrawHouseholdBtn">탈퇴 처리</button>'}
        </span>
      </div>`;

    container.innerHTML = isWithdrawn
      ? statusLine + actionRow + '<p class="panel-note">탈퇴 처리된 농가입니다. 개인식별정보는 익명화되었고, 기존 진단·작업일지 기록은 통계용으로 보존됩니다.</p>'
      : statusLine + memberRows + actionRow;

    if (!isWithdrawn) {
      document.getElementById("editHouseholdNameBtn").addEventListener("click", () => {
        openEditInfoModal("household", detail.id, detail.name, null, false, "농가명 수정", refresh);
      });
      container.querySelectorAll("[data-edit-user]").forEach((btn) => {
        const member = detail.members.find((m) => m.id === Number(btn.dataset.editUser));
        btn.addEventListener("click", () => {
          openEditInfoModal("user", member.id, member.name, member.phone, true, "대표자 정보 수정", refresh);
        });
      });
      container.querySelectorAll("[data-reset-user]").forEach((btn) => {
        btn.addEventListener("click", () => resetHouseholdUserPasswordFlow(Number(btn.dataset.resetUser)));
      });
      if (isSuspended) {
        document.getElementById("reactivateHouseholdBtn").addEventListener("click", () => reactivateHouseholdFlow(householdId, refresh));
      } else {
        document.getElementById("suspendHouseholdBtn").addEventListener("click", () => suspendHouseholdFlow(householdId, refresh));
      }
      document.getElementById("withdrawHouseholdBtn").addEventListener("click", () => withdrawHouseholdFlow(householdId, detail.name, refresh));
    }
  } catch (e) {
    container.innerHTML = "계정 정보를 불러오지 못했습니다.";
  }
}

// 농가가 새 작물을 재배하기 시작했을 때 관리자가 노출 작물을 직접 추가/제거할 수 있게 한다.
// 최소 1개는 항상 남아있어야 한다(서버에서도 마지막 1개는 삭제를 막지만, UI에서도 미리
// x 버튼을 숨겨서 헛된 요청을 안 보내게 한다).
function renderHouseholdCrops(householdId) {
  const container = document.getElementById("householdCropChips");
  container.innerHTML = "로딩 중...";

  Promise.all([ensureCropsLoaded(), Api.getHouseholdCrops(householdId)])
    .then(([allCrops, myCrops]) => {
      container.innerHTML = "";
      const myCropIds = new Set(myCrops.map((c) => c.id));

      myCrops.forEach((c) => {
        const chip = document.createElement("span");
        chip.className = "badge badge-low";
        chip.style.display = "inline-flex";
        chip.style.alignItems = "center";
        chip.style.gap = "4px";
        chip.innerHTML = `${c.icon_emoji || ""} ${c.name_kr}`;
        if (myCrops.length > 1) {
          const removeBtn = document.createElement("button");
          removeBtn.textContent = "×";
          removeBtn.title = "노출 작물에서 제거";
          removeBtn.style.cssText = "border:none;background:none;cursor:pointer;font-weight:800;padding:0 0 0 2px;";
          removeBtn.addEventListener("click", () => {
            Api.removeHouseholdCrop(householdId, c.id)
              .then(() => renderHouseholdCrops(householdId))
              .catch((e) => showToast(`작물 제거 실패: ${e.message}`, true));
          });
          chip.appendChild(removeBtn);
        }
        container.appendChild(chip);
      });

      const remaining = allCrops.filter((c) => !myCropIds.has(c.id));
      if (remaining.length > 0) {
        const select = document.createElement("select");
        select.style.cssText = "font-size:12px;padding:2px 4px;";
        select.innerHTML = remaining.map((c) => `<option value="${c.id}">${c.icon_emoji || ""} ${c.name_kr}</option>`).join("");
        const addBtn = document.createElement("button");
        addBtn.className = "btn btn-ghost btn-sm";
        addBtn.textContent = "+ 작물 추가";
        addBtn.addEventListener("click", () => {
          Api.addHouseholdCrop(householdId, select.value)
            .then(() => renderHouseholdCrops(householdId))
            .catch((e) => showToast(`작물 추가 실패: ${e.message}`, true));
        });
        container.appendChild(select);
        container.appendChild(addBtn);
      }
    })
    .catch((e) => {
      container.innerHTML = "";
      showToast(`노출 작물 정보를 불러오지 못했습니다: ${e.message}`, true);
    });
}

// 이 농가를 담당하는 컨설턴트를 관리자가 직접 배정/해제한다. 작물과 달리 "최소 1명"
// 제약은 없다(컨설턴트 미배정 농가도 정상적인 상태) - x 버튼을 항상 보여준다.
let currentConsultantsCache = [];

function ensureConsultantsLoaded() {
  if (currentConsultantsCache.length > 0) return Promise.resolve(currentConsultantsCache);
  return Api.listConsultants().then((consultants) => {
    currentConsultantsCache = consultants;
    return consultants;
  });
}

function renderHouseholdConsultants(householdId, householdStatus) {
  const container = document.getElementById("householdConsultantChips");
  container.innerHTML = "로딩 중...";
  const isWithdrawn = householdStatus === "withdrawn";

  Promise.all([ensureConsultantsLoaded(), Api.getHouseholdConsultants(householdId)])
    .then(([allConsultants, myConsultants]) => {
      container.innerHTML = "";
      const myIds = new Set(myConsultants.map((c) => c.id));

      if (myConsultants.length === 0) {
        const empty = document.createElement("span");
        empty.style.cssText = "font-size:12px;color:var(--gray-400);";
        empty.textContent = "배정된 컨설턴트 없음";
        container.appendChild(empty);
      }

      myConsultants.forEach((c) => {
        const chip = document.createElement("span");
        chip.className = "badge badge-low";
        chip.style.display = "inline-flex";
        chip.style.alignItems = "center";
        chip.style.gap = "4px";
        chip.innerHTML = `👤 ${c.name}`;
        const removeBtn = document.createElement("button");
        removeBtn.textContent = "×";
        removeBtn.title = "담당에서 해제";
        removeBtn.style.cssText = "border:none;background:none;cursor:pointer;font-weight:800;padding:0 0 0 2px;";
        removeBtn.addEventListener("click", () => {
          Api.unassignConsultantHousehold(c.id, householdId)
            .then(() => renderHouseholdConsultants(householdId))
            .catch((e) => showToast(`담당 해제 실패: ${e.message}`, true));
        });
        chip.appendChild(removeBtn);
        container.appendChild(chip);
      });

      const remaining = allConsultants.filter((c) => !myIds.has(c.id));
      if (remaining.length > 0 && !isWithdrawn) {
        const select = document.createElement("select");
        select.style.cssText = "font-size:12px;padding:2px 4px;";
        select.innerHTML = remaining.map((c) => `<option value="${c.id}">${c.name}</option>`).join("");
        const addBtn = document.createElement("button");
        addBtn.className = "btn btn-ghost btn-sm";
        addBtn.textContent = "+ 컨설턴트 배정";
        addBtn.addEventListener("click", () => {
          Api.assignConsultantHousehold(select.value, householdId)
            .then(() => renderHouseholdConsultants(householdId))
            .catch((e) => showToast(`배정 실패: ${e.message}`, true));
        });
        container.appendChild(select);
        container.appendChild(addBtn);
      }
    })
    .catch((e) => {
      container.innerHTML = "";
      showToast(`담당 컨설턴트 정보를 불러오지 못했습니다: ${e.message}`, true);
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
    div.className = "feed-item feed-item-clickable";
    div.innerHTML = `
      <div class="feed-dot" style="background:${typeColors[item.diagnosis_type] || "#999"}"></div>
      <div class="feed-main">
        <div class="feed-title">${item.farm_name || "농가"} · ${item.final_disease_name || item.ai_disease_name || "진단 결과 없음"}</div>
        <div class="feed-sub">${item.region || "-"} · ${item.diagnosis_type} · 발생일 ${fmtDate(item.occurrence_date)}</div>
      </div>
      <div class="feed-confidence">${item.confidence != null ? Math.round(item.confidence * 100) + "%" : ""}</div>
      <div class="feed-time">${timeAgo(item.created_at)}</div>
    `;
    div.addEventListener("click", () => openDiagnosisDetailModal(item.id));
    list.appendChild(div);
  });
}

function loadFeedScreen() {
  return Api.getFeed(30, getSelectedCropId())
    .then(renderFeed)
    .catch((e) => {
      if (e.isAuthError) {
        showLoginScreen();
        return;
      }
      showToast(`실시간 진단 피드를 불러오지 못했습니다: ${e.message}`, true);
    });
}

// ---------- Weather ----------
function populateWeatherFarmSelect() {
  const select = document.getElementById("weatherFarmSelect");
  const prev = select.value;
  select.innerHTML =
    `<option value="">전체 농장 평균</option>` +
    currentFarms
      .map((f) => `<option value="${f.farm_id}">${f.household_name || "-"} · ${f.farm_name}</option>`)
      .join("");
  if (prev && currentFarms.some((f) => String(f.farm_id) === prev)) select.value = prev;
}

function renderWeatherChart(records) {
  const ctx = document.getElementById("weatherChart");
  const note = document.getElementById("weatherNote");
  if (charts.weather) charts.weather.destroy();

  if (records.length === 0) {
    note.textContent = "선택한 조건에 해당하는 기상 데이터가 없습니다.";
    charts.weather = new Chart(ctx, { type: "line", data: { labels: [], datasets: [] } });
    return;
  }
  note.textContent = `${records.length}건의 일별 기상 기록 (최신순으로 수집된 데이터를 날짜순 정렬하여 표시)`;

  const sorted = [...records].sort((a, b) => a.record_date.localeCompare(b.record_date));

  // 같은 날짜에 여러 농장 데이터가 섞여 있으면(전체 농장 선택 시) 날짜별 평균을 낸다.
  const byDate = {};
  sorted.forEach((r) => {
    if (!byDate[r.record_date]) byDate[r.record_date] = { temp: [], humidity: [], rainfall: [] };
    if (r.temp_c != null) byDate[r.record_date].temp.push(r.temp_c);
    if (r.humidity_percent != null) byDate[r.record_date].humidity.push(r.humidity_percent);
    if (r.rainfall_mm != null) byDate[r.record_date].rainfall.push(r.rainfall_mm);
  });
  const avg = (arr) => (arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : null);
  const labels = Object.keys(byDate).sort();
  const tempData = labels.map((d) => avg(byDate[d].temp));
  const humidityData = labels.map((d) => avg(byDate[d].humidity));
  const rainfallData = labels.map((d) => avg(byDate[d].rainfall));

  charts.weather = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "기온(℃)",
          data: tempData,
          borderColor: "#ef6c00",
          backgroundColor: "transparent",
          yAxisID: "y",
          tension: 0.3,
          pointRadius: 2,
        },
        {
          label: "습도(%)",
          data: humidityData,
          borderColor: "#1565c0",
          backgroundColor: "transparent",
          yAxisID: "y",
          tension: 0.3,
          pointRadius: 2,
        },
        {
          label: "강수량(mm)",
          data: rainfallData,
          borderColor: "#2e7d32",
          backgroundColor: "rgba(46,125,50,0.15)",
          yAxisID: "y1",
          type: "bar",
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } } },
      scales: {
        y: { position: "left", title: { display: true, text: "기온 / 습도" } },
        y1: { position: "right", title: { display: true, text: "강수량(mm)" }, grid: { drawOnChartArea: false } },
      },
    },
  });
}

function loadWeather() {
  const farmId = document.getElementById("weatherFarmSelect").value || null;
  const days = document.getElementById("weatherDaysSelect").value;
  Api.getWeatherHistory(farmId, days)
    .then(renderWeatherChart)
    .catch((e) => {
      if (e.isAuthError) {
        showLoginScreen();
        return;
      }
      showToast(`기상 데이터 로드 실패: ${e.message}`, true);
    });
}

// ---------- Reference CMS ----------
let currentReferences = [];
let editingReferenceId = null;
let currentCrops = [];
let currentAgriMaterials = [];

function ensureCropsLoaded() {
  if (currentCrops.length > 0) return Promise.resolve(currentCrops);
  return Api.listCrops().then((crops) => {
    currentCrops = crops;
    const select = document.getElementById("refCropId");
    select.innerHTML = crops
      .map((c) => `<option value="${c.id}">${c.icon_emoji || ""} ${c.name_kr}${c.is_sample_data ? " (샘플)" : ""}</option>`)
      .join("");
    return crops;
  });
}

function ensureAgriMaterialsLoaded() {
  return Api.listAgriMaterials()
    .then((materials) => {
      currentAgriMaterials = materials;
      const datalist = document.getElementById("materialsDatalist");
      datalist.innerHTML = materials.map((m) => `<option value="${m.name}"></option>`).join("");
      return materials;
    })
    .catch(() => {});
}

function loadReferences() {
  Api.listReferences()
    .then((refs) => {
      currentReferences = refs;
      renderReferenceTable();
    })
    .catch((e) => {
      if (e.isAuthError) {
        showLoginScreen();
        return;
      }
      showToast(`자료 목록 로드 실패: ${e.message}`, true);
    });
}

function renderReferenceTable() {
  const tbody = document.querySelector("#referenceTable tbody");
  tbody.innerHTML = "";
  if (currentReferences.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6">등록된 자료가 없습니다.</td></tr>`;
    return;
  }
  currentReferences.forEach((r) => {
    const tr = document.createElement("tr");
    tr.className = "clickable-row";
    tr.innerHTML = `
      <td>${r.crop_name}</td>
      <td><span class="${typeBadgeClass(r.type)}">${r.type}</span></td>
      <td><strong>${r.name_kr}</strong>${r.name_en ? ` <span class="panel-sub">${r.name_en}</span>` : ""}</td>
      <td>${r.is_active ? '<span class="badge badge-low">활성</span>' : '<span class="badge badge-mid">비활성</span>'}</td>
      <td>${new Date(r.updated_at).toLocaleDateString("ko-KR")} · ${r.updated_by || "-"}</td>
      <td><button class="btn btn-ghost btn-sm">수정</button></td>
    `;
    tr.addEventListener("click", () => openReferenceModal(r));
    tbody.appendChild(tr);
  });
}

function _treatmentItemRow(item) {
  const row = document.createElement("div");
  row.className = "treatment-item-row";
  row.innerHTML = `
    <input class="ti-product" type="text" list="materialsDatalist" placeholder="제품명" value="${(item?.product_name || "").replace(/"/g, "&quot;")}" />
    <input class="ti-ingredient" type="text" placeholder="성분" value="${(item?.active_ingredient || "").replace(/"/g, "&quot;")}" />
    <input class="ti-usage" type="text" placeholder="사용법" value="${(item?.usage || "").replace(/"/g, "&quot;")}" />
    <input class="ti-note" type="text" placeholder="비고" value="${(item?.note || "").replace(/"/g, "&quot;")}" />
    <button type="button" title="삭제">✕</button>
  `;
  row.querySelector("button").addEventListener("click", () => row.remove());
  return row;
}

function _readTreatmentList(containerId) {
  const rows = document.querySelectorAll(`#${containerId} .treatment-item-row`);
  const items = [];
  rows.forEach((row) => {
    const product_name = row.querySelector(".ti-product").value.trim();
    const active_ingredient = row.querySelector(".ti-ingredient").value.trim();
    const usage = row.querySelector(".ti-usage").value.trim();
    const note = row.querySelector(".ti-note").value.trim();
    if (product_name) items.push({ product_name, active_ingredient, usage, note: note || null });
  });
  return items;
}

async function openReferenceModal(ref) {
  editingReferenceId = ref ? ref.id : null;
  document.getElementById("referenceModalTitle").textContent = ref ? "자료 수정" : "신규 자료 추가";

  await ensureCropsLoaded();
  ensureAgriMaterialsLoaded();

  const cropSelect = document.getElementById("refCropId");
  if (ref?.crop_id) {
    cropSelect.value = String(ref.crop_id);
  } else if (currentCrops.length > 0) {
    cropSelect.value = String(currentCrops[0].id);
  }

  document.getElementById("refType").value = ref?.type || "병해";
  document.getElementById("refNameKr").value = ref?.name_kr || "";
  document.getElementById("refNameEn").value = ref?.name_en || "";
  document.getElementById("refSymptoms").value = ref?.symptoms || "";
  document.getElementById("refCause").value = ref?.cause || "";
  document.getElementById("refTempMin").value = ref?.favorable_temp_min ?? "";
  document.getElementById("refTempMax").value = ref?.favorable_temp_max ?? "";
  document.getElementById("refHumidityMin").value = ref?.favorable_humidity_min ?? "";
  document.getElementById("refIsActive").checked = ref ? !!ref.is_active : true;

  const ecoList = document.getElementById("refEcoList");
  const chemList = document.getElementById("refChemList");
  ecoList.innerHTML = "";
  chemList.innerHTML = "";
  (ref?.eco_treatments || []).forEach((t) => ecoList.appendChild(_treatmentItemRow(t)));
  (ref?.chemical_treatments || []).forEach((t) => chemList.appendChild(_treatmentItemRow(t)));

  document.getElementById("referenceDeleteBtn").classList.toggle("hidden", !ref);
  document.getElementById("referenceModal").classList.remove("hidden");
}

function closeReferenceModal() {
  document.getElementById("referenceModal").classList.add("hidden");
  editingReferenceId = null;
}

async function submitReference() {
  const payload = {
    crop_id: Number(document.getElementById("refCropId").value),
    type: document.getElementById("refType").value,
    name_kr: document.getElementById("refNameKr").value.trim(),
    name_en: document.getElementById("refNameEn").value.trim() || null,
    symptoms: document.getElementById("refSymptoms").value.trim() || null,
    cause: document.getElementById("refCause").value.trim() || null,
    favorable_temp_min: document.getElementById("refTempMin").value
      ? Number(document.getElementById("refTempMin").value)
      : null,
    favorable_temp_max: document.getElementById("refTempMax").value
      ? Number(document.getElementById("refTempMax").value)
      : null,
    favorable_humidity_min: document.getElementById("refHumidityMin").value
      ? Number(document.getElementById("refHumidityMin").value)
      : null,
    eco_treatments: _readTreatmentList("refEcoList"),
    chemical_treatments: _readTreatmentList("refChemList"),
    is_active: document.getElementById("refIsActive").checked,
  };
  if (!payload.name_kr) {
    showToast("병해충/생리장애명을 입력해주세요.", true);
    return;
  }

  try {
    if (editingReferenceId) {
      await Api.updateReference(editingReferenceId, payload);
      showToast("자료가 수정되었습니다.");
    } else {
      await Api.createReference(payload);
      showToast("자료가 추가되었습니다.");
    }
    closeReferenceModal();
    loadReferences();
  } catch (e) {
    if (e.isAuthError) {
      closeReferenceModal();
      showLoginScreen();
      return;
    }
    showToast(e.message, true);
  }
}

async function deleteReferenceHandler() {
  if (!editingReferenceId) return;
  if (!confirm("이 자료를 삭제하시겠습니까? AI 진단 참고자료에서도 제외됩니다.")) return;
  try {
    await Api.deleteReference(editingReferenceId);
    showToast("자료가 삭제되었습니다.");
    closeReferenceModal();
    loadReferences();
  } catch (e) {
    if (e.isAuthError) {
      closeReferenceModal();
      showLoginScreen();
      return;
    }
    showToast(e.message, true);
  }
}

// ---------- Photos / Diagnoses ----------
let currentDiagnoses = [];
let currentPhotoStatus = "";

function renderPhotoGrid() {
  const grid = document.getElementById("photoGrid");
  grid.innerHTML = "";
  const filtered = currentPhotoStatus
    ? currentDiagnoses.filter((d) => d.status === currentPhotoStatus)
    : currentDiagnoses;

  if (filtered.length === 0) {
    grid.innerHTML = `<div class="photo-empty">해당 상태의 진단 기록이 없습니다.</div>`;
    return;
  }

  filtered.forEach((d) => {
    const card = document.createElement("div");
    card.className = "photo-card";
    const photoPaths = d.photo_paths && d.photo_paths.length ? d.photo_paths : d.photo_path ? [d.photo_path] : [];
    const imgSrc = photoPaths.length ? `${Api.getBaseUrl()}/uploads/${photoPaths[0]}` : "";
    const effectiveName = d.final_disease_name || d.ai_disease_name || "진단명 없음";
    const finalBadge = d.final_disease_name
      ? `<span class="final-diagnosis-badge">${d.final_diagnosis_source === "expert" ? "전문가 확정" : "농가 직접확인"}</span>`
      : "";
    card.innerHTML = `
      <div class="photo-card-img-wrap">
        ${imgSrc ? `<img src="${imgSrc}" alt="진단 사진" loading="lazy" />` : `<div class="photo-card-noimg">사진 없음</div>`}
        ${photoPaths.length > 1 ? `<span class="photo-count-badge">📷 ${photoPaths.length}</span>` : ""}
      </div>
      <div class="photo-card-body">
        <div class="photo-card-title">${effectiveName} ${finalBadge}</div>
        <div class="photo-card-sub">${d.household_name || "-"} · ${d.farm_name || "-"} · ${fmtDate(d.occurrence_date)}</div>
        <div class="photo-card-footer">
          <span class="status-badge status-${d.status}">${d.status}</span>
          <span class="feed-confidence">${d.ai_confidence != null ? Math.round(d.ai_confidence * 100) + "%" : ""}</span>
        </div>
        <button class="btn btn-ghost btn-sm photo-expert-btn" data-id="${d.id}" data-name="${(d.final_disease_name || d.ai_disease_name || "").replace(/"/g, "&quot;")}" data-note="${(d.final_diagnosis_note || "").replace(/"/g, "&quot;")}">🩺 전문가 소견 입력</button>
      </div>
    `;
    grid.appendChild(card);
  });

  grid.querySelectorAll(".photo-expert-btn").forEach((btn) => {
    btn.addEventListener("click", () => openExpertDiagnosisModal(btn.dataset.id, btn.dataset.name, btn.dataset.note));
  });
}

function initPhotoTabs() {
  document.querySelectorAll("#photoStatusTabs .filter-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll("#photoStatusTabs .filter-tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      currentPhotoStatus = tab.dataset.status;
      renderPhotoGrid();
    });
  });
}

// ---------- Notifications ----------
function renderNotifications(notifications) {
  const tbody = document.querySelector("#notificationsTable tbody");
  tbody.innerHTML = "";
  if (notifications.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6">발송된 알림이 없습니다.</td></tr>`;
    return;
  }
  const broadcastCounts = {};
  notifications.forEach((n) => {
    if (n.broadcast_group) broadcastCounts[n.broadcast_group] = (broadcastCounts[n.broadcast_group] || 0) + 1;
  });
  notifications.forEach((n) => {
    const tr = document.createElement("tr");
    const methodCell = n.broadcast_group
      ? `<span class="broadcast-group-badge">일괄 ${broadcastCounts[n.broadcast_group]}건</span>`
      : "개별";
    tr.innerHTML = `
      <td>${new Date(n.created_at).toLocaleString("ko-KR")}</td>
      <td>${n.farm_name || "-"}</td>
      <td>${n.title}</td>
      <td>${n.recommended_product || "-"}</td>
      <td>${methodCell}</td>
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

// ---------- Broadcast modal ----------
// prefill: 지역 발생 현황 드릴다운에서 "이 지역·이 병해충 대상 알림 보내기"로 들어올 때
// { region, title, message } 형태로 넘어온다. 대상 조직은 여기서 미리 정하지 않는다 -
// role 기반 조직 필터링(누가 어느 조직을 볼 수 있는지)은 기존 로직 그대로 두고, 관리자가
// 화면에서 직접 고르게 한다.
async function openBroadcastModal(prefill = {}) {
  document.getElementById("broadcastTitle").value = prefill.title || "";
  document.getElementById("broadcastProduct").value = "";
  document.getElementById("broadcastMessage").value = prefill.message || "";
  const targetValue = prefill.region ? "region" : "all";
  document.querySelector(`input[name="broadcastTarget"][value="${targetValue}"]`).checked = true;
  updateBroadcastTargetVisibility();

  const regions = Array.from(new Set(currentFarms.map((f) => f.region).filter(Boolean))).sort();
  const regionSelect = document.getElementById("broadcastRegionSelect");
  regionSelect.innerHTML = regions.map((r) => `<option value="${r}">${r}</option>`).join("");
  if (prefill.region) regionSelect.value = prefill.region;

  // "전체 농가"/"지역 선택"은 조직 경계를 넘나드는 대상 선정이라, 어느 조직 대상인지
  // 화면에서 명시적으로 고르게 한다("농가 직접 선택"은 이미 특정 농가를 콕 집는 것이라
  // 조직 선택이 따로 필요 없음).
  try {
    const orgs = await Api.listOrganizations();
    const orgSelect = document.getElementById("broadcastOrgSelect");
    orgSelect.innerHTML = orgs.map((o) => `<option value="${o.id}">${o.name}</option>`).join("");
  } catch (e) {
    showToast("조직 목록을 불러오지 못했습니다: " + e.message, true);
  }

  const checklist = document.getElementById("broadcastFarmChecklist");
  checklist.innerHTML = currentFarms
    .map(
      (f) => `
    <label><input type="checkbox" value="${f.farm_id}" /> ${f.household_name || "-"} · ${f.farm_name}</label>
  `
    )
    .join("");

  document.getElementById("broadcastModal").classList.remove("hidden");
}

function closeBroadcastModal() {
  document.getElementById("broadcastModal").classList.add("hidden");
}

function updateBroadcastTargetVisibility() {
  const target = document.querySelector('input[name="broadcastTarget"]:checked').value;
  document.getElementById("broadcastOrgWrap").classList.toggle("hidden", target === "farms");
  document.getElementById("broadcastRegionWrap").classList.toggle("hidden", target !== "region");
  document.getElementById("broadcastFarmsWrap").classList.toggle("hidden", target !== "farms");
}

async function submitBroadcast() {
  const target = document.querySelector('input[name="broadcastTarget"]:checked').value;
  const title = document.getElementById("broadcastTitle").value.trim();
  const message = document.getElementById("broadcastMessage").value.trim();
  const product = document.getElementById("broadcastProduct").value.trim();
  if (!title || !message) {
    showToast("제목과 메시지를 입력해주세요.", true);
    return;
  }

  const payload = {
    target_type: target,
    title,
    message,
    recommended_product: product || null,
    sent_by: "관리자",
  };
  if (target !== "farms") {
    const orgId = document.getElementById("broadcastOrgSelect").value;
    if (!orgId) {
      showToast("대상 조직을 선택해주세요.", true);
      return;
    }
    payload.organization_id = Number(orgId);
  }
  if (target === "region") {
    payload.region = document.getElementById("broadcastRegionSelect").value;
    if (!payload.region) {
      showToast("지역을 선택해주세요.", true);
      return;
    }
  } else if (target === "farms") {
    const ids = Array.from(document.querySelectorAll("#broadcastFarmChecklist input:checked")).map((el) =>
      Number(el.value)
    );
    if (ids.length === 0) {
      showToast("대상 농가를 하나 이상 선택해주세요.", true);
      return;
    }
    payload.farm_ids = ids;
  }

  try {
    const result = await Api.broadcastNotification(payload);
    showToast(`${result.sent_count}개 농가에 공지를 발송했습니다.`);
    closeBroadcastModal();
    loadNotifications();
  } catch (e) {
    if (e.isAuthError) {
      closeBroadcastModal();
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
  const consultantShell = document.getElementById("consultantAppShell");
  if (consultantShell) consultantShell.classList.add("hidden");
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
let currentAdminId = null;

async function openAccountModal() {
  document.getElementById("pwCurrent").value = "";
  document.getElementById("pwNew").value = "";
  document.getElementById("newAccountRole").value = "admin";
  document.getElementById("newAccountName").value = "";
  document.getElementById("newAccountUsername").value = "";
  document.getElementById("newAccountPassword").value = "";
  document.getElementById("newAccountConsultantNote").classList.add("hidden");
  document.getElementById("accountModal").classList.remove("hidden");
  try {
    const me = await Api.getMe();
    currentAdminId = me.id;
    document.getElementById("accountMeLabel").textContent = `현재 로그인: ${me.name} (${me.username})`;
  } catch (e) {
    // 조회 실패해도 모달 자체는 그대로 사용 가능하도록 무시
  }
  loadAdminList();
  loadConsultantList();
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
        li.className = "admin-list-item";

        const label = document.createElement("span");
        label.textContent = `${a.name} (${a.username})`;
        if (a.is_protected) label.textContent += " · 최초 관리자";
        li.appendChild(label);

        if (a.id === currentAdminId) {
          const meTag = document.createElement("span");
          meTag.className = "admin-me-tag";
          meTag.textContent = "나";
          li.appendChild(meTag);
        } else if (a.is_protected) {
          const protectedTag = document.createElement("span");
          protectedTag.className = "admin-protected-tag";
          protectedTag.textContent = "삭제 불가";
          li.appendChild(protectedTag);
        } else {
          const delBtn = document.createElement("button");
          delBtn.textContent = "삭제";
          delBtn.className = "admin-delete-btn";
          delBtn.addEventListener("click", () => deleteAdmin(a.id, a.name));
          li.appendChild(delBtn);
        }

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

function updateNewAccountRoleUi() {
  const isConsultant = document.getElementById("newAccountRole").value === "consultant";
  document.getElementById("newAccountConsultantNote").classList.toggle("hidden", !isConsultant);
}

async function submitAddAccount() {
  const role = document.getElementById("newAccountRole").value;
  const name = document.getElementById("newAccountName").value.trim();
  const username = document.getElementById("newAccountUsername").value.trim();
  const password = document.getElementById("newAccountPassword").value;
  if (!name || !username || !password) {
    showToast("이름, 아이디, 초기 비밀번호를 모두 입력해주세요.", true);
    return;
  }
  if (password.length < 8) {
    showToast("초기 비밀번호는 8자 이상이어야 합니다.", true);
    return;
  }
  try {
    if (role === "consultant") {
      await Api.registerConsultant(username, password, name);
      showToast(`${name} 컨설턴트 계정이 추가되었습니다.`);
      loadConsultantList();
    } else {
      await Api.registerAdmin(username, password, name);
      showToast(`${name} 관리자 계정이 추가되었습니다.`);
      loadAdminList();
    }
    document.getElementById("newAccountName").value = "";
    document.getElementById("newAccountUsername").value = "";
    document.getElementById("newAccountPassword").value = "";
  } catch (e) {
    if (e.isAuthError) {
      closeAccountModal();
      showLoginScreen();
      return;
    }
    showToast(e.message, true);
  }
}

async function deleteAdmin(adminId, name) {
  if (!confirm(`${name} 관리자 계정을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.`)) return;
  try {
    await Api.deleteAdmin(adminId);
    showToast(`${name} 관리자 계정이 삭제되었습니다.`);
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

// ---------- Consultant account management ----------
function loadConsultantList() {
  Api.listConsultants()
    .then((consultants) => {
      const ul = document.getElementById("consultantListUl");
      ul.innerHTML = "";
      consultants.forEach((c) => {
        const li = document.createElement("li");
        li.className = "admin-list-item";

        const label = document.createElement("span");
        label.textContent = `${c.name} (${c.username})${c.phone ? " · " + c.phone : ""}`;
        li.appendChild(label);

        // 활동 실적통계는 계정관리에서 뺐다 - 대시보드 메인 화면(종합 현황)의
        // "컨설턴트 활동 실적" 카드 -> 상세 모달에서 컨설턴트 이름을 눌러 확인한다.
        // 여기(계정관리)에는 계정 자체를 다루는 기능(정보수정/비밀번호초기화/삭제)만 남긴다.
        const editBtn = document.createElement("button");
        editBtn.textContent = "정보 수정";
        editBtn.className = "btn btn-ghost btn-sm";
        editBtn.addEventListener("click", () =>
          openEditInfoModal("consultant", c.id, c.name, c.phone, true, "컨설턴트 정보 수정", loadConsultantList)
        );
        li.appendChild(editBtn);

        const resetBtn = document.createElement("button");
        resetBtn.textContent = "비밀번호 초기화";
        resetBtn.className = "btn btn-ghost btn-sm";
        resetBtn.addEventListener("click", () => resetConsultantPasswordFlow(c.id));
        li.appendChild(resetBtn);

        const delBtn = document.createElement("button");
        delBtn.textContent = "삭제";
        delBtn.className = "admin-delete-btn";
        delBtn.addEventListener("click", () => deleteConsultant(c.id, c.name));
        li.appendChild(delBtn);

        ul.appendChild(li);
      });
    })
    .catch(() => {});
}

const CONSULTANT_PERIOD_LABELS = {
  this_month: "이번 달",
  last_month: "지난 달",
  last_3_months: "최근 3개월",
  this_year: "올해",
  all: "전체 기간",
};

function openConsultantStatsModal(consultantId, name, periodOpts = {}) {
  const periodLabel =
    periodOpts.startDate || periodOpts.endDate
      ? `${periodOpts.startDate || "처음"} ~ ${periodOpts.endDate || "지금"}`
      : CONSULTANT_PERIOD_LABELS[periodOpts.period] || "전체 기간";
  document.getElementById("consultantStatsSub").textContent = `${name} 컨설턴트 · ${periodLabel}`;
  const body = document.getElementById("consultantStatsModalBody");
  body.textContent = "불러오는 중…";
  document.getElementById("consultantStatsModal").classList.remove("hidden");
  Api.getConsultantStats(consultantId, periodOpts)
    .then((stats) => {
      body.innerHTML = renderConsultantStatsHtml(stats);
    })
    .catch((e) => {
      if (e.isAuthError) {
        showLoginScreen();
        return;
      }
      body.textContent = `통계를 불러오지 못했습니다: ${e.message}`;
    });
}

function closeConsultantStatsModal() {
  document.getElementById("consultantStatsModal").classList.add("hidden");
}

// ---------- 컨설턴트 활동 실적 요약 (종합 현황 메인 화면 카드 - 항상 "이번 달" 스냅샷) ----------
function loadConsultantActivitySummary() {
  Api.getConsultantActivitySummary({ topN: 5, cropId: getSelectedCropId() })
    .then((summary) => {
      document.getElementById("consultantActivityMonthCount").textContent = summary.diagnosis_count;
      document.getElementById("consultantActivityActiveCount").textContent =
        `${summary.active_consultant_count} / ${summary.consultant_count}`;
      document.getElementById("consultantActivityRanking").innerHTML = renderConsultantRankingMiniList(summary.ranking);
    })
    .catch(() => {});
}

function renderConsultantRankingMiniList(ranking) {
  if (!ranking.length) {
    return `<li class="admin-list-item"><span class="panel-sub">등록된 컨설턴트가 없습니다.</span></li>`;
  }
  return ranking
    .map(
      (r, i) => `<li class="admin-list-item">
        <span>${i + 1}. ${r.name}</span>
        <span class="panel-sub">이번 달 ${r.diagnosis_count}건 · 누적 ${r.total_diagnosis_count}건</span>
      </li>`
    )
    .join("");
}

// ---------- 컨설턴트 활동현황 (전용 화면 - 기간 선택 + 전체 보기 + 개인별 상세) ----------
const CONSULTANT_ACTIVITY_COLUMN_LABELS = {
  name: "이름",
  diagnosis_count: "진단 건수",
  final_diagnosis_count: "최종확정 건수",
  comment_count: "코멘트 수",
  feedback_accuracy_percent: "피드백 일치율",
  total_diagnosis_count: "누적(전체기간)",
};

let consultantActivityState = {
  period: "this_month",
  startDate: null,
  endDate: null,
  sortField: "diagnosis_count",
  sortDir: "desc",
  ranking: [],
};

function loadConsultantActivityPage() {
  const { period, startDate, endDate } = consultantActivityState;
  Api.getConsultantActivitySummary({ topN: 1000, period, startDate, endDate, cropId: getSelectedCropId() })
    .then((summary) => {
      document.getElementById("consultantActivityPageDiagnosisCount").textContent = summary.diagnosis_count;
      document.getElementById("consultantActivityPageActiveCount").textContent =
        `${summary.active_consultant_count} / ${summary.consultant_count}`;
      consultantActivityState.ranking = summary.ranking;
      renderConsultantActivityTable();
    })
    .catch((e) => {
      if (e.isAuthError) {
        showLoginScreen();
        return;
      }
      showToast(`컨설턴트 활동현황을 불러오지 못했습니다: ${e.message}`, true);
    });
}

function sortedConsultantActivityRanking() {
  const { sortField, sortDir, ranking } = consultantActivityState;
  return [...ranking].sort((a, b) => {
    if (sortField === "name") {
      return sortDir === "asc" ? a.name.localeCompare(b.name, "ko") : b.name.localeCompare(a.name, "ko");
    }
    // 피드백 일치율은 데이터가 없으면 null - 정렬에서는 가장 낮은 값으로 취급한다.
    const av = a[sortField] ?? -1;
    const bv = b[sortField] ?? -1;
    return sortDir === "asc" ? av - bv : bv - av;
  });
}

function renderConsultantActivityTable() {
  const tbody = document.getElementById("consultantActivityTableBody");
  const rows = sortedConsultantActivityRanking();
  tbody.innerHTML = rows.length
    ? rows
        .map(
          (r) => `<tr class="clickable-row" data-consultant-id="${r.consultant_id}" data-consultant-name="${r.name}">
        <td>${r.name}</td>
        <td>${r.diagnosis_count}</td>
        <td>${r.final_diagnosis_count}</td>
        <td>${r.comment_count}</td>
        <td>${r.feedback_accuracy_percent != null ? r.feedback_accuracy_percent + "%" : "-"}</td>
        <td>${r.total_diagnosis_count}</td>
      </tr>`
        )
        .join("")
    : `<tr><td colspan="6" style="text-align:center; color: var(--gray-400);">등록된 컨설턴트가 없습니다.</td></tr>`;

  tbody.querySelectorAll("tr.clickable-row").forEach((tr) => {
    tr.addEventListener("click", () => {
      openConsultantStatsModal(Number(tr.dataset.consultantId), tr.dataset.consultantName, {
        period: consultantActivityState.period,
        startDate: consultantActivityState.startDate,
        endDate: consultantActivityState.endDate,
        cropId: getSelectedCropId(),
      });
    });
  });

  document.querySelectorAll('#consultantActivityTable th[data-sort]').forEach((th) => {
    const field = th.dataset.sort;
    const label = CONSULTANT_ACTIVITY_COLUMN_LABELS[field] || field;
    th.textContent =
      field === consultantActivityState.sortField
        ? `${label} ${consultantActivityState.sortDir === "asc" ? "▲" : "▼"}`
        : label;
  });
}

async function deleteConsultant(consultantId, name) {
  if (!confirm(`${name} 컨설턴트 계정을 삭제하시겠습니까? 담당 농가 배정도 함께 해제됩니다.`)) return;
  try {
    await Api.deleteConsultant(consultantId);
    showToast(`${name} 컨설턴트 계정이 삭제되었습니다.`);
    loadConsultantList();
  } catch (e) {
    if (e.isAuthError) {
      closeAccountModal();
      showLoginScreen();
      return;
    }
    showToast(e.message, true);
  }
}

// ---------- Diagnosis detail (농가 모니터링 / 실시간 진단 피드에서 항목 클릭) ----------
function openDiagnosisDetailModal(diagnosisId) {
  if (!diagnosisId) return;
  document.getElementById("diagnosisDetailModal").classList.remove("hidden");
  document.getElementById("diagnosisDetailSub").textContent = `진단 #${diagnosisId}`;
  document.getElementById("diagnosisDetailBody").innerHTML = "불러오는 중…";
  Api.getDiagnosisDetail(diagnosisId)
    .then(renderDiagnosisDetailBody)
    .catch((e) => {
      if (e.isAuthError) {
        closeDiagnosisDetailModal();
        showLoginScreen();
        return;
      }
      document.getElementById("diagnosisDetailBody").innerHTML = `불러오기 실패: ${e.message}`;
    });
}

function closeDiagnosisDetailModal() {
  document.getElementById("diagnosisDetailModal").classList.add("hidden");
}

function renderDiagnosisDetailBody(d) {
  document.getElementById("diagnosisDetailSub").textContent =
    `${d.household_name || "-"} · ${d.farm_name || "-"} (${d.region || "-"}) · ${fmtDate(d.occurrence_date)}`;

  const photoPaths = d.photo_paths && d.photo_paths.length ? d.photo_paths : d.photo_path ? [d.photo_path] : [];
  const photosHtml = photoPaths.length
    ? `<div class="diagnosis-photo-grid">${photoPaths
        .map((p) => `<img src="${Api.getBaseUrl()}/uploads/${p}" alt="진단 사진" loading="lazy" />`)
        .join("")}</div>`
    : `<div class="photo-card-noimg">첨부된 사진이 없습니다.</div>`;

  const effectiveName = d.final_disease_name || d.ai_disease_name || "진단명 없음";
  const registrant =
    d.created_by_type === "consultant" ? `👤 ${d.created_by_consultant_name || "컨설턴트"}` : "🌾 농가 직접 등록";

  const treatmentList = (items) =>
    items && items.length
      ? `<ul class="admin-list">${items
          .map(
            (t) =>
              `<li class="admin-list-item" style="display:block;">
                <strong>${t.product_name}</strong> <span style="color: var(--gray-500);">(${t.active_ingredient})</span>
                <div style="font-size:12px; color: var(--gray-600); margin-top:2px;">${t.usage}</div>
                ${t.note ? `<div style="font-size:11px; color: var(--gray-400); margin-top:2px;">※ ${t.note}</div>` : ""}
              </li>`
          )
          .join("")}</ul>`
      : `<p class="panel-sub">등록된 자료가 없습니다.</p>`;

  const finalBlock = d.final_disease_name
    ? `
      <div class="panel-sub" style="margin-top:14px;">최종 확정 진단</div>
      <p><strong>${d.final_disease_name}</strong> <span class="${typeBadgeClass(d.diagnosis_type)}">${
        d.final_diagnosis_source === "expert" ? "전문가 확정" : d.final_diagnosis_source === "consultant" ? "컨설턴트 확정" : "농가 직접확인"
      }</span></p>
      ${d.final_diagnosis_note ? `<p style="font-size:12.5px; color: var(--gray-600);">${d.final_diagnosis_note}</p>` : ""}
      <p style="font-size:11.5px; color: var(--gray-400);">확정자: ${d.final_diagnosis_by || "-"} · ${d.final_diagnosis_at ? fmtDate(d.final_diagnosis_at) : "-"}</p>
    `
    : "";

  // 정정 후 병명이 AI 원본과 달라지면, 아래 증상/방제 정보가 여전히 원본 기준
  // 고정값이라는 걸 화면에서 바로 알 수 있도록 두 섹션 앞에 각각 안내문을 붙인다.
  const correctionNotice =
    d.final_disease_name && d.ai_disease_name && d.final_disease_name !== d.ai_disease_name
      ? `<p style="font-size:11px; color: var(--gray-500); background: var(--gray-100, #f2f3f5); border-radius:6px; padding:6px 10px; margin: 8px 0;">ℹ️ 이 정보는 AI 원본 진단(${d.ai_disease_name}) 기준이며, 정정된 최종 진단명과 다를 수 있습니다.</p>`
      : "";

  document.getElementById("diagnosisDetailBody").innerHTML = `
    ${photosHtml}
    <div style="margin-top:14px; display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
      <span class="badge badge-type-${d.diagnosis_type}">${d.diagnosis_type}</span>
      <strong style="font-size:15px;">${effectiveName}</strong>
      ${d.ai_confidence != null ? `<span class="feed-confidence">AI 확신도 ${Math.round(d.ai_confidence * 100)}%</span>` : ""}
      <span class="status-badge status-${d.status}">${d.status}</span>
      <span style="font-size:11.5px; color: var(--gray-500); margin-left:auto;">${registrant}</span>
    </div>
    ${d.ai_symptoms ? `${correctionNotice}<div class="panel-sub" style="margin-top:14px;">특징 및 증상</div><p style="font-size:13px;">${d.ai_symptoms}</p>` : ""}
    <div class="panel-sub" style="margin-top:14px;">촬영 당시 기상 정보</div>
    ${
      d.weather_temp_c == null
        ? `<p style="font-size:12.5px; color: var(--gray-500);">위치 정보를 확인할 수 없어 날씨 데이터가 반영되지 않았습니다.</p>`
        : `
    ${
      d.weather_source !== "openweather_timemachine" && d.weather_source !== "openweather_current"
        ? `<p style="font-size:11.5px; color: var(--orange-500); background:#fdf0d8; border-radius:6px; padding:6px 10px; margin-bottom:6px; font-weight:600;">⚠ 실제 기상 데이터가 아닌 임시 값입니다</p>`
        : ""
    }
    <p style="font-size:12.5px; color: var(--gray-600);">
      기온 ${d.weather_temp_c.toFixed(1)}℃ ·
      습도 ${d.weather_humidity_percent != null ? Math.round(d.weather_humidity_percent) + "%" : "-"} ·
      강우량 ${d.weather_rainfall_mm != null ? d.weather_rainfall_mm.toFixed(1) + "mm" : "-"} ·
      풍속 ${d.weather_wind_ms != null ? d.weather_wind_ms.toFixed(1) + "m/s" : "-"}
    </p>
    ${
      d.weather_source === "openweather_current"
        ? `<p style="font-size:11px; color: var(--gray-400); margin-top:2px;">촬영 시점이 아닌 조회 시점 기준 날씨입니다</p>`
        : ""
    }
    `
    }
    ${
      d.gps_estimated || d.photo_taken_at_estimated
        ? `<p style="font-size:11px; color: var(--gray-400); margin-top:4px;">${[
            d.gps_estimated ? "정확한 촬영 위치 대신 농장 등록 주소 기준으로 조회됨" : null,
            d.photo_taken_at_estimated ? "촬영시각 확인 불가로 업로드 시각 기준으로 조회됨" : null,
          ]
            .filter(Boolean)
            .join(" · ")}</p>`
        : ""
    }
    ${finalBlock}
    ${correctionNotice}
    <div class="panel-sub" style="margin-top:14px;">친환경 방제 자재 (우선 추천)</div>
    ${treatmentList(d.eco_treatments)}
    <div class="panel-sub" style="margin-top:10px;">화학적 관리법 (보조 정보)</div>
    ${treatmentList(d.chemical_treatments)}
    ${
      d.final_disease_name
        ? `
    <div class="panel-sub" style="margin-top:14px;">정정 후 참고 정보 (${d.final_disease_name} 기준)</div>
    ${
      d.corrected_reference
        ? `
      ${d.corrected_reference.symptoms ? `<p style="font-size:12px; color: var(--gray-600); margin-bottom:8px;">${d.corrected_reference.symptoms}</p>` : ""}
      <div class="panel-sub" style="margin-top:8px; font-size:11.5px;">친환경 방제 자재</div>
      ${treatmentList(d.corrected_reference.eco_treatments)}
      <div class="panel-sub" style="margin-top:8px; font-size:11.5px;">화학적 관리법</div>
      ${treatmentList(d.corrected_reference.chemical_treatments)}
      `
        : `<p class="panel-sub">정정된 진단명에 대한 참고 방제자료가 등록돼 있지 않습니다 — 소견을 참고하세요.</p>`
    }
    `
        : ""
    }
  `;
}

// ---------- Expert diagnosis override ----------
let expertDiagnosisTargetId = null;

let expertDiagnosisNameOptionsLoaded = false;

function ensureExpertDiagnosisNameOptions() {
  if (expertDiagnosisNameOptionsLoaded) return;
  expertDiagnosisNameOptionsLoaded = true;
  Api.listReferences()
    .then((refs) => {
      const names = [...new Set(refs.map((r) => r.name_kr))];
      document.getElementById("expertDiagnosisNameList").innerHTML = names
        .map((n) => `<option value="${n.replace(/"/g, "&quot;")}"></option>`)
        .join("");
    })
    .catch(() => {
      expertDiagnosisNameOptionsLoaded = false;
    });
}

function openExpertDiagnosisModal(diagnosisId, currentName, currentNote) {
  expertDiagnosisTargetId = diagnosisId;
  document.getElementById("expertDiagnosisSub").textContent = `진단 #${diagnosisId}`;
  document.getElementById("expertDiagnosisName").value = currentName || "";
  document.getElementById("expertDiagnosisNote").value = currentNote || "";
  document.getElementById("expertDiagnosisModal").classList.remove("hidden");
  ensureExpertDiagnosisNameOptions();
}

function closeExpertDiagnosisModal() {
  document.getElementById("expertDiagnosisModal").classList.add("hidden");
  expertDiagnosisTargetId = null;
}

function loadPhotosDiagnoses() {
  return Api.getAdminDiagnoses({ limit: 200, crop_id: getSelectedCropId() })
    .then((diagnoses) => {
      currentDiagnoses = diagnoses;
      renderPhotoGrid();
    })
    .catch((e) => {
      if (e.isAuthError) {
        showLoginScreen();
        return;
      }
      showToast(`병해충 사진 목록을 불러오지 못했습니다: ${e.message}`, true);
    });
}

async function submitExpertDiagnosis() {
  const name = document.getElementById("expertDiagnosisName").value.trim();
  const note = document.getElementById("expertDiagnosisNote").value.trim();
  if (!name) {
    showToast("진단명을 입력해주세요.", true);
    return;
  }
  try {
    await Api.submitAdminFinalDiagnosis(expertDiagnosisTargetId, name, note);
    showToast("전문가 진단이 저장되었습니다.");
    closeExpertDiagnosisModal();
    await loadPhotosDiagnoses();
  } catch (e) {
    if (e.isAuthError) {
      closeExpertDiagnosisModal();
      showLoginScreen();
      return;
    }
    showToast(e.message, true);
  }
}

// ---------- 농가 참여도 현황 ----------
let participationState = {
  period: "last_3_months",
  startDate: null,
  endDate: null,
  sortField: "participation_score",
  sortDir: "desc",
  rows: [],
};

const PARTICIPATION_COLUMN_LABELS = {
  household_name: "농가명",
  diagnosis_count: "진단 요청 건수",
  worklog_count: "작업일지 작성 건수",
  last_worklog_days_ago: "최근 작성일",
  info_completeness_percent: "정보 완성도",
  participation_score: "종합 참여도 점수",
};

function loadParticipationOrganizations() {
  const select = document.getElementById("participationOrgSelect");
  if (select.options.length > 0) return Promise.resolve();
  return Api.listOrganizations()
    .then((orgs) => {
      select.innerHTML = orgs.map((o) => `<option value="${o.id}">${o.name}</option>`).join("");
    })
    .catch((e) => showToast("조직 목록을 불러오지 못했습니다: " + e.message, true));
}

function loadParticipationPage() {
  const orgId = document.getElementById("participationOrgSelect").value;
  if (!orgId) {
    showToast("대상 조직을 선택해주세요.", true);
    return;
  }
  const { period, startDate, endDate } = participationState;
  const tbody = document.querySelector("#participationTable tbody");
  tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color: var(--gray-400);">불러오는 중…</td></tr>`;
  Api.getHouseholdParticipation({ period, startDate, endDate, organizationId: orgId, cropId: getSelectedCropId() })
    .then((rows) => {
      participationState.rows = rows;
      renderParticipationTable();
    })
    .catch((e) => {
      if (e.isAuthError) {
        showLoginScreen();
        return;
      }
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color: var(--gray-400);">불러오기 실패: ${e.message}</td></tr>`;
    });
}

function sortedParticipationRows() {
  const { sortField, sortDir, rows } = participationState;
  return [...rows].sort((a, b) => {
    if (sortField === "household_name") {
      return sortDir === "asc"
        ? a.household_name.localeCompare(b.household_name, "ko")
        : b.household_name.localeCompare(a.household_name, "ko");
    }
    // 최근 작성일(일 전)은 값이 작을수록 "최근"이라 오름차순=최근순으로 느껴지도록 그대로 둔다.
    // 기록 없음(null)은 정렬에서 항상 가장 뒤로 보낸다.
    const av = a[sortField];
    const bv = b[sortField];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    return sortDir === "asc" ? av - bv : bv - av;
  });
}

function renderParticipationTable() {
  const tbody = document.querySelector("#participationTable tbody");
  const rows = sortedParticipationRows();
  tbody.innerHTML = rows.length
    ? rows
        .map(
          (r) => `<tr>
        <td>${r.household_name}</td>
        <td>${r.diagnosis_count}</td>
        <td>${r.worklog_count}</td>
        <td>${r.last_worklog_days_ago != null ? `${r.last_worklog_days_ago}일 전` : "기록 없음"}</td>
        <td>${r.info_completeness_percent}%</td>
        <td><strong>${r.participation_score}</strong></td>
      </tr>`
        )
        .join("")
    : `<tr><td colspan="6" style="text-align:center; color: var(--gray-400);">데이터가 없습니다.</td></tr>`;

  document.querySelectorAll('#participationTable th[data-sort]').forEach((th) => {
    const field = th.dataset.sort;
    const label = PARTICIPATION_COLUMN_LABELS[field] || field;
    th.textContent =
      field === participationState.sortField
        ? `${label} ${participationState.sortDir === "asc" ? "▲" : "▼"}`
        : label;
  });
}

function downloadParticipationCsv() {
  const rows = sortedParticipationRows();
  if (rows.length === 0) {
    showToast("내려받을 데이터가 없습니다.", true);
    return;
  }
  const header = ["농가명", "진단 요청 건수", "작업일지 작성 건수", "최근 작성일(일 전)", "정보 완성도(%)", "종합 참여도 점수"];
  const csvRows = [
    header,
    ...rows.map((r) => [
      r.household_name,
      r.diagnosis_count,
      r.worklog_count,
      r.last_worklog_days_ago != null ? r.last_worklog_days_ago : "",
      r.info_completeness_percent,
      r.participation_score,
    ]),
  ];
  const csv =
    "﻿" + csvRows.map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(",")).join("\r\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `농가_참여도_현황_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
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
    // 5개 화면(종합현황/지역별발생현황/컨설턴트 활동현황/농가 참여도현황/병해충 사진 관리)이
    // 공유하는 품목 선택 기본값을 데이터를 받아오기 전에 먼저 확정해야, 첫 화면부터 바로
    // "인삼" 기준으로 걸러진 숫자가 보인다(나중에 확정하면 전체 데이터가 잠깐 보였다가
    // 바뀌는 깜빡임이 생김).
    const crops = await ensureCropsLoaded();
    ensureCropDefault(crops);
    const cropId = getSelectedCropId();
    [
      "statsSummaryCropSelect",
      "regionalCropFilter",
      "consultantActivityCropSelect",
      "participationCropSelect",
      "photosCropSelect",
      "farmsCropSelect",
      "feedCropSelect",
    ].forEach((id) => {
      const el = document.getElementById(id);
      if (el) populateCropSelect(el);
    });

    const [summary, farmsAll, householdFarms, regional, feed, notifications, diagnoses] = await Promise.all([
      Api.getStatsSummary({ ...statsSummaryPeriodState, cropId }),
      Api.getFarmsOverview(), // 항상 전체 품목 - 기상/브로드캐스트 화면용 (currentFarms)
      Api.getFarmsOverview(cropId), // 농가 모니터링 화면 전용, 품목 필터 적용
      Api.getRegionalStats(cropId, regionalStatsPeriodState),
      Api.getFeed(30, cropId),
      Api.getNotifications(),
      Api.getAdminDiagnoses({ limit: 200, crop_id: cropId }),
    ]);
    currentFarms = farmsAll;
    renderSummary(summary);
    renderHouseholdsTable(householdFarms);
    renderMap(regional);
    renderRegionTable(regional);
    renderRegionCropChart(regional);
    renderFeed(feed);
    renderNotifications(notifications);
    currentDiagnoses = diagnoses;
    renderPhotoGrid();
    populateWeatherFarmSelect();
    loadWeather();
    loadReferences();
    loadConsultantActivitySummary();
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

// ---------- Community moderation ----------
function loadCommunityReports() {
  const tbody = document.querySelector("#communityReportsTable tbody");
  tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color: var(--gray-400);">불러오는 중…</td></tr>`;
  Api.listCommunityReports()
    .then(renderCommunityReports)
    .catch((e) => {
      if (e.isAuthError) {
        showLoginScreen();
        return;
      }
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color: var(--gray-400);">불러오기 실패: ${e.message}</td></tr>`;
    });
}

function renderCommunityReports(reports) {
  const tbody = document.querySelector("#communityReportsTable tbody");
  tbody.innerHTML = "";
  if (reports.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color: var(--gray-400);">신고된 글/댓글이 없습니다.</td></tr>`;
    return;
  }
  reports.forEach((r) => {
    const tr = document.createElement("tr");
    const targetLabel = r.target_type === "post" ? "게시글" : "댓글";
    const statusBadge =
      r.target_status === "hidden"
        ? `<span class="badge badge-high">숨김</span>`
        : `<span class="badge badge-low">노출중</span>`;
    tr.innerHTML = `
      <td>${targetLabel}</td>
      <td>${(r.target_preview || "(삭제됨)").slice(0, 60).replace(/</g, "&lt;")}</td>
      <td>${statusBadge}</td>
      <td>${r.reporter_household_name || "-"}</td>
      <td>${r.reason || "-"}</td>
      <td>${new Date(r.created_at).toLocaleString("ko-KR")}</td>
      <td></td>
    `;
    const actionsTd = tr.lastElementChild;
    if (r.target_status) {
      const toggleBtn = document.createElement("button");
      toggleBtn.className = "btn btn-ghost btn-sm";
      toggleBtn.textContent = r.target_status === "hidden" ? "복구" : "숨김";
      toggleBtn.addEventListener("click", () =>
        setCommunityTargetStatus(r.target_type, r.post_id || r.comment_id, r.target_status === "hidden" ? "visible" : "hidden")
      );
      actionsTd.appendChild(toggleBtn);

      const delBtn = document.createElement("button");
      delBtn.className = "admin-delete-btn";
      delBtn.textContent = "삭제";
      delBtn.style.marginLeft = "6px";
      delBtn.addEventListener("click", () => deleteCommunityTarget(r.target_type, r.post_id || r.comment_id));
      actionsTd.appendChild(delBtn);
    }
    tbody.appendChild(tr);
  });
}

async function setCommunityTargetStatus(targetType, targetId, status) {
  try {
    if (targetType === "post") await Api.updateCommunityPostStatus(targetId, status);
    else await Api.updateCommunityCommentStatus(targetId, status);
    showToast(status === "hidden" ? "숨김 처리되었습니다." : "복구되었습니다.");
    loadCommunityReports();
  } catch (e) {
    if (e.isAuthError) {
      showLoginScreen();
      return;
    }
    showToast(e.message, true);
  }
}

async function deleteCommunityTarget(targetType, targetId) {
  const label = targetType === "post" ? "게시글" : "댓글";
  if (!confirm(`이 ${label}을(를) 완전히 삭제하시겠습니까? 되돌릴 수 없습니다.`)) return;
  try {
    if (targetType === "post") await Api.deleteCommunityPost(targetId);
    else await Api.deleteCommunityComment(targetId);
    showToast(`${label}이(가) 삭제되었습니다.`);
    loadCommunityReports();
  } catch (e) {
    if (e.isAuthError) {
      showLoginScreen();
      return;
    }
    showToast(e.message, true);
  }
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
  initPhotoTabs();
  document.getElementById("photosCropSelect").addEventListener("change", (e) => {
    setSelectedCropId(e.target.value);
    loadPhotosDiagnoses();
  });
  document.getElementById("farmsCropSelect").addEventListener("change", (e) => {
    setSelectedCropId(e.target.value);
    loadHouseholdsScreen();
  });
  document.getElementById("feedCropSelect").addEventListener("change", (e) => {
    setSelectedCropId(e.target.value);
    loadFeedScreen();
  });
  document.getElementById("weatherFarmSelect").addEventListener("change", loadWeather);
  document.getElementById("weatherDaysSelect").addEventListener("change", loadWeather);
  document.getElementById("regionalCropFilter").addEventListener("change", (e) => {
    setSelectedCropId(e.target.value);
    loadRegionalStats(e.target.value);
  });

  document.getElementById("backToHouseholds").addEventListener("click", backToHouseholdList);
  document.getElementById("statFarmsCard").addEventListener("click", () => {
    document.querySelector('.nav-item[data-section="farms"]').click();
  });
  document.getElementById("consultantActivityCard").addEventListener("click", () => {
    document.querySelector('.nav-item[data-section="consultant-activity"]').click();
  });

  document.querySelectorAll('#consultantActivityTable th[data-sort]').forEach((th) => {
    th.addEventListener("click", () => {
      const field = th.dataset.sort;
      if (consultantActivityState.sortField === field) {
        consultantActivityState.sortDir = consultantActivityState.sortDir === "asc" ? "desc" : "asc";
      } else {
        consultantActivityState.sortField = field;
        consultantActivityState.sortDir = "desc";
      }
      renderConsultantActivityTable();
    });
  });

  document.getElementById("consultantActivityPeriod").addEventListener("change", (e) => {
    const val = e.target.value;
    consultantActivityState.period = val;
    document.getElementById("consultantActivityCustomRange").classList.toggle("hidden", val !== "custom");
    if (val !== "custom") {
      consultantActivityState.startDate = null;
      consultantActivityState.endDate = null;
      loadConsultantActivityPage();
    }
  });
  document.getElementById("consultantActivityCustomApply").addEventListener("click", () => {
    const start = document.getElementById("consultantActivityStartDate").value;
    const end = document.getElementById("consultantActivityEndDate").value;
    if (!start && !end) {
      showToast("시작일 또는 종료일을 선택해주세요.", true);
      return;
    }
    consultantActivityState.startDate = start || null;
    consultantActivityState.endDate = end || null;
    loadConsultantActivityPage();
  });
  document.getElementById("consultantActivityCropSelect").addEventListener("change", (e) => {
    setSelectedCropId(e.target.value);
    loadConsultantActivityPage();
  });

  document.getElementById("statsSummaryPeriod").addEventListener("change", (e) => {
    const val = e.target.value;
    statsSummaryPeriodState.period = val;
    document.getElementById("statsSummaryCustomRange").classList.toggle("hidden", val !== "custom");
    if (val !== "custom") {
      statsSummaryPeriodState.startDate = null;
      statsSummaryPeriodState.endDate = null;
      reloadStatsSummary();
    }
  });
  document.getElementById("statsSummaryCustomApply").addEventListener("click", () => {
    const start = document.getElementById("statsSummaryStartDate").value;
    const end = document.getElementById("statsSummaryEndDate").value;
    if (!start && !end) {
      showToast("시작일 또는 종료일을 선택해주세요.", true);
      return;
    }
    statsSummaryPeriodState.startDate = start || null;
    statsSummaryPeriodState.endDate = end || null;
    reloadStatsSummary();
  });
  document.getElementById("statsSummaryCropSelect").addEventListener("change", (e) => {
    setSelectedCropId(e.target.value);
    reloadStatsSummary();
    loadConsultantActivitySummary();
  });

  document.getElementById("regionalStatsPeriod").addEventListener("change", (e) => {
    const val = e.target.value;
    regionalStatsPeriodState.period = val;
    document.getElementById("regionalStatsCustomRange").classList.toggle("hidden", val !== "custom");
    if (val !== "custom") {
      regionalStatsPeriodState.startDate = null;
      regionalStatsPeriodState.endDate = null;
      loadRegionalStats(currentRegionalCropFilterValue());
    }
  });
  document.getElementById("regionalStatsCustomApply").addEventListener("click", () => {
    const start = document.getElementById("regionalStatsStartDate").value;
    const end = document.getElementById("regionalStatsEndDate").value;
    if (!start && !end) {
      showToast("시작일 또는 종료일을 선택해주세요.", true);
      return;
    }
    regionalStatsPeriodState.startDate = start || null;
    regionalStatsPeriodState.endDate = end || null;
    loadRegionalStats(currentRegionalCropFilterValue());
  });

  document.getElementById("participationOrgSelect").addEventListener("change", loadParticipationPage);
  document.getElementById("participationPeriod").addEventListener("change", (e) => {
    const val = e.target.value;
    participationState.period = val;
    document.getElementById("participationCustomRange").classList.toggle("hidden", val !== "custom");
    if (val !== "custom") {
      participationState.startDate = null;
      participationState.endDate = null;
      loadParticipationPage();
    }
  });
  document.getElementById("participationCustomApply").addEventListener("click", () => {
    const start = document.getElementById("participationStartDate").value;
    const end = document.getElementById("participationEndDate").value;
    if (!start && !end) {
      showToast("시작일 또는 종료일을 선택해주세요.", true);
      return;
    }
    participationState.startDate = start || null;
    participationState.endDate = end || null;
    loadParticipationPage();
  });
  document.getElementById("participationCropSelect").addEventListener("change", (e) => {
    setSelectedCropId(e.target.value);
    loadParticipationPage();
  });
  document.getElementById("participationCsvBtn").addEventListener("click", downloadParticipationCsv);
  document.querySelectorAll('#participationTable th[data-sort]').forEach((th) => {
    th.addEventListener("click", () => {
      const field = th.dataset.sort;
      if (participationState.sortField === field) {
        participationState.sortDir = participationState.sortDir === "asc" ? "desc" : "asc";
      } else {
        participationState.sortField = field;
        participationState.sortDir = "desc";
      }
      renderParticipationTable();
    });
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

  document.getElementById("openBroadcastBtn").addEventListener("click", () => openBroadcastModal());
  document.getElementById("broadcastCancel").addEventListener("click", closeBroadcastModal);
  document.getElementById("broadcastSend").addEventListener("click", submitBroadcast);
  document.getElementById("broadcastModal").addEventListener("click", (e) => {
    if (e.target.id === "broadcastModal") closeBroadcastModal();
  });
  document.querySelectorAll('input[name="broadcastTarget"]').forEach((radio) => {
    radio.addEventListener("change", updateBroadcastTargetVisibility);
  });

  document.getElementById("loginForm").addEventListener("submit", handleLoginSubmit);
  document.getElementById("logoutBtn").addEventListener("click", handleLogout);
  document.getElementById("installBtn").addEventListener("click", handleInstallClick);

  document.getElementById("accountBtn").addEventListener("click", openAccountModal);
  document.getElementById("accountClose").addEventListener("click", closeAccountModal);
  document.getElementById("accountModal").addEventListener("click", (e) => {
    if (e.target.id === "accountModal") closeAccountModal();
  });
  document.getElementById("pwSubmit").addEventListener("click", submitChangePassword);
  document.getElementById("newAccountRole").addEventListener("change", updateNewAccountRoleUi);
  document.getElementById("newAccountSubmit").addEventListener("click", submitAddAccount);

  document.getElementById("editInfoCancel").addEventListener("click", closeEditInfoModal);
  document.getElementById("editInfoSubmit").addEventListener("click", submitEditInfo);
  document.getElementById("editInfoModal").addEventListener("click", (e) => {
    if (e.target.id === "editInfoModal") closeEditInfoModal();
  });
  document.getElementById("tempPasswordClose").addEventListener("click", closeTempPasswordModal);
  document.getElementById("tempPasswordCopy").addEventListener("click", () => {
    const input = document.getElementById("tempPasswordValue");
    input.select();
    navigator.clipboard?.writeText(input.value).catch(() => {});
    showToast("복사되었습니다.");
  });
  document.getElementById("consultantStatsModalClose").addEventListener("click", closeConsultantStatsModal);
  document.getElementById("consultantStatsModal").addEventListener("click", (e) => {
    if (e.target.id === "consultantStatsModal") closeConsultantStatsModal();
  });

  document.getElementById("regionBreakdownClose").addEventListener("click", closeRegionBreakdownModal);
  document.getElementById("regionBreakdownModal").addEventListener("click", (e) => {
    if (e.target.id === "regionBreakdownModal") closeRegionBreakdownModal();
  });
  document.getElementById("regionBreakdownBackBtn").addEventListener("click", backToRegionBreakdownList);
  document.getElementById("regionBreakdownNotifyBtn").addEventListener("click", notifyFromRegionBreakdown);

  document.getElementById("diagnosisDetailClose").addEventListener("click", closeDiagnosisDetailModal);
  document.getElementById("diagnosisDetailModal").addEventListener("click", (e) => {
    if (e.target.id === "diagnosisDetailModal") closeDiagnosisDetailModal();
  });

  document.getElementById("expertDiagnosisCancel").addEventListener("click", closeExpertDiagnosisModal);
  document.getElementById("expertDiagnosisSubmit").addEventListener("click", submitExpertDiagnosis);
  document.getElementById("expertDiagnosisModal").addEventListener("click", (e) => {
    if (e.target.id === "expertDiagnosisModal") closeExpertDiagnosisModal();
  });

  document.getElementById("openReferenceAddBtn").addEventListener("click", () => openReferenceModal(null));
  document.getElementById("referenceCancel").addEventListener("click", closeReferenceModal);
  document.getElementById("referenceSubmit").addEventListener("click", submitReference);
  document.getElementById("referenceDeleteBtn").addEventListener("click", deleteReferenceHandler);
  document.getElementById("referenceModal").addEventListener("click", (e) => {
    if (e.target.id === "referenceModal") closeReferenceModal();
  });
  document.getElementById("refEcoAdd").addEventListener("click", () => {
    document.getElementById("refEcoList").appendChild(_treatmentItemRow(null));
  });
  document.getElementById("refChemAdd").addEventListener("click", () => {
    document.getElementById("refChemList").appendChild(_treatmentItemRow(null));
  });

  if (Api.isLoggedIn()) {
    showAppShell();
    loadAll();
  } else {
    showLoginScreen();
  }
}

document.addEventListener("DOMContentLoaded", init);
