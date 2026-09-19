"use client";

import { ChevronRight, History, MousePointer2, RotateCw, Zap } from "lucide-react";
import type { DeliveryAttempt } from "@/lib/types";
import { CopyButton, Time } from "./primitives";
import { duration } from "./model";

const resultLabels = { succeeded: "Succeeded", permanent_failure: "Permanent failure", retryable_failure: "Retryable failure", unknown: "Unknown result" };
const triggerLabels = { automatic: "Automatic", retry: "Retry", manual_replay: "Manual replay" };

export function AttemptTrace({ attempts }: { attempts: DeliveryAttempt[] }) {
  const ordered = attempts.map((attempt, index) => ({ attempt, number: index + 1 })).reverse();
  return <section className="attempts" aria-labelledby="attempts-title"><div className="pane-title"><span className="section-label"><History size={15} aria-hidden="true" /><h2 id="attempts-title">Attempt history</h2><span className="count">{attempts.length}</span></span><span className="muted small">Newest first</span></div>
    {!ordered.length ? <div className="inline-empty">No attempts recorded yet. Execution evidence will appear here.</div> : <ol className="attempt-trace">{ordered.map(({ attempt, number }) => {
      const Icon = { automatic: Zap, retry: RotateCw, manual_replay: MousePointer2 }[attempt.trigger];
      return <li className={`attempt attempt-${attempt.result ?? "unrecorded"}`} key={attempt.id}>
        <span className="attempt-number" title={`Chronological attempt ${number}`}>{String(number).padStart(2, "0")}</span>
        <details>
          <summary><div className="attempt-summary"><div className="attempt-primary"><strong>{attempt.result ? resultLabels[attempt.result] : "No result recorded"}</strong><ChevronRight size={14} className="attempt-chevron" aria-hidden="true" /></div><div className="attempt-secondary"><span><Icon size={12} aria-hidden="true" />{triggerLabels[attempt.trigger]}</span><Time value={attempt.created_at} mode="time" /></div></div></summary>
          <div className="attempt-evidence"><dl className="evidence-facts"><div><dt>Attempt ID</dt><dd>#{attempt.id}</dd></div><div><dt>Duration</dt><dd>{duration(attempt.created_at, attempt.finished_at)}</dd></div><div className="fact-wide"><dt>Started</dt><dd><Time value={attempt.created_at} /></dd></div><div className="fact-wide"><dt>Finished</dt><dd>{attempt.finished_at ? <Time value={attempt.finished_at} /> : "Not recorded"}</dd></div></dl>
            {attempt.error ? <div className="error-evidence"><div className="evidence-label"><span>Recorded error</span><CopyButton value={attempt.error} label={`Copy error from attempt ${number}`} compact /></div><pre>{attempt.error}</pre></div> : <p className="no-error">{attempt.result === "succeeded" ? "Successful outcome recorded." : "No error evidence recorded."}</p>}
          </div>
        </details>
      </li>;
    })}</ol>}
  </section>;
}
