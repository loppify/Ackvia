"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import type { Form } from "@/lib/types";
import { useCallback, useEffect, useRef, useState, useTransition } from "react";
import { ArrowDown, ArrowUp, ArrowUpRight, Check, ChevronDown, CircleCheck, Inbox, Keyboard, Layers2, RadioTower, RefreshCw, ShieldCheck } from "lucide-react";
import { ACTIVE_STATUSES, deskUrl, type DeskContext, type DeskSnapshot } from "./model";
import { CopyButton, Dialog, Empty, Fault, Mark, Time } from "./primitives";
import { SourceSwitcher } from "./source-switcher";
import { SubmissionStream } from "./submission-stream";
import { PayloadExplorer } from "./payload-explorer";
import { DeliveryExecution } from "./delivery-execution";

export function Desk({ snapshot }: { snapshot: DeskSnapshot }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [sourceOpen, setSourceOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [mobileView, setMobileView] = useState<"stream" | "investigation">(snapshot.linkedSelection ? "investigation" : "stream");
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [inspectionFocus, setInspectionFocus] = useState<"execution" | "payload">("execution");
  const inFlight = useRef(false);
  const { context, submission: submissionResource, delivery: deliveryResource } = snapshot;
  const submission = submissionResource.data;
  const pageForm = snapshot.forms.data?.find((item) => item.id === context.form);
  const [rememberedForm, setRememberedForm] = useState<Form | undefined>(pageForm);
  if (pageForm && (pageForm.id !== rememberedForm?.id || pageForm.title !== rememberedForm?.title)) {
    setRememberedForm(pageForm);
  }
  const form = pageForm ?? (rememberedForm?.id === context.form ? rememberedForm : undefined);
  const live = !!submission?.deliveries.some((d) => ACTIVE_STATUSES.includes(d.status)) || (!!deliveryResource.data && ACTIVE_STATUSES.includes(deliveryResource.data.status));
  const navigate = useCallback((next: DeskContext) => {
    startTransition(() => router.push(deskUrl(next), { scroll: false }));
  }, [router]);
  const refresh = useCallback(() => {
    inFlight.current = true;
    startTransition(() => router.refresh());
  }, [router]);
  const refreshAll = useCallback(() => { setRefreshVersion((value) => value + 1); refresh(); }, [refresh]);
  useEffect(() => { inFlight.current = pending; }, [pending]);
  useEffect(() => {
    const investigation = document.getElementById("investigation");
    if (investigation) investigation.scrollTop = 0;
  }, [context.submission]);
  useEffect(() => {
    const execution = document.getElementById("execution-panel");
    if (execution) execution.scrollTop = 0;
  }, [context.submission, context.delivery]);
  useEffect(() => {
    // Materialize defaults without another request. Polling must not silently
    // jump to a newer submission (or a different delivery) during investigation.
    const url = new URL(window.location.href);
    let changed = false;
    for (const [key, value] of [["form", context.form], ["submission", context.submission], ["delivery", context.delivery]] as const) {
      if (value && !url.searchParams.has(key)) {
        url.searchParams.set(key, String(value));
        changed = true;
      }
    }
    if (changed) window.history.replaceState(null, "", url.pathname + url.search);
  }, [context.form, context.submission, context.delivery]);
  useEffect(() => {
    if (!live) return;
    const timer = setInterval(() => { if (!inFlight.current) refresh(); }, 2000);
    return () => clearInterval(timer);
  }, [live, refresh]);
  useEffect(() => {
    function shortcuts(event: KeyboardEvent) {
      if (event.key.toLowerCase() === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault(); setSourceOpen((open) => !open); return;
      }
      if (document.querySelector("dialog[open]") || (event.target instanceof HTMLElement && (event.target.closest("input, textarea, select, [contenteditable=true]")))) return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (event.key === "/") {
        event.preventDefault();
        setMobileView("stream");
        requestAnimationFrame(() => document.getElementById("stream-search")?.focus());
      }
      if (event.key === "?") { event.preventDefault(); setHelpOpen(true); }
      if (event.key.toLowerCase() === "r") { event.preventDefault(); refreshAll(); }
    }
    document.addEventListener("keydown", shortcuts);
    return () => document.removeEventListener("keydown", shortcuts);
  }, [refreshAll]);
  function selectSubmission(id: number) {
    setMobileView("investigation");
    navigate({ ...context, submission: id, delivery: undefined });
  }
  const rows = snapshot.submissions.data ?? [];
  const selectedIndex = rows.findIndex((row) => row.id === context.submission);
  const delivered = submission?.deliveries.filter((d) => d.status === "succeeded").length ?? 0;
  const needsAttention = submission?.deliveries.filter((d) => d.status === "failed" || d.status === "unknown").length ?? 0;

  return <div className="desk" data-mobile-view={mobileView}>
    <a className="skip-link" href="#investigation">Skip to investigation</a>
    <header className="command-bar"><Link href="/" className="brand" aria-label="Ackvia home"><Mark /><span>ackvia<span className="brand-stop">.</span></span></Link><span className="shell-divider" /><span className="desk-name">Investigation desk</span><div className="command-spacer" /><button type="button" className="button command-source" aria-label="Switch form" onClick={() => setSourceOpen(true)}><Layers2 size={14} aria-hidden="true" /><span>Switch form</span><kbd>⌘ K</kbd></button><button type="button" className="icon-button keyboard-help" title="Keyboard shortcuts (?)" aria-label="Keyboard shortcuts" onClick={() => setHelpOpen(true)}><Keyboard size={17} /></button></header>
    <div className="context-bar"><div className="source-context"><span className="source-icon"><RadioTower size={17} aria-hidden="true" /></span><div><span className="eyebrow">FORM SOURCE</span><button type="button" className="form-selector" onClick={() => setSourceOpen(true)}><span>{form?.title || (context.form ? `Form ${context.form.slice(0, 8)}` : "Choose a form")}</span><ChevronDown size={13} aria-hidden="true" /></button></div><details className="form-identity"><summary title="Form identity">ID</summary><div className="identity-popover"><span className="eyebrow">FORM ID</span><code>{context.form || "No form selected"}</code>{context.form && <CopyButton value={context.form} label="Copy form ID" />}</div></details></div><div className="context-actions"><span className="snapshot-label"><span className={live ? "live-dot" : "small-dot"} />{live ? "Active delivery · updating" : "Stream snapshot"}</span><button className="button refresh-button" type="button" disabled={pending} onClick={refreshAll} title="Refresh evidence (R)"><RefreshCw size={14} className={pending ? "spin" : undefined} aria-hidden="true" /><span>Refresh</span></button></div></div>
    <div className="mobile-navigation"><button type="button" aria-pressed={mobileView === "stream"} onClick={() => setMobileView("stream")}><Inbox size={14} aria-hidden="true" />Stream</button><button id="mobile-investigation" type="button" aria-pressed={mobileView === "investigation"} onClick={() => setMobileView("investigation")}><Layers2 size={14} aria-hidden="true" />Investigation{context.submission ? <span>#{context.submission}</span> : null}</button></div>
    {pending && <div className="navigation-progress" role="status" aria-label="Updating investigation"><span /></div>}
    <main className="desk-workspace">
      <SubmissionStream key={`${context.form}:${context.offset}`} refreshVersion={refreshVersion} rows={rows} selected={submission} context={context} more={snapshot.moreSubmissions} error={snapshot.submissions.error ?? (!context.form ? snapshot.forms.error : null)} onSelect={selectSubmission} onPage={(offset) => { setMobileView("stream"); navigate({ ...context, offset, submission: undefined, delivery: undefined }); }} refresh={refreshAll} />
      <section className="investigation" id="investigation" tabIndex={-1} aria-label="Submission investigation">
        {snapshot.forms.error && context.form && <Fault error={snapshot.forms.error} onRetry={refreshAll} />}
        {submissionResource.error ? <Fault error={submissionResource.error} onRetry={refresh} /> : !submission ? <div className="investigation-placeholder"><div className="placeholder-path"><span><Inbox size={22} /></span><i /><span><ShieldCheck size={24} /></span><i /><span><ArrowUpRight size={22} /></span></div><Empty icon={<Layers2 size={22} />} title={!context.form ? "Your evidence starts here" : "Ready to investigate"}>{!context.form ? "Choose a form to follow its captured submissions and independent deliveries." : "Select a submission in the stream. Its payload, delivery outcomes and attempt history stay together here."}</Empty><button type="button" className="button" onClick={() => setSourceOpen(true)}>Browse forms<ArrowUpRight size={14} aria-hidden="true" /></button></div> : <>
          <div className="investigation-heading"><div><div className="eyebrow"><span className="capture-check"><Check size={11} aria-hidden="true" /></span>CAPTURED SUBMISSION</div><div className="submission-title"><h2>Submission <span>#{submission.id}</span></h2><CopyButton value={String(submission.id)} label="Copy submission ID" compact /></div><div className="capture-time"><Time value={submission.created_at} /></div></div><div className="investigation-tools"><div className="button-group adjacent-controls"><button className="icon-button" type="button" aria-label="Newer submission" disabled={selectedIndex <= 0} onClick={() => selectSubmission(rows[selectedIndex - 1].id)}><ArrowUp size={15} /></button><button className="icon-button" type="button" aria-label="Older submission" disabled={selectedIndex < 0 || selectedIndex >= rows.length - 1} onClick={() => selectSubmission(rows[selectedIndex + 1].id)}><ArrowDown size={15} /></button></div><CopyButton value={() => new URL(deskUrl(context), window.location.origin).href} label="Copy link" /></div></div>
          <div className="capture-strip"><span className="capture-confirmed"><CircleCheck size={14} aria-hidden="true" />Safely captured</span><span className="capture-connector" aria-hidden="true" /><span>{delivered}<span className="muted"> / {submission.deliveries.length} deliveries succeeded</span></span>{needsAttention > 0 && <span className="attention-count"><span className="small-dot" />{needsAttention} need{needsAttention === 1 ? "s" : ""} attention</span>}</div>
          <div className="inspection-switch" aria-label="Investigation pane"><button type="button" aria-pressed={inspectionFocus === "execution"} aria-controls="execution-panel" onClick={() => setInspectionFocus("execution")}>Delivery & attempts<span className="count">{submission.deliveries.length}</span></button><button type="button" aria-pressed={inspectionFocus === "payload"} aria-controls="payload-panel" onClick={() => setInspectionFocus("payload")}>Captured payload</button></div>
          <div className="investigation-grid" data-inspection-focus={inspectionFocus}><PayloadExplorer key={submission.id} payload={submission.payload} /><DeliveryExecution deliveries={submission.deliveries} resource={deliveryResource} selectedId={context.delivery} onSelect={(delivery) => navigate({ ...context, delivery })} refresh={refresh} /></div>
        </>}
      </section>
    </main>
    <footer className="desk-status"><span><span className="status-square" />CAPTURE → DELIVERY → EVIDENCE</span><span className="footer-checked">Checked <Time value={snapshot.checkedAt} mode="time" /> UTC</span><button type="button" onClick={() => setHelpOpen(true)}><kbd>?</kbd> Shortcuts</button></footer>
    {sourceOpen && <SourceSwitcher forms={snapshot.forms} current={context.form} offset={context.formsOffset} more={snapshot.moreForms} pending={pending} onClose={() => setSourceOpen(false)} refresh={refreshAll} onPage={(formsOffset) => navigate({ ...context, formsOffset })} onSelect={(form) => { setSourceOpen(false); setMobileView("stream"); navigate({ form, offset: 0, formsOffset: context.formsOffset }); }} />}
    {helpOpen && <Dialog title="Move through the evidence" onClose={() => setHelpOpen(false)}><dl className="shortcut-list"><div><dt>Switch form</dt><dd><kbd>⌘ / Ctrl</kbd><kbd>K</kbd></dd></div><div><dt>Search this stream page</dt><dd><kbd>/</kbd></dd></div><div><dt>Select adjacent submission</dt><dd><kbd>↑</kbd><kbd>↓</kbd><small>while a stream row is focused</small></dd></div><div><dt>Refresh evidence</dt><dd><kbd>R</kbd></dd></div><div><dt>Close a dialog</dt><dd><kbd>Esc</kbd></dd></div><div><dt>Show shortcuts</dt><dd><kbd>?</kbd></dd></div></dl></Dialog>}
  </div>;
}
