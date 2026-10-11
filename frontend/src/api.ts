export type DocumentStatus = "processing" | "ready" | "failed";

export interface DocumentInfo {
  id: string;
  filename: string;
  size_bytes: number;
  page_count: number | null;
  chunk_count: number | null;
  status: DocumentStatus;
  error: string | null;
  created_at: string;
}

export interface Source {
  n: number;
  doc_id: string;
  filename: string;
  page_start: number;
  page_end: number;
  score: number;
  snippet: string;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface StoredMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  sources: Source[];
  rewritten_query: string | null;
  created_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: StoredMessage[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Request failed (${response.status})`);
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

export const api = {
  listDocuments: () => request<DocumentInfo[]>("/documents"),
  uploadDocument: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<DocumentInfo>("/documents", { method: "POST", body: form });
  },
  deleteDocument: (id: string) => request<void>(`/documents/${id}`, { method: "DELETE" }),
  documentUrl: (id: string, page?: number) => `/api/documents/${id}/file${page ? `#page=${page}` : ""}`,

  listConversations: () => request<Conversation[]>("/conversations"),
  getConversation: (id: string) => request<ConversationDetail>(`/conversations/${id}`),
  deleteConversation: (id: string) => request<void>(`/conversations/${id}`, { method: "DELETE" }),
};

export interface ChatHandlers {
  onMeta: (meta: { conversation_id: string; query: string }) => void;
  onSources: (sources: Source[]) => void;
  onToken: (text: string) => void;
  onDone: () => void;
  onError: (message: string) => void;
}

/** POSTs a question and parses the Server-Sent Events stream (EventSource only supports GET). */
export async function streamChat(
  question: string,
  conversationId: string | null,
  handlers: ChatHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, conversation_id: conversationId }),
    signal,
  });
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => null);
    handlers.onError(body?.detail?.[0]?.msg ?? body?.detail ?? `Request failed (${response.status})`);
    return;
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const event = block.match(/^event: (.*)$/m)?.[1];
      const data = block.match(/^data: (.*)$/m)?.[1];
      if (!event || data === undefined) continue;
      const payload = JSON.parse(data);
      if (event === "meta") handlers.onMeta(payload);
      else if (event === "sources") handlers.onSources(payload);
      else if (event === "token") handlers.onToken(payload.text);
      else if (event === "done") handlers.onDone();
      else if (event === "error") handlers.onError(payload.message);
    }
  }
}
