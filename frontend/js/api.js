const BASE = "/api/v1";

export class ApiError extends Error {
    constructor(status, code, message, details) {
        super(message);
        this.status = status;
        this.code = code;
        this.details = details || {};
    }
}

async function request(path, options = {}) {
    let response;
    try {
        response = await fetch(BASE + path, options);
    } catch {
        throw new ApiError(0, "network_error", "Cannot reach the server. Is it running?");
    }
    if (response.status === 204) return null;

    let body = null;
    try { body = await response.json(); } catch { /* not JSON */ }

    if (!response.ok) {
        const err = body && body.error;
        throw new ApiError(
            response.status,
            err ? err.code : "http_error",
            err ? err.message : `Request failed (${response.status}).`,
            err ? err.details : {},
        );
    }
    return body;
}

const json = (method, data) => ({
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
});

export const api = {
    health: () => request("/health"),
    listDatasets: (limit = 50, offset = 0) => request(`/datasets?limit=${limit}&offset=${offset}`),
    getDataset: (id) => request(`/datasets/${id}`),
    getProfile: (id) => request(`/datasets/${id}/profile`),
    uploadDataset: (formData) => request("/datasets/upload", { method: "POST", body: formData }),
    listRules: (id) => request(`/datasets/${id}/rules`),
    createRule: (id, rule) => request(`/datasets/${id}/rules`, json("POST", rule)),
    updateRule: (ruleId, changes) => request(`/rules/${ruleId}`, json("PATCH", changes)),
    deleteRule: (ruleId) => request(`/rules/${ruleId}`, { method: "DELETE" }),
    createRun: (id, formData) => request(`/datasets/${id}/runs`, { method: "POST", body: formData }),
    listRuns: (id, limit = 50, offset = 0) => request(`/datasets/${id}/runs?limit=${limit}&offset=${offset}`),
    getRun: (id) => request(`/runs/${id}`),
};