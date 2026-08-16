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
    photos: "병해충 사진 관리",
    weather: "기상 데이터",
    reference: "병해충·자재 자료",
    notifications: "처방 알림 이력",
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
    const cropStr = Object.entries(r.by_crop || {})
      .map(([c, n]) => `${c} ${n}`)
      .join(" · ");
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${r.region}</strong></td>
      <td>${r.total}건</td>
      <td>${r.top_issue || "-"}</td>
      <td>${typeStr}</td>
      <td>${cropStr || "-"}</td>
    `;
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
function loadRegionalStats(cropId) {
  return Api.getRegionalStats(cropId || undefined)
    .then((regional) => {
      renderMap(regional);
      renderRegionTable(regional);
      renderRegionCropChart(regional);
    })
    .catch((e) => showToast(`지역 통계 로드 실패: ${e.message}`, true));
}

function populateRegionalCropFilter() {
  ensureCropsLoaded().then((crops) => {
    const select = document.getElementById("regionalCropFilter");
    const current = select.value;
    select.innerHTML =
      `<option value="">전체 작물</option>` +
      crops.map((c) => `<option value="${c.id}">${c.icon_emoji || ""} ${c.name_kr}</option>`).join("");
    select.value = current;
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

  renderHouseholdCrops(householdId);
  renderHouseholdConsultants(householdId);

  const farms = currentFarms.filter((f) => f.household_id === householdId);
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

function renderHouseholdConsultants(householdId) {
  const container = document.getElementById("householdConsultantChips");
  container.innerHTML = "로딩 중...";

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
      if (remaining.length > 0) {
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
        <div class="feed-title">${item.farm_name || "농가"} · ${item.ai_disease_name || "진단 결과 없음"}</div>
        <div class="feed-sub">${item.region || "-"} · ${item.diagnosis_type} · 발생일 ${fmtDate(item.occurrence_date)}</div>
      </div>
      <div class="feed-confidence">${item.confidence != null ? Math.round(item.confidence * 100) + "%" : ""}</div>
      <div class="feed-time">${timeAgo(item.created_at)}</div>
    `;
    div.addEventListener("click", () => openDiagnosisDetailModal(item.id));
    list.appendChild(div);
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
function openBroadcastModal() {
  document.getElementById("broadcastTitle").value = "";
  document.getElementById("broadcastProduct").value = "";
  document.getElementById("broadcastMessage").value = "";
  document.querySelector('input[name="broadcastTarget"][value="all"]').checked = true;
  updateBroadcastTargetVisibility();

  const regions = Array.from(new Set(currentFarms.map((f) => f.region).filter(Boolean))).sort();
  const regionSelect = document.getElementById("broadcastRegionSelect");
  regionSelect.innerHTML = regions.map((r) => `<option value="${r}">${r}</option>`).join("");

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
        label.textContent = `${c.name} (${c.username})`;
        li.appendChild(label);

        const statsBtn = document.createElement("button");
        statsBtn.textContent = "통계";
        statsBtn.className = "btn btn-ghost btn-sm";
        statsBtn.style.marginRight = "6px";
        statsBtn.addEventListener("click", () => openConsultantStatsModal(c.id, c.name));
        li.appendChild(statsBtn);

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

function openConsultantStatsModal(consultantId, name) {
  document.getElementById("consultantStatsSub").textContent = `${name} 컨설턴트`;
  const body = document.getElementById("consultantStatsModalBody");
  body.textContent = "불러오는 중…";
  document.getElementById("consultantStatsModal").classList.remove("hidden");
  Api.getConsultantStats(consultantId)
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

  document.getElementById("diagnosisDetailBody").innerHTML = `
    ${photosHtml}
    <div style="margin-top:14px; display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
      <span class="badge badge-type-${d.diagnosis_type}">${d.diagnosis_type}</span>
      <strong style="font-size:15px;">${effectiveName}</strong>
      ${d.ai_confidence != null ? `<span class="feed-confidence">AI 확신도 ${Math.round(d.ai_confidence * 100)}%</span>` : ""}
      <span class="status-badge status-${d.status}">${d.status}</span>
      <span style="font-size:11.5px; color: var(--gray-500); margin-left:auto;">${registrant}</span>
    </div>
    ${d.ai_symptoms ? `<div class="panel-sub" style="margin-top:14px;">특징 및 증상</div><p style="font-size:13px;">${d.ai_symptoms}</p>` : ""}
    <div class="panel-sub" style="margin-top:14px;">촬영 당시 기상 정보</div>
    <p style="font-size:12.5px; color: var(--gray-600);">
      기온 ${d.weather_temp_c != null ? d.weather_temp_c.toFixed(1) + "℃" : "-"} ·
      습도 ${d.weather_humidity_percent != null ? Math.round(d.weather_humidity_percent) + "%" : "-"} ·
      강우량 ${d.weather_rainfall_mm != null ? d.weather_rainfall_mm.toFixed(1) + "mm" : "-"} ·
      풍속 ${d.weather_wind_ms != null ? d.weather_wind_ms.toFixed(1) + "m/s" : "-"}
    </p>
    ${finalBlock}
    <div class="panel-sub" style="margin-top:14px;">친환경 방제 자재 (우선 추천)</div>
    ${treatmentList(d.eco_treatments)}
    <div class="panel-sub" style="margin-top:10px;">화학적 관리법 (보조 정보)</div>
    ${treatmentList(d.chemical_treatments)}
  `;
}

// ---------- Expert diagnosis override ----------
let expertDiagnosisTargetId = null;

function openExpertDiagnosisModal(diagnosisId, currentName, currentNote) {
  expertDiagnosisTargetId = diagnosisId;
  document.getElementById("expertDiagnosisSub").textContent = `진단 #${diagnosisId}`;
  document.getElementById("expertDiagnosisName").value = currentName || "";
  document.getElementById("expertDiagnosisNote").value = currentNote || "";
  document.getElementById("expertDiagnosisModal").classList.remove("hidden");
}

function closeExpertDiagnosisModal() {
  document.getElementById("expertDiagnosisModal").classList.add("hidden");
  expertDiagnosisTargetId = null;
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
    const diagnoses = await Api.getAdminDiagnoses({ limit: 200 });
    currentDiagnoses = diagnoses;
    renderPhotoGrid();
  } catch (e) {
    if (e.isAuthError) {
      closeExpertDiagnosisModal();
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
    const [summary, farms, regional, feed, notifications, diagnoses] = await Promise.all([
      Api.getStatsSummary(),
      Api.getFarmsOverview(),
      Api.getRegionalStats(),
      Api.getFeed(30),
      Api.getNotifications(),
      Api.getAdminDiagnoses({ limit: 200 }),
    ]);
    renderSummary(summary);
    renderHouseholdsTable(farms);
    renderMap(regional);
    renderRegionTable(regional);
    renderRegionCropChart(regional);
    populateRegionalCropFilter();
    renderFeed(feed);
    renderNotifications(notifications);
    currentDiagnoses = diagnoses;
    renderPhotoGrid();
    populateWeatherFarmSelect();
    loadWeather();
    loadReferences();
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
  document.getElementById("weatherFarmSelect").addEventListener("change", loadWeather);
  document.getElementById("weatherDaysSelect").addEventListener("change", loadWeather);
  document.getElementById("regionalCropFilter").addEventListener("change", (e) => loadRegionalStats(e.target.value));

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

  document.getElementById("openBroadcastBtn").addEventListener("click", openBroadcastModal);
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

  document.getElementById("accountBtn").addEventListener("click", openAccountModal);
  document.getElementById("accountClose").addEventListener("click", closeAccountModal);
  document.getElementById("accountModal").addEventListener("click", (e) => {
    if (e.target.id === "accountModal") closeAccountModal();
  });
  document.getElementById("pwSubmit").addEventListener("click", submitChangePassword);
  document.getElementById("newAccountRole").addEventListener("change", updateNewAccountRoleUi);
  document.getElementById("newAccountSubmit").addEventListener("click", submitAddAccount);
  document.getElementById("consultantStatsModalClose").addEventListener("click", closeConsultantStatsModal);
  document.getElementById("consultantStatsModal").addEventListener("click", (e) => {
    if (e.target.id === "consultantStatsModal") closeConsultantStatsModal();
  });

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
