// 컨설턴트 전용 로직. dashboard.js(관리자 전용)와 상태를 공유하지 않도록 완전히
// 분리한다 - 토큰도 별도 localStorage 키(consultantToken)를 쓴다. API 서버 주소만
// 관리자 대시보드와 동일하게 Api.getBaseUrl()을 그대로 재사용한다.
const ConsultantApi = (() => {
  let token = localStorage.getItem("consultantToken") || null;

  function setToken(t) {
    token = t;
    if (t) localStorage.setItem("consultantToken", t);
    else localStorage.removeItem("consultantToken");
  }

  function isLoggedIn() {
    return !!token;
  }

  async function request(path, options = {}) {
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(`${Api.getBaseUrl()}${path}`, { ...options, headers });
    if (res.status === 401) {
      setToken(null);
      const err = new Error("로그인이 만료되었습니다. 다시 로그인해주세요.");
      err.isAuthError = true;
      throw err;
    }
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`API 오류 (${res.status}): ${text}`);
    }
    return res.json();
  }

  async function requestMultipart(path, method, formData) {
    const headers = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(`${Api.getBaseUrl()}${path}`, { method, headers, body: formData });
    if (res.status === 401) {
      setToken(null);
      const err = new Error("로그인이 만료되었습니다. 다시 로그인해주세요.");
      err.isAuthError = true;
      throw err;
    }
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`API 오류 (${res.status}): ${text}`);
    }
    return res.json();
  }

  return {
    setToken,
    isLoggedIn,
    login: (username, password) =>
      request("/api/consultant/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
    getMe: () => request("/api/consultant/auth/me"),
    getHouseholds: () => request("/api/consultant/households"),
    getDiagnoses: (farmId) => request(`/api/consultant/diagnoses?farm_id=${farmId}`),
    createDiagnosis: (formData) => requestMultipart("/api/consultant/diagnoses", "POST", formData),
    submitFinalDiagnosis: (diagnosisId, diseaseName, note) =>
      request(`/api/consultant/diagnoses/${diagnosisId}/final-diagnosis`, {
        method: "PATCH",
        body: JSON.stringify({ disease_name: diseaseName, note: note || null }),
      }),
    getComments: (diagnosisId) => request(`/api/consultant/diagnoses/${diagnosisId}/comments`),
    getStats: () => request("/api/consultant/stats/summary"),
    createComment: (diagnosisId, body) =>
      request(`/api/consultant/diagnoses/${diagnosisId}/comments`, {
        method: "POST",
        body: JSON.stringify({ body }),
      }),
  };
})();

// ---------- 로그인 화면 전환 ----------
function showConsultantLoginForm() {
  document.getElementById("loginForm").classList.add("hidden");
  document.getElementById("consultantLoginForm").classList.remove("hidden");
}

function showAdminLoginForm() {
  document.getElementById("consultantLoginForm").classList.add("hidden");
  document.getElementById("loginForm").classList.remove("hidden");
}

async function handleConsultantLoginSubmit(e) {
  e.preventDefault();
  const username = document.getElementById("consultantLoginUsername").value.trim();
  const password = document.getElementById("consultantLoginPassword").value;
  const errorBox = document.getElementById("consultantLoginError");
  errorBox.classList.add("hidden");
  if (!username || !password) return;

  try {
    const resp = await ConsultantApi.login(username, password);
    ConsultantApi.setToken(resp.access_token);
    showConsultantAppShell();
    loadConsultantAll();
  } catch (err) {
    errorBox.textContent = "아이디 또는 비밀번호가 올바르지 않습니다.";
    errorBox.classList.remove("hidden");
  }
}

function showConsultantAppShell() {
  document.getElementById("loginScreen").classList.add("hidden");
  document.getElementById("consultantAppShell").classList.remove("hidden");
}

function handleConsultantLogout() {
  ConsultantApi.setToken(null);
  document.getElementById("loginScreen").classList.remove("hidden");
  document.getElementById("consultantAppShell").classList.add("hidden");
  document.getElementById("consultantLoginPassword").value = "";
}

// ---------- 네비게이션 ----------
function initConsultantNav() {
  const navItems = document.querySelectorAll("#consultantAppShell .nav-item");
  const titles = { "c-households": "담당 농가", "c-stats": "내 활동 통계" };
  navItems.forEach((item) => {
    item.addEventListener("click", (e) => {
      e.preventDefault();
      const section = item.dataset.csection;
      navItems.forEach((i) => i.classList.remove("active"));
      item.classList.add("active");
      document.querySelectorAll("#consultantAppShell .section").forEach((s) => s.classList.add("hidden"));
      document.getElementById(section).classList.remove("hidden");
      document.getElementById("consultantPageTitle").textContent = titles[section];
      if (section === "c-stats") loadConsultantStats();
    });
  });
}

// ---------- 담당 농가 / 진단 ----------
let consultantHouseholds = [];
const diagnosisTypeOptions = ["병해", "해충", "생리장애"];

async function loadConsultantAll() {
  try {
    const me = await ConsultantApi.getMe();
    document.getElementById("consultantMeLabel").textContent = `${me.name} 컨설턴트`;
    document.getElementById("consultantConnStatus").textContent = `연결됨: ${Api.getBaseUrl()}`;
    document.getElementById("consultantConnStatus").className = "conn-status conn-ok";
  } catch (e) {
    if (e.isAuthError) {
      handleConsultantLogout();
      return;
    }
  }
  loadConsultantHouseholds();
}

function loadConsultantHouseholds() {
  ConsultantApi.getHouseholds()
    .then((households) => {
      consultantHouseholds = households;
      const tbody = document.querySelector("#consultantHouseholdsTable tbody");
      tbody.innerHTML = "";
      if (households.length === 0) {
        tbody.innerHTML = `<tr><td colspan="3" style="text-align:center; color: var(--gray-400);">배정된 담당 농가가 없습니다. 관리자에게 문의해주세요.</td></tr>`;
        return;
      }
      households.forEach((h) => {
        const tr = document.createElement("tr");
        tr.style.cursor = "pointer";
        tr.innerHTML = `<td><strong>${h.name}</strong></td><td>${h.join_code}</td><td>${h.farms.length}개</td>`;
        tr.addEventListener("click", () => showConsultantHouseholdDetail(h.id));
        tbody.appendChild(tr);
      });
    })
    .catch((e) => {
      if (e.isAuthError) handleConsultantLogout();
      else showToast(`담당 농가 조회 실패: ${e.message}`, true);
    });
}

function showConsultantHouseholdDetail(householdId) {
  const household = consultantHouseholds.find((h) => h.id === householdId);
  if (!household) return;

  document.getElementById("consultantHouseholdListPanel").classList.add("hidden");
  document.getElementById("consultantHouseholdDetailPanel").classList.remove("hidden");
  document.getElementById("consultantHouseholdDetailTitle").textContent = `${household.name} · 농장 목록`;

  const container = document.getElementById("consultantFarmsList");
  container.innerHTML = "";
  household.farms.forEach((f) => {
    const card = document.createElement("div");
    card.className = "panel";
    card.innerHTML = `
      <div class="panel-header">
        <h2>${f.farm_name}</h2>
        <span class="panel-sub">${f.crop_name || ""} · ${f.region || "-"} · ${f.address || ""}</span>
      </div>
      <div class="table-wrap">
        <table class="data-table" id="c-diag-table-${f.id}">
          <thead><tr><th>발생일</th><th>진단명</th><th>확신도</th><th>등록자</th><th>최종확정</th><th></th></tr></thead>
          <tbody><tr><td colspan="6" style="text-align:center; color: var(--gray-400);">불러오는 중…</td></tr></tbody>
        </table>
      </div>
      <div class="modal-actions" style="justify-content:flex-start;">
        <button class="btn btn-primary btn-sm" data-open-new-diag="${f.id}">+ 새 진단 등록(현장 방문)</button>
      </div>
      <div class="hidden" id="c-new-diag-form-${f.id}" style="margin-top:12px; padding-top:12px; border-top:1px solid var(--gray-100);">
        <label>진단 유형</label>
        <select id="c-diag-type-${f.id}">
          ${diagnosisTypeOptions.map((t) => `<option value="${t}">${t}</option>`).join("")}
        </select>
        <label>피해 부위 사진 (현장 촬영)</label>
        <input type="file" accept="image/*" capture="environment" id="c-diag-photo-${f.id}" />
        <div class="modal-actions">
          <button class="btn btn-ghost btn-sm" data-cancel-new-diag="${f.id}">취소</button>
          <button class="btn btn-primary btn-sm" data-submit-new-diag="${f.id}">등록</button>
        </div>
      </div>
    `;
    container.appendChild(card);
    loadConsultantFarmDiagnoses(f.id);
  });

  container.querySelectorAll("button[data-open-new-diag]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.getElementById(`c-new-diag-form-${btn.dataset.openNewDiag}`).classList.remove("hidden");
    });
  });
  container.querySelectorAll("button[data-cancel-new-diag]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.getElementById(`c-new-diag-form-${btn.dataset.cancelNewDiag}`).classList.add("hidden");
    });
  });
  container.querySelectorAll("button[data-submit-new-diag]").forEach((btn) => {
    btn.addEventListener("click", () => submitConsultantNewDiagnosis(btn.dataset.submitNewDiag));
  });
}

function loadConsultantFarmDiagnoses(farmId) {
  ConsultantApi.getDiagnoses(farmId)
    .then((diagnoses) => {
      const tbody = document.querySelector(`#c-diag-table-${farmId} tbody`);
      tbody.innerHTML = "";
      if (diagnoses.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color: var(--gray-400);">등록된 진단 기록이 없습니다.</td></tr>`;
        return;
      }
      diagnoses.forEach((d) => {
        const tr = document.createElement("tr");
        const finalText = d.final_disease_name
          ? `${d.final_disease_name} (${d.final_diagnosis_source === "consultant" ? "본인" : d.final_diagnosis_source})`
          : "-";
        tr.innerHTML = `
          <td>${d.occurrence_date}</td>
          <td>${d.ai_disease_name || "-"}</td>
          <td>${d.ai_confidence != null ? Math.round(d.ai_confidence * 100) + "%" : "-"}</td>
          <td>${d.created_by_type === "consultant" ? `👤 ${d.created_by_consultant_name || "컨설턴트"}` : "농가"}</td>
          <td>${finalText}</td>
          <td>
            <button class="btn btn-ghost btn-sm" data-edit-diag="${d.id}">현장 확인 정정</button>
            <button class="btn btn-ghost btn-sm" data-comment-diag="${d.id}">💬 코멘트</button>
          </td>
        `;
        tbody.appendChild(tr);
      });
      tbody.querySelectorAll("button[data-edit-diag]").forEach((btn) => {
        btn.addEventListener("click", () => openConsultantFinalDiagnosisPrompt(btn.dataset.editDiag, farmId));
      });
      tbody.querySelectorAll("button[data-comment-diag]").forEach((btn) => {
        btn.addEventListener("click", () => openConsultantCommentModal(btn.dataset.commentDiag));
      });
    })
    .catch((e) => {
      if (e.isAuthError) handleConsultantLogout();
    });
}

async function openConsultantFinalDiagnosisPrompt(diagnosisId, farmId) {
  const diseaseName = prompt("현장에서 확인한 진단명(병해충명)을 입력해주세요:");
  if (!diseaseName) return;
  const note = prompt("메모(선택, 없으면 빈 칸으로 확인):") || "";
  try {
    await ConsultantApi.submitFinalDiagnosis(diagnosisId, diseaseName, note);
    showToast("현장 확인 진단이 반영되었습니다.");
    loadConsultantFarmDiagnoses(farmId);
  } catch (e) {
    if (e.isAuthError) {
      handleConsultantLogout();
      return;
    }
    showToast(`정정 실패: ${e.message}`, true);
  }
}

async function submitConsultantNewDiagnosis(farmId) {
  const type = document.getElementById(`c-diag-type-${farmId}`).value;
  const photoInput = document.getElementById(`c-diag-photo-${farmId}`);
  const file = photoInput.files[0];
  if (!file) {
    showToast("피해 부위 사진을 촬영하거나 선택해주세요.", true);
    return;
  }
  const formData = new FormData();
  formData.append("farm_id", farmId);
  formData.append("diagnosis_type", type);
  formData.append("photos", file);

  try {
    await ConsultantApi.createDiagnosis(formData);
    showToast("새 진단이 등록되었습니다.");
    document.getElementById(`c-new-diag-form-${farmId}`).classList.add("hidden");
    photoInput.value = "";
    loadConsultantFarmDiagnoses(farmId);
  } catch (e) {
    if (e.isAuthError) {
      handleConsultantLogout();
      return;
    }
    showToast(`진단 등록 실패: ${e.message}`, true);
  }
}

// ---------- 코멘트 ----------
let currentCommentDiagnosisId = null;

function openConsultantCommentModal(diagnosisId) {
  currentCommentDiagnosisId = diagnosisId;
  document.getElementById("consultantCommentSub").textContent = `진단 #${diagnosisId}`;
  document.getElementById("consultantCommentBody").value = "";
  document.getElementById("consultantCommentList").innerHTML = "불러오는 중…";
  document.getElementById("consultantCommentModal").classList.remove("hidden");
  loadConsultantComments(diagnosisId);
}

function closeConsultantCommentModal() {
  document.getElementById("consultantCommentModal").classList.add("hidden");
  currentCommentDiagnosisId = null;
}

function renderConsultantComments(comments) {
  const listEl = document.getElementById("consultantCommentList");
  if (comments.length === 0) {
    listEl.innerHTML = `<p style="color: var(--gray-400);">아직 코멘트가 없습니다.</p>`;
    return;
  }
  listEl.innerHTML = comments
    .map((c) => {
      const badge = c.author_type === "consultant" ? "👤 컨설턴트" : "🌾 농가";
      const when = new Date(c.created_at).toLocaleString("ko-KR");
      return `
        <div style="padding:8px 0; border-bottom:1px solid var(--gray-100);">
          <div style="font-size:12px; color: var(--gray-400);">${badge} · ${c.author_name} · ${when}</div>
          <div>${c.body.replace(/</g, "&lt;")}</div>
        </div>
      `;
    })
    .join("");
}

function loadConsultantComments(diagnosisId) {
  ConsultantApi.getComments(diagnosisId)
    .then(renderConsultantComments)
    .catch((e) => {
      if (e.isAuthError) {
        handleConsultantLogout();
        return;
      }
      document.getElementById("consultantCommentList").innerHTML = `<p style="color: var(--danger, red);">불러오기 실패: ${e.message}</p>`;
    });
}

async function submitConsultantComment() {
  const body = document.getElementById("consultantCommentBody").value.trim();
  if (!body || !currentCommentDiagnosisId) return;
  try {
    await ConsultantApi.createComment(currentCommentDiagnosisId, body);
    document.getElementById("consultantCommentBody").value = "";
    loadConsultantComments(currentCommentDiagnosisId);
  } catch (e) {
    if (e.isAuthError) {
      handleConsultantLogout();
      return;
    }
    showToast(`코멘트 등록 실패: ${e.message}`, true);
  }
}

function backToConsultantHouseholdList() {
  document.getElementById("consultantHouseholdDetailPanel").classList.add("hidden");
  document.getElementById("consultantHouseholdListPanel").classList.remove("hidden");
}

// ---------- 내 활동 통계 ----------
// 컨설턴트 본인 화면과 관리자가 특정 컨설턴트 통계를 보는 모달(dashboard.js
// openConsultantStatsModal)이 동일한 렌더링 로직을 공유한다.
function renderConsultantStatsHtml(s) {
  const total = s.farmer_feedback_correct + s.farmer_feedback_incorrect + s.farmer_feedback_pending;
  return `
    <div class="cards-grid">
      <div class="stat-card"><div><div class="stat-value">${s.household_count}</div><div class="stat-label">담당 농가 수</div></div></div>
      <div class="stat-card"><div><div class="stat-value">${s.farm_count}</div><div class="stat-label">담당 농장 수</div></div></div>
      <div class="stat-card"><div><div class="stat-value">${s.my_diagnosis_count}</div><div class="stat-label">본인 등록 진단 건수</div></div></div>
      <div class="stat-card"><div><div class="stat-value">${s.my_final_diagnosis_count}</div><div class="stat-label">본인 최종확정 건수</div></div></div>
      <div class="stat-card"><div><div class="stat-value">${s.my_comment_count}</div><div class="stat-label">남긴 코멘트 수</div></div></div>
      <div class="stat-card"><div><div class="stat-value">${s.total_diagnosis_count}</div><div class="stat-label">담당 농가 전체 진단 건수</div></div></div>
    </div>
    <div class="panel-sub" style="margin-top:14px;">담당 농가 AI 진단 피드백 (총 ${total}건 중 확인됨)</div>
    <div style="margin-top:6px;">
      <span class="badge badge-low">일치 ${s.farmer_feedback_correct}건</span>
      <span class="badge badge-high" style="margin-left:6px;">불일치 ${s.farmer_feedback_incorrect}건</span>
      <span class="badge" style="margin-left:6px; background:#eee; color:#666;">미확인 ${s.farmer_feedback_pending}건</span>
    </div>
  `;
}

function loadConsultantStats() {
  const body = document.getElementById("consultantStatsBody");
  body.textContent = "불러오는 중…";
  ConsultantApi.getStats()
    .then((stats) => {
      body.innerHTML = renderConsultantStatsHtml(stats);
    })
    .catch((e) => {
      if (e.isAuthError) {
        handleConsultantLogout();
        return;
      }
      body.textContent = `통계를 불러오지 못했습니다: ${e.message}`;
    });
}

// ---------- 초기화 ----------
function initConsultant() {
  document.getElementById("switchToConsultantLogin").addEventListener("click", showConsultantLoginForm);
  document.getElementById("switchToAdminLogin").addEventListener("click", showAdminLoginForm);
  document.getElementById("consultantLoginForm").addEventListener("submit", handleConsultantLoginSubmit);
  document.getElementById("consultantLogoutBtn").addEventListener("click", handleConsultantLogout);
  document.getElementById("consultantBackToHouseholds").addEventListener("click", backToConsultantHouseholdList);
  document.getElementById("consultantCommentCancel").addEventListener("click", closeConsultantCommentModal);
  document.getElementById("consultantCommentSubmit").addEventListener("click", submitConsultantComment);
  initConsultantNav();

  if (ConsultantApi.isLoggedIn()) {
    showConsultantAppShell();
    loadConsultantAll();
  }
}

document.addEventListener("DOMContentLoaded", initConsultant);
