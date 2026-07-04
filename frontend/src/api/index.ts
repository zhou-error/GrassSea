import axios from 'axios';

const API_BASE = '/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

// Auth
export const loginApi = (username: string, password: string) =>
  api.post('/auth/login', { username, password });

// Chat
export const chatApi = (message: string, sessionId?: string) =>
  api.post('/chat', { message, session_id: sessionId });

// RAG
export const ragQueryApi = (query: string) =>
  api.post('/rag/query', { query });

export const uploadDocumentApi = (file: File, kb: string) => {
  const fd = new FormData();
  fd.append('file', file);
  return api.post(`/rag/documents?knowledge_base=${encodeURIComponent(kb)}`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

// Task
export const getTaskStatusApi = (taskId: string) =>
  api.get(`/task/${taskId}/status`);

export default api;
