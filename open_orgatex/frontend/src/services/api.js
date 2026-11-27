import axios from 'axios';

export const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export function getApiErrorMessage(err, fallback = 'Terjadi kesalahan saat menghubungi server.') {
  if (!err) return fallback;
  if (typeof err === 'string') return err;
  const detail = err.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((d) => d?.msg || JSON.stringify(d)).join('; ');
  }
  if (typeof err.response?.data === 'string' && err.response.data.trim()) {
    return err.response.data;
  }
  if (err.message) return err.message;
  return fallback;
}

export default api;
