function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// Lightweight JSON syntax coloring. Runs on already-escaped text, so the only
// markup injected is our own <span> tags — safe for dangerouslySetInnerHTML.
function highlight(json: string): string {
  return json.replace(
    /("(?:\\.|[^"\\])*"(?:\s*:)?|\b(?:true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g,
    (m) => {
      let cls = "text-emerald-300"; // number
      if (m.startsWith("&quot;") || m.startsWith('"')) cls = m.trimEnd().endsWith(":") ? "text-sky-300" : "text-amber-200";
      else if (m === "true" || m === "false") cls = "text-purple-300";
      else if (m === "null") cls = "text-slate-500";
      return `<span class="${cls}">${m}</span>`;
    },
  );
}

/** Formatted, syntax-highlighted, scrollable JSON view. */
export default function JsonBlock({ value }: { value: unknown }) {
  const json = JSON.stringify(value ?? null, null, 2);
  const html = highlight(escapeHtml(json));
  return (
    <pre
      className="max-h-64 overflow-auto rounded-lg border border-white/10 bg-surface-950/70 p-3 font-mono text-xs leading-relaxed text-slate-300"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
