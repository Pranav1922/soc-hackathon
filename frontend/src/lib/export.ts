import type { HistoryRecord } from "@/types/workflow";
import { absoluteTime } from "@/lib/time";

/** Trigger a client-side file download from a string. */
export function downloadBlob(filename: string, content: string, type: string): void {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function downloadJSON(filename: string, data: unknown): void {
  downloadBlob(filename, JSON.stringify(data, null, 2), "application/json");
}

/** Clipboard copy with a legacy execCommand fallback for insecure contexts. */
export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      ta.remove();
      return ok;
    } catch {
      return false;
    }
  }
}

function csvCell(value: string | number): string {
  const s = String(value);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** Serialize the history table to CSV (columns match the on-screen table). */
export function historyToCSV(records: HistoryRecord[]): string {
  const header = ["Time", "Query", "Intent", "Pattern", "Risk", "Flagged", "Summary"];
  const rows = records.map((r) =>
    [absoluteTime(r.timestamp), r.query, r.intent ?? "", r.pattern ?? "", r.avgRisk.toFixed(2), r.flagged, r.summary]
      .map(csvCell)
      .join(","),
  );
  return [header.join(","), ...rows].join("\n");
}

const esc = (s: string) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c] as string);

/** Open a print-friendly investigation summary in a new window. Returns false if blocked. */
export function printInvestigation(record: HistoryRecord): boolean {
  const res = record.response;
  const rows =
    res?.results
      .map(
        (r) =>
          `<tr><td>${esc(r.entity_id)}</td><td>${esc(r.entity_type)}</td><td>${esc(r.risk)}</td><td>${r.score.toFixed(
            2,
          )}</td><td>${esc(r.action)}</td><td>${esc(r.explanation)}</td></tr>`,
      )
      .join("") ?? "";
  const html = `<!doctype html><html><head><meta charset="utf-8"><title>Investigation — ${esc(record.query)}</title>
<style>
  body{font-family:Inter,system-ui,sans-serif;color:#0f172a;margin:40px;line-height:1.5}
  h1{font-size:20px;margin:0 0 4px} .muted{color:#64748b;font-size:13px}
  .meta{margin:16px 0;display:flex;flex-wrap:wrap;gap:8px}
  .chip{border:1px solid #cbd5e1;border-radius:999px;padding:2px 10px;font-size:12px}
  table{width:100%;border-collapse:collapse;margin-top:16px;font-size:12px}
  th,td{border:1px solid #e2e8f0;padding:6px 8px;text-align:left;vertical-align:top}
  th{background:#f1f5f9}
</style></head><body>
  <h1>AEGIS Investigation Report</h1>
  <div class="muted">${esc(absoluteTime(record.timestamp))}</div>
  <p><strong>Query:</strong> ${esc(record.query)}</p>
  <div class="meta">
    <span class="chip">Intent: ${esc(record.intent ?? "—")}</span>
    <span class="chip">Pattern: ${esc(record.pattern ?? "none")}</span>
    <span class="chip">Flagged: ${record.flagged}</span>
    <span class="chip">Avg risk: ${record.avgRisk.toFixed(2)}</span>
  </div>
  <p>${esc(record.summary)}</p>
  ${rows ? `<table><thead><tr><th>Entity</th><th>Type</th><th>Risk</th><th>Score</th><th>Action</th><th>Explanation</th></tr></thead><tbody>${rows}</tbody></table>` : "<p class='muted'>Full results were not stored for this investigation.</p>"}
  <script>window.onload=function(){window.print()}</script>
</body></html>`;
  const w = window.open("", "_blank", "width=900,height=700");
  if (!w) return false;
  w.document.write(html);
  w.document.close();
  return true;
}
