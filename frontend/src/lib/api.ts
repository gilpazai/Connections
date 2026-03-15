/**
 * Typed API client for the FastAPI backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, body);
  }
  return res.json();
}

// --- Contacts ---

import type { Contact, Lead, Match, WorkHistoryEntry, ConnectivityStatus } from "@/types";

export const contacts = {
  list: (status = "Active") =>
    request<Contact[]>(`/api/contacts?status=${status}`),

  create: (data: Partial<Contact>) =>
    request<Contact>("/api/contacts", { method: "POST", body: JSON.stringify(data) }),

  update: (pageId: string, data: Record<string, unknown>) =>
    request<{ updated: boolean }>(`/api/contacts/${pageId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  delete: (pageId: string, personName: string) =>
    request<{ deleted: boolean }>(
      `/api/contacts/${pageId}?person_name=${encodeURIComponent(personName)}`,
      { method: "DELETE" },
    ),
};

// --- Leads ---

export interface ImportStatus {
  task_id: string;
  status: "running" | "done" | "error";
  total: number;
  processed: number;
  created: number;
  skipped: number;
  imported_names: string[];
  error: string | null;
}

export const leads = {
  list: (params?: { batch?: string; status?: string }) => {
    const qs = new URLSearchParams();
    if (params?.batch) qs.set("batch", params.batch);
    if (params?.status) qs.set("status", params.status);
    return request<Lead[]>(`/api/leads?${qs}`);
  },

  create: (data: Partial<Lead>) =>
    request<Lead>("/api/leads", { method: "POST", body: JSON.stringify(data) }),

  importCsv: async (
    file: File,
    batch: string,
    priority: string,
    onProgress?: (status: ImportStatus) => void,
  ): Promise<ImportStatus> => {
    const form = new FormData();
    form.append("file", file);
    form.append("batch", batch);
    form.append("priority", priority);
    const res = await fetch(`${API_BASE}/api/leads/import-csv`, { method: "POST", body: form });
    if (!res.ok) throw new ApiError(res.status, await res.text());
    const { task_id } = (await res.json()) as { task_id: string };

    // Poll for completion
    while (true) {
      await new Promise((r) => setTimeout(r, 1500));
      const status = await request<ImportStatus>(`/api/leads/import-status/${task_id}`);
      onProgress?.(status);
      if (status.status === "done" || status.status === "error") return status;
    }
  },

  importPaste: (lines: string[], batch: string, priority: string) =>
    request<{ created: number; skipped: number; imported_names: string[] }>("/api/leads/import-paste", {
      method: "POST",
      body: JSON.stringify({ lines, batch, priority }),
    }),

  update: (pageId: string, data: Record<string, unknown>) =>
    request<{ updated: boolean }>(`/api/leads/${pageId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  delete: (pageId: string, personName: string) =>
    request<{ deleted: boolean }>(
      `/api/leads/${pageId}?person_name=${encodeURIComponent(personName)}`,
      { method: "DELETE" },
    ),

  archiveBatch: (batch: string) =>
    request<{ archived: number }>("/api/leads/archive-batch", {
      method: "POST",
      body: JSON.stringify({ batch }),
    }),

  deleteAll: () =>
    request<{ deleted: number }>("/api/leads", { method: "DELETE" }),
};

// --- Matches ---

export const matches = {
  list: (params?: { status?: string; confidence?: string }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.confidence) qs.set("confidence", params.confidence);
    return request<Match[]>(`/api/matches?${qs}`);
  },

  update: (pageId: string, data: Record<string, unknown>) =>
    request<{ updated: boolean }>(`/api/matches/${pageId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  recheck: () =>
    request<{ created: number; skipped: number }>("/api/matches/recheck", { method: "POST" }),

  deleteAll: () =>
    request<{ deleted: number }>("/api/matches", { method: "DELETE" }),
};

// --- Work History ---

export const workHistory = {
  grouped: (personType?: string) => {
    const qs = personType ? `?person_type=${personType}` : "";
    return request<Record<string, WorkHistoryEntry[]>>(`/api/work-history${qs}`);
  },

  forPerson: (personName: string) =>
    request<WorkHistoryEntry[]>(`/api/work-history/${encodeURIComponent(personName)}`),
};

// --- Enrichment ---

export const enrichment = {
  enrich: (data: { person_name: string; person_type: string; raw_text: string; notion_page_id?: string }) =>
    request<{ positions_stored: number; new_matches: number }>("/api/enrich", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

// --- Research ---

export const research = {
  run: (personName: string, company = "", forceRefresh = false) =>
    request<{ report: string; cached: boolean }>("/api/research", {
      method: "POST",
      body: JSON.stringify({ person_name: personName, company, force_refresh: forceRefresh }),
    }),

  get: (personName: string) =>
    request<{ report: string; cached: boolean }>(`/api/research/${encodeURIComponent(personName)}`),

  delete: (personName: string) =>
    request<{ deleted: boolean }>(`/api/research/${encodeURIComponent(personName)}`, { method: "DELETE" }),
};

// --- Settings ---

export interface LLMConfig {
  provider: string;
  model: string;
  available_providers: string[];
  available_models: Record<string, string[]>;
}

export interface EnrichmentConfig {
  batch_size: number;
}

export const settings = {
  connectivity: () => request<ConnectivityStatus>("/api/settings/connectivity"),
  llm: () => request<LLMConfig>("/api/settings/llm"),
  updateLlm: (provider: string, model: string) =>
    request<LLMConfig>("/api/settings/llm", {
      method: "PATCH",
      body: JSON.stringify({ provider, model }),
    }),
  enrichment: () => request<EnrichmentConfig>("/api/settings/enrichment"),
  updateEnrichment: (batch_size: number) =>
    request<EnrichmentConfig>("/api/settings/enrichment", {
      method: "PATCH",
      body: JSON.stringify({ batch_size }),
    }),
};
