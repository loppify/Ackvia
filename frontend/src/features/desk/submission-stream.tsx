"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowLeft, ArrowRight, Check, ChevronRight, Inbox, ListFilter, Search } from "lucide-react";
import type { SubmissionDetail, SubmissionSummary } from "@/lib/types";
import { ACTIVE_STATUSES, deskUrl, evidenceState, PAGE_SIZE, payloadPreview, type DeskContext, type EvidenceState, type Resource } from "./model";
import { Empty, Fault, Time } from "./primitives";

type Evidence = Record<number, Resource<SubmissionDetail>>;

// A bounded page is enriched four requests at a time. No hidden all-source scan.
function usePageEvidence(rows: SubmissionSummary[], selected: SubmissionDetail | null, refreshVersion: number) {
  const [state, setState] = useState<{ selected: SubmissionDetail | null; records: Evidence }>(() => ({ selected, records: selected ? { [selected.id]: { data: selected, error: null } } : {} }));
  if (selected && state.selected !== selected) {
    setState({ selected, records: { ...state.records, [selected.id]: { data: selected, error: null } } });
  }
  const records = useRef(state.records);
  const selectedId = useRef(selected?.id);
  useEffect(() => { records.current = state.records; selectedId.current = selected?.id; }, [state.records, selected?.id]);
  const idsKey = rows.map((row) => row.id).join(",");

  useEffect(() => {
    const controller = new AbortController();
    const ids = idsKey.split(",").filter(Boolean).map(Number);
    let timer: ReturnType<typeof setTimeout>;
    async function batch(queue: number[]) {
      let cursor = 0;
      await Promise.all(Array.from({ length: Math.min(4, queue.length) }, async () => {
        while (cursor < queue.length && !controller.signal.aborted) {
          const id = queue[cursor++];
          let result: Resource<SubmissionDetail>;
          try {
            const response = await fetch(`/api/console/submissions/${id}`, { cache: "no-store", signal: controller.signal });
            result = await response.json();
            if (!result.data && !result.error) throw new Error("Invalid evidence response");
          } catch {
            if (controller.signal.aborted) return;
            result = { data: null, error: { title: "Evidence unavailable", message: "Refresh to retry this submission." } };
          }
          // The server-rendered selection owns its freshest snapshot. A request
          // started before selection must not overwrite it when it finishes.
          if (!controller.signal.aborted && id !== selectedId.current) {
            records.current = { ...records.current, [id]: result };
            setState((current) => ({ ...current, records: { ...current.records, [id]: result } }));
          }
        }
      }));
    }
    async function poll() {
      const active = ids.filter((id) => id !== selectedId.current && records.current[id]?.data?.deliveries.some((d) => ACTIVE_STATUSES.includes(d.status)));
      await batch(active);
      if (!controller.signal.aborted) timer = setTimeout(poll, 2000);
    }
    void batch(ids.filter((id) => id !== selectedId.current && (!records.current[id] || refreshVersion > 0))).then(() => {
      if (!controller.signal.aborted) timer = setTimeout(poll, 2000);
    });
    return () => { controller.abort(); clearTimeout(timer); };
  }, [idsKey, refreshVersion]);
  return state.records;
}

const evidenceLabels = { attention: "Needs attention", active: "In progress", delivered: "All delivered", captured: "No deliveries" };

export function SubmissionStream({ rows, selected, context, more, error, onSelect, onPage, refresh, refreshVersion }: { rows: SubmissionSummary[]; selected: SubmissionDetail | null; context: DeskContext; more: boolean; error: Resource<SubmissionSummary[]>["error"]; onSelect: (id: number) => void; onPage: (offset: number) => void; refresh: () => void; refreshVersion: number }) {
  const records = usePageEvidence(rows, selected, refreshVersion);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | EvidenceState>("all");
  const known = rows.filter((row) => records[row.id]?.data);
  const attention = known.filter((row) => evidenceState(records[row.id].data!) === "attention").length;
  const unavailable = rows.filter((row) => records[row.id]?.error).length;
  const loading = rows.length - known.length - unavailable;
  const visible = rows.filter((row) => {
    const detail = records[row.id]?.data;
    const state = detail ? evidenceState(detail) : null;
    const text = `${row.id} ${row.created_at} ${detail ? payloadPreview(detail.payload) : ""}`.toLowerCase();
    return (filter === "all" || state === filter) && text.includes(query.toLowerCase());
  });
  return <aside className="stream" aria-label="Submission stream">
    <div className="stream-heading"><span className="section-label"><Inbox size={17} aria-hidden="true" /><h1>Submissions</h1><span className="count">{rows.length}</span></span><ArrowDown size={13} className="muted" aria-label="Newest first" /></div>
    <div className="stream-scope"><span>Captured by this form</span><span className="mono">UTC</span></div>
    <label className="search-field stream-search"><Search size={14} aria-hidden="true" /><input id="stream-search" aria-label="Search this page" placeholder="Search this page…" value={query} onChange={(event) => setQuery(event.target.value)} /><kbd>/</kbd></label>
    <div className="stream-filters" aria-label="Filter this page">{([ ["all", "All"], ["attention", "Attention"], ["active", "In progress"], ["delivered", "Delivered"] ] as const).map(([value, label]) => <button type="button" key={value} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}{value === "attention" && attention > 0 && <span>{attention}</span>}</button>)}</div>
    <div className="stream-results" role="status"><span><ListFilter size={11} aria-hidden="true" />{filter === "all" && !query ? "Current page" : `${visible.length} matches on this page`}</span><span>{loading ? `Checking ${loading}…` : unavailable ? `${unavailable} unavailable` : "Delivery evidence loaded"}</span></div>
    {context.submission && !rows.some((row) => row.id === context.submission) && !error && <div className="linked-selection">Inspecting linked submission #{context.submission}. It is outside this page.</div>}
    <div className="stream-scroll">
      {error ? <Fault error={error} onRetry={refresh} /> : !rows.length ? <Empty icon={<Inbox size={24} />} title={context.offset ? "End of the stream" : "No submissions yet"}>{context.offset ? "Go to the previous page to continue investigating." : "Captured submissions will appear here when this form receives them."}</Empty> : !visible.length ? <Empty icon={<Search size={22} />} title={loading ? "Checking delivery evidence…" : "No matches on this page"}>{loading ? "Results will appear as evidence arrives." : <><button className="text-button" onClick={() => { setFilter("all"); setQuery(""); }}>Clear filters</button> or browse another page.</>}</Empty> : <ol className="stream-list">{visible.map((row, index) => {
        const evidence = records[row.id];
        const detail = selected?.id === row.id ? selected : evidence?.data;
        const state = detail ? evidenceState(detail) : null;
        return <li key={row.id}><Link prefetch={false} scroll={false} href={deskUrl({ ...context, submission: row.id, delivery: undefined })} data-submission={row.id} className={`stream-row ${context.submission === row.id ? "is-selected" : ""}`} aria-current={context.submission === row.id ? "true" : undefined} onClick={(event) => {
          if (!event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey && event.button === 0) { event.preventDefault(); onSelect(row.id); }
        }} onKeyDown={(event) => {
          if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
          event.preventDefault();
          const next = visible[index + (event.key === "ArrowDown" ? 1 : -1)];
          if (next) { onSelect(next.id); document.querySelector<HTMLAnchorElement>(`[data-submission="${next.id}"]`)?.focus(); }
        }}>
          <div className="stream-row-top"><span className="submission-id"><span className="capture-dot" aria-hidden="true" />#{row.id}</span><Time value={row.created_at} mode="time" /></div>
          <div className="stream-preview">{detail ? payloadPreview(detail.payload) : <span className="muted"><Check size={11} aria-hidden="true" /> Submission captured</span>}</div>
          <div className="stream-row-bottom"><span className={`evidence-state evidence-${state ?? "unread"}`}><span className="small-dot" />{state ? evidenceLabels[state] : evidence?.error ? "Evidence unavailable" : "Checking delivery…"}</span><ChevronRight size={13} aria-hidden="true" /></div>
        </Link></li>;
      })}</ol>}
    </div>
    <div className="stream-pagination"><button className="icon-button" type="button" aria-label="Previous submissions" disabled={!context.offset} onClick={() => onPage(Math.max(0, context.offset - PAGE_SIZE))}><ArrowLeft size={15} /></button><span>{rows.length ? `${context.offset + 1}–${context.offset + rows.length}` : "0"} <span className="muted">shown</span></span><button className="icon-button" type="button" aria-label="Next submissions" disabled={!more} onClick={() => onPage(context.offset + PAGE_SIZE)}><ArrowRight size={15} /></button></div>
  </aside>;
}
