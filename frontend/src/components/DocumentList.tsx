import { api, type DocumentInfo } from "../api";

interface Props {
  documents: DocumentInfo[];
  onDelete: (doc: DocumentInfo) => void;
}

const badge: Record<DocumentInfo["status"], string> = {
  processing: "bg-amber-100 text-amber-800",
  ready: "bg-emerald-100 text-emerald-800",
  failed: "bg-red-100 text-red-800",
};

function formatSize(bytes: number) {
  return bytes < 1024 * 1024 ? `${Math.ceil(bytes / 1024)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

export function DocumentList({ documents, onDelete }: Props) {
  if (documents.length === 0) {
    return <p className="px-1 text-xs text-slate-400">No documents yet.</p>;
  }
  return (
    <ul className="space-y-1">
      {documents.map((doc) => (
        <li key={doc.id} className="group rounded-md px-2 py-1.5 hover:bg-slate-100" title={doc.error ?? undefined}>
          <div className="flex items-center gap-2">
            <a
              href={api.documentUrl(doc.id)}
              target="_blank"
              rel="noreferrer"
              className="min-w-0 flex-1 truncate text-sm text-slate-800 hover:underline"
            >
              {doc.filename}
            </a>
            <button
              onClick={() => onDelete(doc)}
              disabled={doc.status === "processing"}
              className="invisible text-xs text-slate-400 hover:text-red-600 disabled:hidden group-hover:visible"
              aria-label={`Delete ${doc.filename}`}
            >
              ✕
            </button>
          </div>
          <div className="mt-0.5 flex items-center gap-2 text-xs text-slate-500">
            <span className={`rounded px-1.5 py-px ${badge[doc.status]}`}>
              {doc.status === "processing" ? "processing…" : doc.status}
            </span>
            <span>{formatSize(doc.size_bytes)}</span>
            {doc.page_count !== null && <span>{plural(doc.page_count, "page")}</span>}
            {doc.chunk_count !== null && <span>{plural(doc.chunk_count, "chunk")}</span>}
          </div>
          {doc.error && <p className="mt-0.5 line-clamp-2 text-xs text-red-600">{doc.error}</p>}
        </li>
      ))}
    </ul>
  );
}
