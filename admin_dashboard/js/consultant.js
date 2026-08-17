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
    updateHousehold: (householdId, payload) =>
      request(`/api/consultant/households/${householdId}`, { method: "PATCH", body: JSON.stringify(payload) }),
    updateHouseholdUser: (userId, payload) =>
      request(`/api/consultant/users/${userId}`, { method: "PATCH", body: JSON.stringify(payload) }),
    getDiagnoses: (farmId) => request(`/api/consultant/diagnoses?farm_id=${farmId}`),
    getDiagnosisDetail: (diagnosisId) => request(`/api/consultant/diagnoses/${diagnosisId}`),
    createDiagnosis: (formData) => requestMultipart("/api/consultant/diagnoses", "POST", formData),
    submitFinalDiagnosis: (diagnosisId, diseaseName, note) =>
      request(`/api/consultant/diagnoses/${diagnosisId}/final-diagnosis`, {
        method: "PATCH",
        body: JSON.stringify({ disease_name: diseaseName, note: note || null }),
      }),
    getComments: (diagnosisId) => request(`/api/consultant/diagnoses/${diagnosisId}/comments`),
    getReference: () => request("/api/consultant/reference"),
    getStats: () => request("/api/consultant/stats/summary"),
    getOverviewSummary: (cropId) => {
      const qs = new URLSearchParams();
      if (cropId) qs.set("crop_id", cropId);
      const query = qs.toString();
      return request(`/api/consultant/overview/summary${query ? `?${query}` : ""}`);
    },
    getOverviewRegionalStats: (cropId) => {
      const qs = new URLSearchParams();
      if (cropId) qs.set("crop_id", cropId);
      const query = qs.toString();
      return request(`/api/consultant/overview/regional-stats${query ? `?${query}` : ""}`);
    },
    createComment: (diagnosisId, body) =>
      request(`/api/consultant/diagnoses/${diagnosisId}/comments`, {
        method: "POST",
        body: JSON.stringify({ body }),
      }),
    listCommunityPosts: () => request("/api/consultant/community/posts"),
    getCommunityPost: (postId) => request(`/api/consultant/community/posts/${postId}`),
    createChannelPost: (title, body, cropId, visibility) =>
      request("/api/consultant/community/posts", {
        method: "POST",
        body: JSON.stringify({ title, body: body || null, crop_id: cropId || null, visibility }),
      }),
    createCommunityComment: (postId, body) =>
      request(`/api/consultant/community/posts/${postId}/comments`, {
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
  const titles = {
    "c-households": "담당 농가",
    "c-community": "커뮤니티",
    "c-region-stats": "지역/현황 통계",
    "c-stats": "내 활동 통계",
  };
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
      if (section === "c-region-stats") loadConsultantRegionStats();
      if (section === "c-community") loadConsultantCommunity();
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

// 관리자 대시보드의 renderHouseholdAccountInfo와 동일한 카드/여백 스타일(account-info-row)을
// 재사용한다. 비밀번호 초기화·정지·탈퇴는 이번 범위 밖이라 이름/전화번호 수정만 둔다.
function renderConsultantHouseholdAccountInfo(container, household) {
  const panel = document.createElement("div");
  panel.className = "panel";
  const memberRows = household.members
    .map(
      (m) => `
    <div class="account-info-row">
      <span>${m.name} · ${m.phone}</span>
      <button class="btn btn-ghost btn-sm" data-c-edit-user="${m.id}">정보 수정</button>
    </div>`
    )
    .join("");
  panel.innerHTML = `
    <div class="panel-header">
      <h2>계정 정보</h2>
      <span class="panel-sub">농가명·대표자 정보를 직접 수정할 수 있습니다</span>
    </div>
    <div class="account-info-row">
      <span><strong>${household.name}</strong> (농가명) · 가입코드 ${household.join_code}</span>
      <button class="btn btn-ghost btn-sm" id="cEditHouseholdNameBtn">정보 수정</button>
    </div>
    ${memberRows}
  `;
  container.appendChild(panel);

  panel.querySelector("#cEditHouseholdNameBtn").addEventListener("click", () => {
    openEditInfoModal("consultant-household", household.id, household.name, null, false, "농가명 수정", () =>
      reloadConsultantHouseholdDetail(household.id)
    );
  });
  panel.querySelectorAll("[data-c-edit-user]").forEach((btn) => {
    const member = household.members.find((m) => m.id === Number(btn.dataset.cEditUser));
    btn.addEventListener("click", () => {
      openEditInfoModal("consultant-user", member.id, member.name, member.phone, true, "대표자 정보 수정", () =>
        reloadConsultantHouseholdDetail(household.id)
      );
    });
  });
}

// 정보 수정 후 목록(consultantHouseholds 캐시)을 새로 받아와 같은 농가 상세를 다시 그린다.
function reloadConsultantHouseholdDetail(householdId) {
  ConsultantApi.getHouseholds()
    .then((households) => {
      consultantHouseholds = households;
      showConsultantHouseholdDetail(householdId);
    })
    .catch((e) => {
      if (e.isAuthError) handleConsultantLogout();
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
  renderConsultantHouseholdAccountInfo(container, household);
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
        <label class="field-label">진단 유형</label>
        <select class="field-input" id="c-diag-type-${f.id}">
          ${diagnosisTypeOptions.map((t) => `<option value="${t}">${t}</option>`).join("")}
        </select>
        <label class="field-label">피해 부위 사진 (현장 촬영)</label>
        <input class="field-input" type="file" accept="image/*" capture="environment" id="c-diag-photo-${f.id}" />
        <p style="font-size:11px; color: var(--gray-500); margin: 4px 0 0;">사진을 등록하면 AI가 자동으로 1차 진단합니다. 결과 확인 후 필요하면 정정해주세요.</p>
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
        tr.className = "clickable-row";
        const finalText = d.final_disease_name
          ? `${d.final_disease_name} (${d.final_diagnosis_source === "consultant" ? "본인" : d.final_diagnosis_source})`
          : "-";
        const estimatedMark = d.photo_taken_at_estimated
          ? ` <span class="badge badge-mid" title="촬영시각 확인 불가로 업로드 시각 기준 발생일입니다">추정</span>`
          : "";
        tr.innerHTML = `
          <td>${d.occurrence_date}${estimatedMark}</td>
          <td>${d.ai_disease_name || "-"}</td>
          <td>${d.ai_confidence != null ? Math.round(d.ai_confidence * 100) + "%" : "-"}</td>
          <td>${d.created_by_type === "consultant" ? `👤 ${d.created_by_consultant_name || "컨설턴트"}` : "농가"}</td>
          <td>${finalText}</td>
          <td>
            <button class="btn btn-ghost btn-sm" data-edit-diag="${d.id}" data-name="${(d.final_disease_name || "").replace(/"/g, "&quot;")}" data-note="${(d.final_diagnosis_note || "").replace(/"/g, "&quot;")}">현장 확인 정정</button>
            <button class="btn btn-ghost btn-sm" data-comment-diag="${d.id}">💬 코멘트</button>
          </td>
        `;
        // 행 자체를 클릭하면 상세 모달이 뜨도록 하되, 안의 두 버튼(현장 확인 정정/코멘트)을
        // 클릭했을 때는 그 버튼 자체의 동작만 실행되고 상세 모달이 같이 뜨지 않게 막는다.
        tr.addEventListener("click", (e) => {
          if (e.target.closest("button")) return;
          openConsultantDiagnosisDetailModal(d.id);
        });
        tbody.appendChild(tr);
      });
      tbody.querySelectorAll("button[data-edit-diag]").forEach((btn) => {
        btn.addEventListener("click", () =>
          openConsultantFinalDiagnosisModal(btn.dataset.editDiag, farmId, btn.dataset.name, btn.dataset.note)
        );
      });
      tbody.querySelectorAll("button[data-comment-diag]").forEach((btn) => {
        btn.addEventListener("click", () => openConsultantCommentModal(btn.dataset.commentDiag));
      });
    })
    .catch((e) => {
      if (e.isAuthError) handleConsultantLogout();
    });
}

// 관리자 대시보드와 완전히 같은 모달(#diagnosisDetailModal)/렌더 함수(renderDiagnosisDetailBody,
// dashboard.js)를 그대로 재사용한다 - 그 모달은 특정 화면(appShell)에 속하지 않고 body
// 최상위에 있어서 컨설턴트 화면에서도 그대로 열고 닫을 수 있다. 관리자 쪽은 Api(관리자
// 토큰)로 조회하지만 여기서는 ConsultantApi(컨설턴트 토큰)로 조회한다는 점만 다르다.
function openConsultantDiagnosisDetailModal(diagnosisId) {
  if (!diagnosisId) return;
  document.getElementById("diagnosisDetailModal").classList.remove("hidden");
  document.getElementById("diagnosisDetailSub").textContent = `진단 #${diagnosisId}`;
  document.getElementById("diagnosisDetailBody").innerHTML = "불러오는 중…";
  ConsultantApi.getDiagnosisDetail(diagnosisId)
    .then(renderDiagnosisDetailBody)
    .catch((e) => {
      if (e.isAuthError) {
        document.getElementById("diagnosisDetailModal").classList.add("hidden");
        handleConsultantLogout();
        return;
      }
      document.getElementById("diagnosisDetailBody").innerHTML = `불러오기 실패: ${e.message}`;
    });
}

// ---------- 현장 확인 정정 (admin의 expertDiagnosisModal과 동일한 패턴) ----------
let consultantFinalDiagnosisTargetId = null;
let consultantFinalDiagnosisFarmId = null;

let consultantFinalDiagnosisNameOptionsLoaded = false;

function ensureConsultantFinalDiagnosisNameOptions() {
  if (consultantFinalDiagnosisNameOptionsLoaded) return;
  consultantFinalDiagnosisNameOptionsLoaded = true;
  ConsultantApi.getReference()
    .then((refs) => {
      const names = [...new Set(refs.map((r) => r.name_kr))];
      document.getElementById("consultantFinalDiagnosisNameList").innerHTML = names
        .map((n) => `<option value="${n.replace(/"/g, "&quot;")}"></option>`)
        .join("");
    })
    .catch(() => {
      consultantFinalDiagnosisNameOptionsLoaded = false;
    });
}

function openConsultantFinalDiagnosisModal(diagnosisId, farmId, currentName, currentNote) {
  consultantFinalDiagnosisTargetId = diagnosisId;
  consultantFinalDiagnosisFarmId = farmId;
  document.getElementById("consultantFinalDiagnosisSub").textContent = `진단 #${diagnosisId}`;
  document.getElementById("consultantFinalDiagnosisName").value = currentName || "";
  document.getElementById("consultantFinalDiagnosisNote").value = currentNote || "";
  document.getElementById("consultantFinalDiagnosisModal").classList.remove("hidden");
  ensureConsultantFinalDiagnosisNameOptions();
}

function closeConsultantFinalDiagnosisModal() {
  document.getElementById("consultantFinalDiagnosisModal").classList.add("hidden");
  consultantFinalDiagnosisTargetId = null;
  consultantFinalDiagnosisFarmId = null;
}

async function submitConsultantFinalDiagnosis() {
  const name = document.getElementById("consultantFinalDiagnosisName").value.trim();
  const note = document.getElementById("consultantFinalDiagnosisNote").value.trim();
  if (!name) {
    showToast("진단명을 입력해주세요.", true);
    return;
  }
  const targetId = consultantFinalDiagnosisTargetId;
  const farmId = consultantFinalDiagnosisFarmId;
  try {
    await ConsultantApi.submitFinalDiagnosis(targetId, name, note);
    showToast("현장 확인 진단이 반영되었습니다.");
    closeConsultantFinalDiagnosisModal();
    if (farmId) loadConsultantFarmDiagnoses(farmId);
  } catch (e) {
    if (e.isAuthError) {
      closeConsultantFinalDiagnosisModal();
      handleConsultantLogout();
      return;
    }
    showToast(`정정 실패: ${e.message}`, true);
  }
}

// ---------- 새 진단 등록 + AI 1차 진단 결과 즉시 표시 ----------
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
    const diagnosis = await ConsultantApi.createDiagnosis(formData);
    document.getElementById(`c-new-diag-form-${farmId}`).classList.add("hidden");
    photoInput.value = "";
    loadConsultantFarmDiagnoses(farmId);
    openConsultantAiResultModal(diagnosis, farmId);
  } catch (e) {
    if (e.isAuthError) {
      handleConsultantLogout();
      return;
    }
    showToast(`진단 등록 실패: ${e.message}`, true);
  }
}

function openConsultantAiResultModal(diagnosis, farmId) {
  document.getElementById("consultantAiResultSub").textContent = `진단 #${diagnosis.id}`;
  const confidenceText =
    diagnosis.ai_confidence != null ? `확신도 ${Math.round(diagnosis.ai_confidence * 100)}%` : "확신도 정보 없음";
  document.getElementById("consultantAiResultBody").innerHTML = `
    <p style="font-size:15px; font-weight:700; margin-bottom:4px;">${diagnosis.ai_disease_name || "AI가 병해충을 특정하지 못했습니다"}</p>
    <p style="font-size:12.5px; color: var(--gray-600);">${confidenceText}</p>
    ${diagnosis.ai_symptoms ? `<p style="font-size:12.5px; color: var(--gray-600); margin-top:8px;">${diagnosis.ai_symptoms}</p>` : ""}
    <p style="font-size:11.5px; color: var(--gray-400); margin-top:10px;">AI 1차 진단 결과입니다. 현장에서 확인한 실제 병해충명과 다르면 "현장 확인 정정하기"로 바로잡아주세요.</p>
  `;
  document.getElementById("consultantAiResultCorrect").onclick = () => {
    closeConsultantAiResultModal();
    openConsultantFinalDiagnosisModal(diagnosis.id, farmId, diagnosis.final_disease_name, diagnosis.final_diagnosis_note);
  };
  document.getElementById("consultantAiResultModal").classList.remove("hidden");
}

function closeConsultantAiResultModal() {
  document.getElementById("consultantAiResultModal").classList.add("hidden");
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

// ---------- 커뮤니티 ----------
let consultantCropOptionsLoaded = false;

function ensureConsultantCropOptions() {
  if (consultantCropOptionsLoaded) return;
  consultantCropOptionsLoaded = true;
  Api.listCrops()
    .then((crops) => {
      const select = document.getElementById("consultantPostCropId");
      crops.forEach((c) => {
        const opt = document.createElement("option");
        opt.value = c.id;
        opt.textContent = c.name_kr;
        select.appendChild(opt);
      });
    })
    .catch(() => {});
}

function loadConsultantCommunity() {
  ensureConsultantCropOptions();
  const list = document.getElementById("consultantCommunityList");
  list.innerHTML = `<p style="color: var(--gray-400);">불러오는 중…</p>`;
  ConsultantApi.listCommunityPosts()
    .then(renderConsultantCommunityList)
    .catch((e) => {
      if (e.isAuthError) {
        handleConsultantLogout();
        return;
      }
      list.innerHTML = `<p style="color: var(--gray-400);">불러오기 실패: ${e.message}</p>`;
    });
}

function renderConsultantCommunityList(posts) {
  const list = document.getElementById("consultantCommunityList");
  list.innerHTML = "";
  if (posts.length === 0) {
    list.innerHTML = `<p class="panel-sub">아직 게시글이 없습니다.</p>`;
    return;
  }
  posts.forEach((p) => {
    const card = document.createElement("div");
    card.className = "community-post-card";
    const kindLabel = p.kind === "channel" ? "📢 공지/팁" : p.kind === "diagnosis_share" ? "🩺 진단 공유" : "게시글";
    const visBadgeClass = p.visibility === "public" ? "badge-low" : "badge-mid";
    const visLabel = p.visibility === "public" ? "전체 공개" : "담당 농가 공개";
    card.innerHTML = `
      <h3 class="community-post-title">${p.title}</h3>
      <div class="community-post-meta">
        <span class="badge badge-low">${kindLabel}</span>
        <span class="badge ${visBadgeClass}">${visLabel}</span>
        <span>${p.author_name} · 댓글 ${p.comment_count}개</span>
      </div>
      <div class="community-post-body">${(p.body || "").replace(/</g, "&lt;")}</div>
      <div id="c-community-detail-${p.id}" class="hidden community-post-detail"></div>
      <div class="modal-actions" style="justify-content:flex-start;">
        <button class="btn btn-ghost btn-sm" data-toggle-post="${p.id}">댓글 보기/작성</button>
      </div>
    `;
    list.appendChild(card);
  });
  list.querySelectorAll("button[data-toggle-post]").forEach((btn) => {
    btn.addEventListener("click", () => toggleConsultantCommunityDetail(btn.dataset.togglePost));
  });
}

function toggleConsultantCommunityDetail(postId) {
  const container = document.getElementById(`c-community-detail-${postId}`);
  const wasHidden = container.classList.contains("hidden");
  container.classList.toggle("hidden");
  if (wasHidden) loadConsultantCommunityDetail(postId);
}

function loadConsultantCommunityDetail(postId) {
  const container = document.getElementById(`c-community-detail-${postId}`);
  container.innerHTML = "불러오는 중…";
  ConsultantApi.getCommunityPost(postId)
    .then((post) => {
      const commentsHtml = post.comments.length
        ? post.comments
            .map((c) => {
              const badge = c.author_type === "consultant" ? "👤 컨설턴트" : "🌾 농가";
              return `<div class="community-comment-item">
                <div class="community-comment-meta">${badge} · ${c.author_name} · ${new Date(c.created_at).toLocaleString("ko-KR")}</div>
                <div>${c.body.replace(/</g, "&lt;")}</div>
              </div>`;
            })
            .join("")
        : `<p class="panel-sub">아직 댓글이 없습니다.</p>`;
      container.innerHTML = `
        <div>${commentsHtml}</div>
        <div class="community-comment-form">
          <input class="field-input" type="text" id="c-community-comment-input-${postId}" placeholder="댓글을 입력하세요" />
          <button class="btn btn-primary btn-sm" data-submit-comment="${postId}">등록</button>
        </div>
      `;
      container.querySelector(`button[data-submit-comment="${postId}"]`).addEventListener("click", () => {
        submitConsultantCommunityComment(postId);
      });
    })
    .catch((e) => {
      if (e.isAuthError) {
        handleConsultantLogout();
        return;
      }
      container.innerHTML = `불러오기 실패: ${e.message}`;
    });
}

async function submitConsultantCommunityComment(postId) {
  const input = document.getElementById(`c-community-comment-input-${postId}`);
  const body = input.value.trim();
  if (!body) return;
  try {
    await ConsultantApi.createCommunityComment(postId, body);
    input.value = "";
    loadConsultantCommunityDetail(postId);
  } catch (e) {
    if (e.isAuthError) {
      handleConsultantLogout();
      return;
    }
    showToast(`댓글 등록 실패: ${e.message}`, true);
  }
}

async function submitConsultantChannelPost() {
  const title = document.getElementById("consultantPostTitle").value.trim();
  const body = document.getElementById("consultantPostBody").value.trim();
  const cropId = document.getElementById("consultantPostCropId").value;
  const visibility = document.getElementById("consultantPostVisibility").value;
  if (!title) {
    showToast("제목을 입력해주세요.", true);
    return;
  }
  try {
    await ConsultantApi.createChannelPost(title, body, cropId, visibility);
    showToast("게시글이 등록되었습니다.");
    document.getElementById("consultantPostTitle").value = "";
    document.getElementById("consultantPostBody").value = "";
    document.getElementById("consultantPostCropId").value = "";
    loadConsultantCommunity();
  } catch (e) {
    if (e.isAuthError) {
      handleConsultantLogout();
      return;
    }
    showToast(`게시글 등록 실패: ${e.message}`, true);
  }
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

// ---------- 지역/현황 통계 (관리자 대시보드 종합현황·지역별발생현황과 같은 정보) ----------
let consultantRegionStatsCropOptionsLoaded = false;

function ensureConsultantRegionStatsCropOptions() {
  if (consultantRegionStatsCropOptionsLoaded) return Promise.resolve();
  consultantRegionStatsCropOptionsLoaded = true;
  return Api.listCrops()
    .then((crops) => {
      const select = document.getElementById("consultantRegionStatsCropSelect");
      crops.forEach((c) => {
        const opt = document.createElement("option");
        opt.value = c.id;
        opt.textContent = `${c.icon_emoji || ""} ${c.name_kr}`;
        select.appendChild(opt);
      });
    })
    .catch(() => {});
}

function loadConsultantRegionStats() {
  ensureConsultantRegionStatsCropOptions().then(() => {
    const cropId = document.getElementById("consultantRegionStatsCropSelect").value;
    Promise.all([ConsultantApi.getOverviewSummary(cropId), ConsultantApi.getOverviewRegionalStats(cropId)])
      .then(([summary, regional]) => {
        renderConsultantOverviewSummary(summary);
        renderConsultantRegionTable(regional);
      })
      .catch((e) => {
        if (e.isAuthError) {
          handleConsultantLogout();
          return;
        }
        showToast(`지역/현황 통계를 불러오지 못했습니다: ${e.message}`, true);
      });
  });
}

function renderConsultantOverviewSummary(summary) {
  document.getElementById("cRegionStatHouseholds").textContent = summary.total_households ?? "-";
  document.getElementById("cRegionStatWorkLogs").textContent = summary.total_work_logs;
  document.getElementById("cRegionStatDiagnoses").textContent = summary.total_diagnoses;
  const acc = summary.ai_vs_actual.accuracy_percent;
  document.getElementById("cRegionStatAccuracy").textContent = acc !== null ? `${acc}%` : "데이터 부족";

  const byType = summary.diagnoses_by_type || {};
  const total = Object.values(byType).reduce((a, b) => a + b, 0);
  const byTypeEl = document.getElementById("cRegionStatByType");
  byTypeEl.innerHTML = total
    ? Object.entries(byType)
        .map(([type, count]) => `<span class="${typeBadgeClass(type)}" style="margin-right:8px;">${type} ${count}건</span>`)
        .join("")
    : "데이터가 없습니다.";
}

function renderConsultantRegionTable(regional) {
  const tbody = document.querySelector("#cRegionStatsTable tbody");
  tbody.innerHTML = regional.length
    ? regional
        .map(
          (r) => `<tr>
        <td><strong>${r.region}</strong></td>
        <td>${r.total_display}</td>
        <td>${r.top_issue || "-"}</td>
        <td>${Object.entries(r.by_type).map(([t, c]) => `${t} ${c}`).join(" · ") || "-"}</td>
        <td>${Object.entries(r.by_crop).map(([c, n]) => `${c} ${n}`).join(" · ") || "-"}</td>
      </tr>`
        )
        .join("")
    : `<tr><td colspan="5" style="text-align:center; color: var(--gray-400);">데이터가 없습니다.</td></tr>`;
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
  document.getElementById("consultantFinalDiagnosisCancel").addEventListener("click", closeConsultantFinalDiagnosisModal);
  document.getElementById("consultantFinalDiagnosisSubmit").addEventListener("click", submitConsultantFinalDiagnosis);
  document.getElementById("consultantFinalDiagnosisModal").addEventListener("click", (e) => {
    if (e.target.id === "consultantFinalDiagnosisModal") closeConsultantFinalDiagnosisModal();
  });
  document.getElementById("consultantAiResultClose").addEventListener("click", closeConsultantAiResultModal);
  document.getElementById("consultantAiResultModal").addEventListener("click", (e) => {
    if (e.target.id === "consultantAiResultModal") closeConsultantAiResultModal();
  });
  document.getElementById("consultantPostSubmit").addEventListener("click", submitConsultantChannelPost);
  document.getElementById("consultantRegionStatsCropSelect").addEventListener("change", loadConsultantRegionStats);
  initConsultantNav();

  if (ConsultantApi.isLoggedIn()) {
    showConsultantAppShell();
    loadConsultantAll();
  }
}

document.addEventListener("DOMContentLoaded", initConsultant);
