export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers || {}),
    },
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
};

/* ---------- presentation helpers ---------- */

export const SEVERITY = {
  critical: { label: "Important", dotColor: "bg-accent", chip: "bg-accent-soft text-accent-deep border-accent/30" },
  worth_knowing: { label: "Worth knowing", dotColor: "bg-peach-deep", chip: "bg-peach-soft text-peach-deep border-peach/40" },
  connection: { label: "New connection", dotColor: "bg-dusty-deep", chip: "bg-dusty-soft text-dusty-deep border-dusty/40" },
  info: { label: "Informational", dotColor: "bg-sage-deep", chip: "bg-sage-soft text-sage-deep border-sage/40" },
} as const;

export const NODE_STYLE: Record<string, { bg: string; border: string; text: string }> = {
  product: { bg: "#EFECF8", border: "#C9C0E4", text: "#4A3F7A" },
  brand: { bg: "#E9EFF5", border: "#AFC3D6", text: "#3B5A76" },
  retailer: { bg: "#E9EFE7", border: "#B4C7B0", text: "#3F5C40" },
  warranty: { bg: "#FBEDE2", border: "#EFC9AC", text: "#8A5330" },
  subscription: { bg: "#F3ECF6", border: "#D7C2E0", text: "#6B4577" },
  payment_method: { bg: "#F1EFEA", border: "#DAD3C6", text: "#5A5346" },
  bill: { bg: "#FBEDE2", border: "#EFC9AC", text: "#8A5330" },
  event: { bg: "#E9EFF5", border: "#AFC3D6", text: "#3B5A76" },
  default: { bg: "#F2F0EC", border: "#DDD7CC", text: "#4A5568" },
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
