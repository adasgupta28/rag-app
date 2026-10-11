import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, type Source } from "../api";

export interface UiMessage {
  key: string;
  role: "user" | "assistant";
  content: string;
  sources: Source[];
  rewrittenQuery?: string | null;
  pending?: boolean;
  error?: string;
}

function pageLabel(s: Source) {
  return s.page_start === s.page_end ? `p. ${s.page_start}` : `pp. ${s.page_start}–${s.page_end}`;
}

/** Turn "[2]" citations into links the markdown renderer can hand to our citation component. */
function linkCitations(text: string) {
  return text.replace(/\[(\d+)\](?!\()/g, "[$1](#cite-$1)");
}

function citedNumbers(text: string) {
  return new Set(Array.from(text.matchAll(/\[(\d+)\]/g), (m) => Number(m[1])));
}

export function ChatMessage({ message }: { message: UiMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-indigo-600 px-4 py-2 text-white">
          {message.content}
        </div>
      </div>
    );
  }

  const bySourceNumber = new Map(message.sources.map((s) => [s.n, s]));
  const cited = citedNumbers(message.content);
  const citedSources = message.sources.filter((s) => cited.has(s.n));

  return (
    <div className="max-w-[90%] space-y-2">
      {message.rewrittenQuery && (
        <p className="text-xs text-slate-400">Searched for: “{message.rewrittenQuery}”</p>
      )}
      <div className="rounded-2xl text-sm leading-relaxed rounded-bl-sm bg-white px-4 py-3 text-slate-800 shadow-sm ring-1 ring-slate-200 [&_li]:my-0.5 [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:my-1.5 [&_ul]:list-disc [&_ul]:pl-5">
        {message.content ? (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              a: ({ href, children }) => {
                const n = href?.startsWith("#cite-") ? Number(href.slice(6)) : null;
                const source = n !== null ? bySourceNumber.get(n) : undefined;
                if (!source) {
                  return (
                    <a href={href} target="_blank" rel="noreferrer" className="text-indigo-600 underline">
                      {children}
                    </a>
                  );
                }
                return (
                  <a
                    href={api.documentUrl(source.doc_id, source.page_start)}
                    target="_blank"
                    rel="noreferrer"
                    title={`${source.filename}, ${pageLabel(source)}`}
                    className="mx-0.5 inline-block rounded bg-indigo-100 px-1 text-[0.7rem] font-semibold text-indigo-700 no-underline hover:bg-indigo-200"
                  >
                    {n}
                  </a>
                );
              },
            }}
          >
            {linkCitations(message.content)}
          </ReactMarkdown>
        ) : message.pending ? (
          <span className="text-slate-400">Searching your documents…</span>
        ) : null}
        {message.error && <p className="text-sm text-red-600">⚠ {message.error}</p>}
      </div>

      {citedSources.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Sources</p>
          {citedSources.map((s) => (
            <details key={s.n} className="rounded-md bg-slate-50 px-3 py-1.5 text-xs ring-1 ring-slate-200">
              <summary className="cursor-pointer text-slate-700">
                <span className="mr-1 font-semibold text-indigo-700">[{s.n}]</span>
                {s.filename} · {pageLabel(s)}
                <span className="ml-2 text-slate-400">relevance {s.score.toFixed(2)}</span>
              </summary>
              <p className="mt-1 whitespace-pre-wrap text-slate-600">{s.snippet}</p>
              <a
                href={api.documentUrl(s.doc_id, s.page_start)}
                target="_blank"
                rel="noreferrer"
                className="mt-1 inline-block text-indigo-600 hover:underline"
              >
                Open PDF at page {s.page_start} →
              </a>
            </details>
          ))}
        </div>
      )}
    </div>
  );
}
