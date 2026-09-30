import { sessionHeaders } from "./supabase";

export type Contact = {
  id: string;
  name: string;
  email: string;
  contact?: string;
  company: string;
  status: string;
  interest_level: string;
  notes: string;
  next_followup: string | null;
  last_interaction: string | null;
  priority_score: number;
  bucket: string;
  source: string;
  do_not_contact: boolean;
  replied: boolean;
  deal_context?: string;
};

export type Draft = { subject: string; body: string; version?: number };
export type Recommendation = {
  id: string;
  contact_id: string;
  action: string;
  reason: string;
  sources: (string | { field: string; value: string })[];
  status: string;
  draft?: Draft | null;
  subject?: string;
  body?: string;
  version?: number;
  eligible?: boolean;
  generation_source?: string;
  model_id?: string;
  prompt_version?: string;
  generation_error?: string | null;
  experiment_id?: string | null;
  variant_id?: string | null;
};

export type Activity = {
  id: string;
  contact_id?: string;
  contact_name?: string;
  type: string;
  kind?: string;
  detail: string;
  created_at: string;
};

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...Object.fromEntries(new Headers(options.headers).entries()), ...await sessionHeaders() },
    cache: "no-store",
  });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : body.message || detail;
    } catch { /* keep HTTP status */ }
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function asList<T>(value: unknown, key: string): T[] {
  if (Array.isArray(value)) return value as T[];
  if (value && typeof value === "object") {
    const nested = (value as Record<string, unknown>)[key];
    if (Array.isArray(nested)) return nested as T[];
  }
  return [];
}

export function asRecommendation(value: unknown): Recommendation {
  const item = value && typeof value === "object" && "recommendation" in value
    ? (value as { recommendation: Recommendation }).recommendation
    : value as Recommendation;
  return item;
}

export function niceDate(value?: string | null) {
  if (!value) return "Not set";
  const date = new Date(value.length === 10 ? `${value}T12:00:00` : value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function initials(name: string) {
  return name.split(/\s+/).slice(0, 2).map(part => part[0] || "").join("").toUpperCase();
}

export async function downloadContacts() {
  const response = await fetch("/api/export.csv", { headers: await sessionHeaders(), cache: "no-store" });
  if (!response.ok) throw new Error(`Could not export contacts (${response.status}).`);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url; link.download = "contacts.csv"; link.click();
  URL.revokeObjectURL(url);
}
