import axios from 'axios';

// Reads from .env (Vercel) or .env.local (local dev)
// Production:  VITE_API_BASE_URL = https://microfinancce-ai.onrender.com/api
// Local dev:   VITE_API_BASE_URL = http://localhost:5001/api
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://microfinancce-ai.onrender.com/api';

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
    withCredentials: false,   // must be false when backend uses wildcard/list origins
});

// ─── Conversational endpoint ──────────────────────────────────────────────────

export const askQuestion = async (question) => {
    try {
        const response = await api.post('/ask', { question });
        return response.data;
    } catch (error) {
        throw error.response?.data || error.message;
    }
};

// ─── Data endpoints ───────────────────────────────────────────────────────────

export const uploadCSV = async (file) => {
    try {
        const formData = new FormData();
        formData.append('file', file);
        const response = await api.post('/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
        return response.data;
    } catch (error) {
        throw error.response?.data || error.message;
    }
};

export const getStats = async () => {
    try {
        const response = await api.get('/stats');
        return response.data;
    } catch (error) {
        throw error.response?.data || error.message;
    }
};

export const getClients = async (limit = 100, offset = 0, search = null) => {
    try {
        const params = { limit, offset };
        if (search) params.search = search;
        const response = await api.get('/clients', { params });
        return response.data;
    } catch (error) {
        throw error.response?.data || error.message;
    }
};

export const getGroups = async (limit = 100, offset = 0, search = null) => {
    try {
        const params = { limit, offset };
        if (search) params.search = search;
        const response = await api.get('/groups', { params });
        return response.data;
    } catch (error) {
        throw error.response?.data || error.message;
    }
};

// ─── Analysis endpoints ───────────────────────────────────────────────────────

export const getInsights = async () => {
    try {
        const response = await api.get('/analyze/insights');
        return response.data;
    } catch (error) {
        throw error.response?.data || error.message;
    }
};

export const getTopClients = async (limit = 10) => {
    try {
        const response = await api.get('/analyze/top-clients', { params: { limit } });
        return response.data;
    } catch (error) {
        throw error.response?.data || error.message;
    }
};

export const getTopGroups = async (limit = 10) => {
    try {
        const response = await api.get('/analyze/top-groups', { params: { limit } });
        return response.data;
    } catch (error) {
        throw error.response?.data || error.message;
    }
};

export const getRiskAnalysis = async (threshold = 3) => {
    try {
        const response = await api.get('/analyze/risk-analysis', { params: { threshold } });
        return response.data;
    } catch (error) {
        throw error.response?.data || error.message;
    }
};

export const getBusinessPerformance = async () => {
    try {
        const response = await api.get('/analyze/business-performance');
        return response.data;
    } catch (error) {
        throw error.response?.data || error.message;
    }
};

export const analyzeClient = async (clientName) => {
    try {
        const response = await api.post('/analyze/client', { client_name: clientName });
        return response.data;
    } catch (error) {
        throw error.response?.data || error.message;
    }
};

export const analyzeGroup = async (groupName) => {
    try {
        const response = await api.post('/analyze/group', { group_name: groupName });
        return response.data;
    } catch (error) {
        throw error.response?.data || error.message;
    }
};

// ─── Document Verification endpoint ──────────────────────────────────────────

export const verifyDocument = async (imageFile) => {
    try {
        const data = new FormData();
        data.append('document', imageFile);
        const response = await api.post('/verify-document', data, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
        return response.data;
    } catch (error) {
        throw error.response?.data || error.message;
    }
};

// ─── NID / VoterID Scanner endpoint ──────────────────────────────────────────

export const scanIDCard = async (imageFile) => {
    try {
        const data = new FormData();
        data.append('id_image', imageFile);
        const response = await api.post('/scan-id', data, {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 60000,
        });
        return response.data;
    } catch (error) {
        throw error.response?.data || error.message;
    }
};

// ─── Evaluation endpoint ──────────────────────────────────────────────────────

export const evaluateApplicant = async (formData, pdfFile) => {
    try {
        const data = new FormData();
        Object.keys(formData).forEach((key) => data.append(key, formData[key]));
        data.append('bankStatement', pdfFile);

        const response = await api.post('/evaluate', data, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
        return response.data;
    } catch (error) {
        throw error.response?.data || error.message;
    }
};

export default api;
