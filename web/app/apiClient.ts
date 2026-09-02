import { supabase } from "./supabaseClient";

const API_BASE = "http://localhost:8000";

export async function apiFetch(path: string, options: RequestInit = {}) {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  const orgId = typeof window !== "undefined" ? localStorage.getItem("selected_org_id") : null;

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: token ? `Bearer ${token}` : "",
      "X-Organization-Id": orgId ?? "",
      "Content-Type": "application/json",
    },
  });

  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(`API error ${res.status}: ${errorBody}`);
  }

  return res.json();
}