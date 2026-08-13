const Api = (() => {
  let baseUrl = localStorage.getItem("apiBaseUrl") || "http://localhost:8000";

  function setBaseUrl(url) {
    baseUrl = url.replace(/\/$/, "");
    localStorage.setItem("apiBaseUrl", baseUrl);
  }

  function getBaseUrl() {
    return baseUrl;
  }

  async function request(path, options = {}) {
    const res = await fetch(`${baseUrl}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`API 오류 (${res.status}): ${text}`);
    }
    return res.json();
  }

  return {
    setBaseUrl,
    getBaseUrl,
    health: () => request("/api/health"),
    getStatsSummary: () => request("/api/stats/summary"),
    getFarmsOverview: () => request("/api/admin/farms/overview"),
    getRegionalStats: () => request("/api/admin/regional-stats"),
    getFeed: (limit = 30) => request(`/api/admin/feed?limit=${limit}`),
    getNotifications: () => request("/api/admin/notifications"),
    sendNotification: (payload) =>
      request("/api/admin/notifications", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  };
})();
