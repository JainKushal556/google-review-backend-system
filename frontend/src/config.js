// API Base URL Configuration for Local and Vercel Production
export const API_BASE = import.meta.env.VITE_API_BASE || 
  (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
    ? 'http://localhost:5000' 
    : 'https://google-review-backend-system.onrender.com');
