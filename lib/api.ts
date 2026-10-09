export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "";

export function getAuthToken(): string | null {
  if (typeof window !== "undefined") {
    return localStorage.getItem("mosaic_token");
  }
  return null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAuthToken();
  const headers: Record<string, string> = {};

  if (!(init?.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  if (init?.headers) {
    if (init.headers instanceof Headers) {
      init.headers.forEach((value, key) => {
        headers[key] = value;
      });
    } else if (Array.isArray(init.headers)) {
      init.headers.forEach(([key, value]) => {
        headers[key] = value;
      });
    } else {
      Object.assign(headers, init.headers);
    }
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status} ${detail.slice(0, 200)}`);
  }
  return (await res.json()) as T;
}

/* ---------- types ---------- */

export type Severity = "critical" | "worth_knowing" | "connection" | "info";

export interface Alert {
  id: string;
  severity: Severity;
  headline: string;
  explanation: string;
  confidence: number;
  status: string;
  suggested_action: string;
  why_it_matters: string[];
  reasoning_chain: { step: string; label: string }[];
  evidence: EvidenceItem[];
  entity: { id: string; name: string; type: string } | null;
  external_item: { id: string; title: string; url: string | null; category: string } | null;
  created_at: string | null;
}

export interface EvidenceItem {
  kind?: string;
  title?: string;
  source?: string;
  url?: string | null;
  snippet?: string;
  score?: number;
  trust_tier?: number;
  ref_type?: string;
}

export interface GraphNode {
  id: string;
  type: string;
  name: string;
  attributes: Record<string, any>;
  aliases: string[];
  document_id: string | null;
  degree: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
}

export interface DashboardData {
  user: { id: string; name: string };
  summary: {
    important: number;
    connections: number;
    upcoming: number;
    upcoming_items: { entity_id: string; name: string; label: string; date: string }[];
    nodes: number;
    edges: number;
    documents: number;
    unread_alerts: number;
    llm_provider: string;
  };
  recent: Alert[];
}

export interface ExtractionResult {
  document: {
    id: string;
    kind: string;
    title: string;
    status: string;
    extraction: { kind: string; summary: string; fields: Record<string, any>; confidence: number };
  };
  thread_id: string;
  trace: { agent: string; action: string; detail: string }[];
  awaiting_confirmation: boolean;
}

export interface DocumentEvaluation {
  document_id: string;
  method: string;
  query: string;
  note: string;
  metrics: {
    context_precision: number;
    context_precision_definition: string;
    context_recall: number;
    context_recall_definition: string;
  };
  checks: { name: string; passed: boolean; actual: string }[];
  retrieved_documents: {
    document_id: string;
    title: string;
    score: number;
    matches_uploaded_document: boolean;
  }[];
  extracted_fields: Record<string, unknown>;
}

/* ---------- calls ---------- */

export const api = {
  health: () => request<Record<string, any>>("/api/health"),
  dashboard: () => request<DashboardData>("/api/dashboard"),
  graph: () => request<{ nodes: GraphNode[]; edges: GraphEdge[] }>("/api/graph"),
  entity: (id: string) => request<any>(`/api/graph/entities/${id}`),
  alerts: (status?: string) =>
    request<{ alerts: Alert[] }>(`/api/alerts${status ? `?status=${status}` : ""}`),
  evidence: (id: string) => request<any>(`/api/alerts/${id}/evidence`),
  dismiss: (id: string) => request<any>(`/api/alerts/${id}/dismiss`, { method: "POST" }),
  runMonitor: () => request<any>("/api/monitor/run", { method: "POST" }),
  sources: () => request<any>("/api/sources"),
  documents: () => request<any>("/api/documents"),
  ingestText: (text: string, kind_hint?: string) =>
    request<ExtractionResult>("/api/documents/text", {
      method: "POST",
      body: JSON.stringify({ text, kind_hint: kind_hint || null }),
    }),
  ingestFile: (file: File, kind_hint?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (kind_hint) form.append("kind_hint", kind_hint);
    return request<ExtractionResult>("/api/documents/upload", { method: "POST", body: form });
  },
  ingestUrl: (url: string) =>
    request<ExtractionResult>("/api/documents/url", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),
  confirm: (documentId: string, threadId: string, overrides: Record<string, any> = {}) =>
    request<any>(`/api/documents/${documentId}/confirm`, {
      method: "POST",
      body: JSON.stringify({ thread_id: threadId, overrides }),
    }),
  evaluateDocument: (documentId: string) =>
    request<DocumentEvaluation>(`/api/documents/${documentId}/evaluation`),
  askAssistant: (question: string, conversationId?: string) =>
    request<{ answer: string; conversation_id: string; provider: string; entities?: any[]; sources?: any[]; evidence?: any[] }>("/api/assistant", {
      method: "POST",
      body: JSON.stringify({ message: question, question, conversation_id: conversationId || null }),
    }),
  chatAssistant: (message: string, conversationId?: string) =>
    request<{
      conversation_id: string;
      message: string;
      answer: string;
      entities: any[];
      sources: any[];
      evidence: any[];
      provider: string;
    }>("/api/assistant/chat", {
      method: "POST",
      body: JSON.stringify({ message, conversation_id: conversationId || null }),
    }),
  listChats: () => request<{ chats: any[] }>("/api/assistant/chats"),
  getChat: (id: string) => request<any>(`/api/assistant/chats/${id}`),
  deleteChat: (id: string) => request<any>(`/api/assistant/chats/${id}`, { method: "DELETE" }),

  // Auth & Profile
  signup: (data: { name: string; email: string; password: string }) =>
    request<{ user: any; token: string }>("/api/auth/signup", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  login: (data: { email: string; password: string }) =>
    request<{ user: any; token: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  logout: () => request<{ status: string }>("/api/auth/logout", { method: "POST" }),
  me: () => request<{ user: any }>("/api/auth/me"),
  getProfile: () => request<{ user_id: string; name: string; email: string; profile: any }>("/api/profile"),
  updateProfile: (body: any) =>
    request<{ user_id: string; name: string; email: string; profile: any }>("/api/profile", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
};

/* ---------- presentation helpers ---------- */

export const SEVERITY = {
  critical: { label: "Important", dotColor: "bg-accent", chip: "bg-accent-soft text-accent-deep border-accent/30" },
  worth_knowing: { label: "Worth knowing", dotColor: "bg-peach-deep", chip: "bg-peach-soft text-peach-deep border-peach/40" },
  connection: { label: "New connection", dotColor: "bg-dusty-deep", chip: "bg-dusty-soft text-dusty-deep border-dusty/40" },
  info: { label: "Informational", dotColor: "bg-sage-deep", chip: "bg-sage-soft text-sage-deep border-sage/40" },
} as const;

export const NODE_STYLE: Record<string, { bg: string; border: string; text: string }> = {
  product:        { bg: "#E8E1F2", border: "#C2B4D5", text: "#57466B" },
  asset:          { bg: "#E8E1F2", border: "#C2B4D5", text: "#57466B" },
  purchase:       { bg: "#F8EBDD", border: "#E7CBAA", text: "#705A45" },
  brand:          { bg: "#E5ECF2", border: "#C3D0DB", text: "#536675" },
  retailer:       { bg: "#E7EFE5", border: "#C6D6C1", text: "#50644F" },
  service:        { bg: "#E7EFE5", border: "#C6D6C1", text: "#50644F" },
  warranty:       { bg: "#F8EBDD", border: "#E8D0AE", text: "#765E3F" },
  subscription:   { bg: "#F0E9F4", border: "#D6C5E2", text: "#675474" },
  payment_method: { bg: "#F5EDE5", border: "#DFCEBD", text: "#6D5948" },
  bill:           { bg: "#F5E8E6", border: "#E6C6C2", text: "#75504D" },
  expense:        { bg: "#F5E8E6", border: "#E6C6C2", text: "#75504D" },
  document:       { bg: "#E5EDF5", border: "#C4D4E3", text: "#506477" },
  alert:          { bg: "#FEE2E2", border: "#EF4444", text: "#7F1D1D" },
  event:          { bg: "#E5EDF5", border: "#C4D4E3", text: "#506477" },
  default:        { bg: "#F0EFEB", border: "#D4D1C8", text: "#5D5A52" },
};

export function nodeStyle(type: string) {
  return NODE_STYLE[type] || NODE_STYLE.default;
}

export function formatFieldLabel(key: string) {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatValue(value: any) {
  if (value === null || value === undefined) return "-";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "number" && value > 999) return value.toLocaleString("en-IN");
  return String(value);
}
