import { useRef, useState } from "react";

interface Props {
  onFiles: (files: File[]) => void;
}

export function UploadZone({ onFiles }: Props) {
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const accept = (list: FileList | null) => {
    if (list?.length) onFiles(Array.from(list));
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => input.current?.click()}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        accept(e.dataTransfer.files);
      }}
      className={`cursor-pointer rounded-lg border-2 border-dashed px-4 py-6 text-center text-sm transition-colors ${
        dragging
          ? "border-indigo-500 bg-indigo-50 text-indigo-700"
          : "border-slate-300 text-slate-500 hover:border-indigo-400 hover:text-slate-700"
      }`}
    >
      <p className="font-medium">Drop PDFs here</p>
      <p className="text-xs">or click to browse</p>
      <input
        ref={input}
        type="file"
        accept="application/pdf,.pdf"
        multiple
        hidden
        onChange={(e) => {
          accept(e.target.files);
          e.target.value = "";
        }}
      />
    </div>
  );
}
