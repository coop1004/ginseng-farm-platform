const Api = (() => {
  let baseUrl = localStorage.getItem("apiBaseUrl") || "https://ginseng-farm-platform.onrender.com";
  let adminToken = localStorage.getItem("adminToken") || null;

  function setBaseUrl(url) {
    baseUrl = url.replace(/\/$/, "");
    localStorage.setItem("apiBaseUrl", baseUrl);
  }

  function getBaseUrl() {
    return baseUrl;
  }

  function setToken(token) {
    adminToken = token;
    if (token) localStorage.setItem("adminToken", token);
    else localStorage.removeItem("adminToken");
  }

  function getToken() {
    return adminToken;
  }

  function isLoggedIn() {
    return !!adminToken;
  }

  async function request(path, options = {}, auth = true) {
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    if (auth && adminToken) headers["Authorization"] = `Bearer ${adminToken}`;

    const res = await fetch(`${baseUrl}${path}`, { ...options, headers });

    if (res.status === 401 && auth) {
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
    setBaseUrl,
    getBaseUrl,
    setToken,
    getToken,
    isLoggedIn,
    health: () => request("/api/health", {}, false),
    login: (username, password) =>
      request("/api/admin/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }, false),
    getStatsSummary: () => request("/api/admin/stats/summary"),
    getFarmsOverview: () => request("/api/admin/farms/overview"),
    getRegionalStats: (cropId) =>
      request(`/api/admin/regional-stats${cropId ? `?crop_id=${cropId}` : ""}`),
    listReferences: () => request("/api/admin/reference"),
    createReference: (payload) =>
      request("/api/admin/reference", { method: "POST", body: JSON.stringify(payload) }),
    updateReference: (id, payload) =>
      request(`/api/admin/reference/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
    deleteReference: (id) => request(`/api/admin/reference/${id}`, { method: "DELETE" }),
    listCrops: () => request("/api/crops", {}, false),
    getHouseholdCrops: (householdId) => request(`/api/admin/households/${householdId}/crops`),
    addHouseholdCrop: (householdId, cropId) =>
      request(`/api/admin/households/${householdId}/crops/${cropId}`, { method: "POST" }),
    removeHouseholdCrop: (householdId, cropId) =>
      request(`/api/admin/households/${householdId}/crops/${cropId}`, { method: "DELETE" }),
    listAgriMaterials: () => request("/api/admin/reference/agri-materials"),
    submitAdminFinalDiagnosis: (diagnosisId, diseaseName, note) =>
      request(`/api/admin/diagnoses/${diagnosisId}/final-diagnosis`, {
        method: "PATCH",
        body: JSON.stringify({ disease_name: diseaseName, note: note || null }),
      }),
    getWeatherHistory: (farmId, days = 30) => {
      const qs = new URLSearchParams({ days });
      if (farmId) qs.set("farm_id", farmId);
      return request(`/api/admin/weather/history?${qs.toString()}`);
    },
    getFeed: (limit = 30) => request(`/api/admin/feed?limit=${limit}`),
    getAdminDiagnoses: (params = {}) => {
      const qs = new URLSearchParams();
      Object.entries(params).forEach(([k, v]) => {
        if (v !== null && v !== undefined && v !== "") qs.set(k, v);
      });
      const query = qs.toString();
      return request(`/api/admin/diagnoses${query ? `?${query}` : ""}`);
    },
    getDiagnosisDetail: (diagnosisId) => request(`/api/admin/diagnoses/${diagnosisId}`),
    getNotifications: () => request("/api/admin/notifications"),
    sendNotification: (payload) =>
      request("/api/admin/notifications", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    broadcastNotification: (payload) =>
      request("/api/admin/notifications/broadcast", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    getMe: () => request("/api/admin/auth/me"),
    listAdmins: () => request("/api/admin/auth/list"),
    listOrganizations: () => request("/api/admin/organizations"),
    changePassword: (currentPassword, newPassword) =>
      request("/api/admin/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      }),
    registerAdmin: (username, password, name) =>
      request("/api/admin/auth/register", {
        method: "POST",
        body: JSON.stringify({ username, password, name }),
      }),
    deleteAdmin: (adminId) =>
      request(`/api/admin/auth/${adminId}`, { method: "DELETE" }),
    listConsultants: () => request("/api/admin/consultants"),
    registerConsultant: (username, password, name) =>
      request("/api/admin/consultants", { method: "POST", body: JSON.stringify({ username, password, name }) }),
    deleteConsultant: (consultantId) => request(`/api/admin/consultants/${consultantId}`, { method: "DELETE" }),
    getHouseholdConsultants: (householdId) => request(`/api/admin/households/${householdId}/consultants`),
    assignConsultantHousehold: (consultantId, householdId) =>
      request(`/api/admin/consultants/${consultantId}/households/${householdId}`, { method: "POST" }),
    unassignConsultantHousehold: (consultantId, householdId) =>
      request(`/api/admin/consultants/${consultantId}/households/${householdId}`, { method: "DELETE" }),
    getConsultantStats: (consultantId, { period, startDate, endDate } = {}) => {
      const params = new URLSearchParams();
      if (period) params.set("period", period);
      if (startDate) params.set("start_date", startDate);
      if (endDate) params.set("end_date", endDate);
      const qs = params.toString();
      return request(`/api/admin/consultants/${consultantId}/stats${qs ? `?${qs}` : ""}`);
    },
    getConsultantActivitySummary: ({ topN, period, startDate, endDate } = {}) => {
      const params = new URLSearchParams();
      if (topN) params.set("top_n", topN);
      if (period) params.set("period", period);
      if (startDate) params.set("start_date", startDate);
      if (endDate) params.set("end_date", endDate);
      const qs = params.toString();
      return request(`/api/admin/consultants/stats/summary${qs ? `?${qs}` : ""}`);
    },
    listCommunityReports: () => request("/api/admin/community/reports"),
    updateCommunityPostStatus: (postId, status) =>
      request(`/api/admin/community/posts/${postId}`, { method: "PATCH", body: JSON.stringify({ status }) }),
    deleteCommunityPost: (postId) => request(`/api/admin/community/posts/${postId}`, { method: "DELETE" }),
    updateCommunityCommentStatus: (commentId, status) =>
      request(`/api/admin/community/comments/${commentId}`, { method: "PATCH", body: JSON.stringify({ status }) }),
    deleteCommunityComment: (commentId) => request(`/api/admin/community/comments/${commentId}`, { method: "DELETE" }),
  };
})();
