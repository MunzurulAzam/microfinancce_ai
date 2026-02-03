import axios from 'axios';

const API_BASE_URL = 'http://localhost:5000/api';

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Ask endpoint - main feature
export const askQuestion = async (question) => {
    try {
        const response = await api.post('/ask', { question });
        return response.data;
    } catch (error) {
        throw error.response?.data || error.message;
    }
};

// Upload CSV
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

// Get statistics
export const getStats = async () => {
    try {
        const response = await api.get('/stats');
        return response.data;
    } catch (error) {
        throw error.response?.data || error.message;
    }
};

// Get insights
export const getInsights = async () => {
    try {
        const response = await api.get('/analyze/insights');
        return response.data;
    } catch (error) {
        throw error.response?.data || error.message;
    }
};

// Get top clients
export const getTopClients = async (limit = 10) => {
    try {
        const response = await api.get(`/analyze/top-clients?limit=${limit}`);
        return response.data;
    } catch (error) {
        throw error.response?.data || error.message;
    }
};

// Get top groups
export const getTopGroups = async (limit = 10) => {
    try {
        const response = await api.get(`/analyze/top-groups?limit=${limit}`);
        return response.data;
    } catch (error) {
        throw error.response?.data || error.message;
    }
};

// Get risk analysis
export const getRiskAnalysis = async (threshold = 3) => {
    try {
        const response = await api.get(`/analyze/risk-analysis?threshold=${threshold}`);
        return response.data;
    } catch (error) {
        throw error.response?.data || error.message;
    }
};

// Get business performance
export const getBusinessPerformance = async () => {
    try {
        const response = await api.get('/analyze/business-performance');
        return response.data;
    } catch (error) {
        throw error.response?.data || error.message;
    }
};

// Analyze client
export const analyzeClient = async (clientName) => {
    try {
        const response = await api.post('/analyze/client', { client_name: clientName });
        return response.data;
    } catch (error) {
        throw error.response?.data || error.message;
    }
};

// Analyze group
export const analyzeGroup = async (groupName) => {
    try {
        const response = await api.post('/analyze/group', { group_name: groupName });
        return response.data;
    } catch (error) {
        throw error.response?.data || error.message;
    }
};

export default api;
