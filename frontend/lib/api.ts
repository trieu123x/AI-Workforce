/**
 * Axios API client with automatic JWT Access Token (RAM/LocalStorage)
 * + Silent Refresh using HttpOnly Cookie (Anti-XSS).
 */

import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true, // Sends HttpOnly refresh_token cookie automatically
  // AI workflows may call multiple tools. Fast paths should normally finish in
  // a few seconds, while this ceiling prevents legitimate long jobs from being
  // reported as a generic Network Error after only 30 seconds.
  timeout: 90000,
});

// ── Request interceptor: Inject Access Token from localStorage ──
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// ── Response interceptor: Silent Token Refresh on 401 ──
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (err: unknown) => void;
}> = [];

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token!);
    }
  });
  failedQueue = [];
};

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/auth/login') &&
      !originalRequest.url?.includes('/auth/register')
    ) {
      if (originalRequest.url?.includes('/auth/refresh')) {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }

      originalRequest._retry = true;

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({
            resolve: (token: string) => {
              originalRequest.headers.Authorization = `Bearer ${token}`;
              resolve(api(originalRequest));
            },
            reject: (err: unknown) => reject(err),
          });
        });
      }

      isRefreshing = true;

      try {
        const storedRefreshToken = typeof window !== 'undefined' ? localStorage.getItem('refresh_token') : null;
        const { data } = await axios.post(
          `${API_BASE}/api/v1/auth/refresh`,
          { refresh_token: storedRefreshToken },
          { withCredentials: true }
        );
        const newAccessToken = data.access_token;
        const newRefreshToken = data.refresh_token;
        if (typeof window !== 'undefined') {
          localStorage.setItem('access_token', newAccessToken);
          if (newRefreshToken) {
            localStorage.setItem('refresh_token', newRefreshToken);
          }
        }
        api.defaults.headers.common.Authorization = `Bearer ${newAccessToken}`;
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;

        try {
          const { useAuthStore } = await import('@/store/useAuthStore');
          if (data.user) {
            useAuthStore.getState().setTokens(newAccessToken, data.user, newRefreshToken);
          } else {
            useAuthStore.setState({ accessToken: newAccessToken, isAuthenticated: true });
          }
        } catch (e) {
          console.warn('Could not sync useAuthStore during refresh:', e);
        }

        processQueue(null, newAccessToken);
        return api(originalRequest);
      } catch (refreshErr) {
        processQueue(refreshErr, null);
        if (typeof window !== 'undefined') {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          if (window.location.pathname !== '/login' && window.location.pathname !== '/register') {
            window.location.href = '/login';
          }
        }
        return Promise.reject(refreshErr);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export default api;
