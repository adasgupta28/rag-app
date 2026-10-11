import type { Conversation } from "../api";

interface Props {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

export function ConversationList({ conversations, activeId, onSelect, onDelete }: Props) {
  if (conversations.length === 0) {
    return <p className="px-1 text-xs text-slate-400">No conversations yet.</p>;
  }
  return (
    <ul className="space-y-0.5">
      {conversations.map((c) => (
        <li
          key={c.id}
          className={`group flex items-center gap-2 rounded-md px-2 py-1.5 text-sm ${
            c.id === activeId ? "bg-indigo-100 text-indigo-900" : "text-slate-700 hover:bg-slate-100"
          }`}
        >
          <button onClick={() => onSelect(c.id)} className="min-w-0 flex-1 truncate text-left">
            {c.title}
          </button>
          <button
            onClick={() => onDelete(c.id)}
            className="invisible text-xs text-slate-400 hover:text-red-600 group-hover:visible"
            aria-label={`Delete conversation ${c.title}`}
          >
            ✕
          </button>
        </li>
      ))}
    </ul>
  );
}
