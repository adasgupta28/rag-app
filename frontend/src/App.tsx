import { useCallback, useEffect, useRef, useState } from "react";
import { api, streamChat, type Conversation, type DocumentInfo } from "./api";
import { ChatMessage, type UiMessage } from "./components/ChatMessage";
import { ConversationList } from "./components/ConversationList";
import { DocumentList } from "./components/DocumentList";
import { UploadZone } from "./components/UploadZone";

const POLL_MS = 2000;

export default function App() {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  const refreshDocuments = useCallback(() => api.listDocuments().then(setDocuments).catch(() => {}), []);
  const refreshConversations = useCallback(
    () => api.listConversations().then(setConversations).catch(() => {}),
    [],
  );

  useEffect(() => {
    refreshDocuments();
    refreshConversations();
  }, [refreshDocuments, refreshConversations]);

  // Poll while any document is still being ingested.
  const anyProcessing = documents.some((d) => d.status === "processing");
  useEffect(() => {
    if (!anyProcessing) return;
    const timer = setInterval(refreshDocuments, POLL_MS);
    return () => clearInterval(timer);
  }, [anyProcessing, refreshDocuments]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const uploadFiles = async (files: File[]) => {
    const errors: string[] = [];
    for (const file of files) {
      try {
        await api.uploadDocument(file);
      } catch (e) {
        errors.push(`${file.name}: ${(e as Error).message}`);
      }
      refreshDocuments();
    }
    setNotice(errors.length ? errors.join("\n") : null);
  };

  const deleteDocument = async (doc: DocumentInfo) => {
    if (!confirm(`Delete "${doc.filename}" and its embeddings?`)) return;
    await api.deleteDocument(doc.id).catch((e) => setNotice(e.message));
    refreshDocuments();
  };

  const openConversation = async (id: string) => {
    if (busy) return;
    const detail = await api.getConversation(id);
    setActiveId(id);
    setMessages(
      detail.messages.map((m) => ({
        key: String(m.id),
        role: m.role,
        content: m.content,
        sources: m.sources,
        rewrittenQuery: m.rewritten_query,
      })),
    );
  };

  const deleteConversation = async (id: string) => {
    await api.deleteConversation(id);
    if (id === activeId) newChat();
    refreshConversations();
  };

  const newChat = () => {
    if (busy) return;
    setActiveId(null);
    setMessages([]);
  };

  const updateLast = (patch: (m: UiMessage) => Partial<UiMessage>) =>
    setMessages((prev) => [...prev.slice(0, -1), { ...prev[prev.length - 1], ...patch(prev[prev.length - 1]) }]);

  const ask = async () => {
    const question = input.trim();
    if (!question || busy) return;
    setInput("");
    setBusy(true);
    const stamp = Date.now();
    setMessages((prev) => [
      ...prev,
      { key: `u${stamp}`, role: "user", content: question, sources: [] },
      { key: `a${stamp}`, role: "assistant", content: "", sources: [], pending: true },
    ]);

    try {
      await streamChat(question, activeId, {
        onMeta: ({ conversation_id, query }) => {
          setActiveId(conversation_id);
          if (query !== question) updateLast(() => ({ rewrittenQuery: query }));
        },
        onSources: (sources) => updateLast(() => ({ sources })),
        onToken: (text) => updateLast((m) => ({ content: m.content + text })),
        onDone: () => updateLast(() => ({ pending: false })),
        onError: (message) => updateLast(() => ({ pending: false, error: message })),
      });
    } catch (e) {
      updateLast(() => ({ pending: false, error: (e as Error).message }));
    } finally {
      setBusy(false);
      refreshConversations();
    }
  };

  const readyCount = documents.filter((d) => d.status === "ready").length;

  return (
    <div className="flex h-full bg-slate-50 text-slate-900">
      <aside className="flex w-80 shrink-0 flex-col gap-5 overflow-y-auto border-r border-slate-200 bg-white p-4">
        <header>
          <h1 className="text-lg font-bold tracking-tight">📄 PaperTrail</h1>
          <p className="text-xs text-slate-500">Ask questions about your PDFs. Every answer cites its sources.</p>
        </header>

        <section className="space-y-2">
          <UploadZone onFiles={uploadFiles} />
          {notice && <p className="whitespace-pre-wrap rounded bg-red-50 p-2 text-xs text-red-700">{notice}</p>}
        </section>

        <section className="space-y-1">
          <h2 className="px-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Documents ({documents.length})
          </h2>
          <DocumentList documents={documents} onDelete={deleteDocument} />
        </section>

        <section className="space-y-1">
          <div className="flex items-center justify-between px-1">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Conversations</h2>
            <button onClick={newChat} className="text-xs font-medium text-indigo-600 hover:underline">
              + New chat
            </button>
          </div>
          <ConversationList
            conversations={conversations}
            activeId={activeId}
            onSelect={openConversation}
            onDelete={deleteConversation}
          />
        </section>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl space-y-5 px-6 py-8">
            {messages.length === 0 && (
              <div className="mt-24 text-center text-slate-500">
                <p className="text-xl font-semibold text-slate-700">What would you like to know?</p>
                <p className="mt-2 text-sm">
                  {readyCount > 0
                    ? `Searching across ${readyCount} document${readyCount === 1 ? "" : "s"}.`
                    : "Upload a PDF on the left to get started."}
                </p>
              </div>
            )}
            {messages.map((m) => (
              <ChatMessage key={m.key} message={m} />
            ))}
            <div ref={bottom} />
          </div>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            ask();
          }}
          className="border-t border-slate-200 bg-white px-6 py-4"
        >
          <div className="mx-auto flex max-w-3xl gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  ask();
                }
              }}
              rows={1}
              placeholder="Ask a question about your documents…"
              className="flex-1 resize-none rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
            <button
              type="submit"
              disabled={busy || !input.trim()}
              className="rounded-lg bg-indigo-600 px-4 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {busy ? "…" : "Ask"}
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}
