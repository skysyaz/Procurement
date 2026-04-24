import axios from "axios";

const BASE = process.env.REACT_APP_BACKEND_URL;

export const api = axios.create({
  baseURL: `${BASE}/api`,
});

export const fileUrl = (path) => (path?.startsWith("http") ? path : `${BASE}${path}`);
