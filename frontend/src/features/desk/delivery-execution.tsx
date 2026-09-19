"use client";

import { ArrowUpRight, CircleHelp, GitBranch, Radio, Send } from "lucide-react";
import type { DeliveryDetail, DeliverySummary } from "@/lib/types";
import { ACTIVE_STATUSES, type Resource } from "./model";
import { CopyButton, Empty, Fault, Signal, Time } from "./primitives";
import { AttemptTrace } from "./attempt-trace";
import { ReplayControl } from "./replay-control";

const explanations = {
  pending: "Queued for a worker to pick up.",
  processing: "A worker is attempting delivery.",
  awaiting_retry: "A transient failure will be retried automatically.",
  succeeded: "A successful delivery outcome was recorded.",
  failed: "Delivery stopped. Inspect the evidence, then replay when ready.",
  unknown: "The provider outcome could not be confirmed. Review the evidence before replaying.",
};

export function DeliveryExecution({ deliveries, resource, selectedId, onSelect, refresh }: { deliveries: DeliverySummary[]; resource: Resource<DeliveryDetail>; selectedId?: number; onSelect: (id: number) => void; refresh: () => void }) {
  const delivery = resource.data;
  return <section className="execution-panel" aria-labelledby="execution-title" id="execution-panel">
    <div className="pane-title"><span className="section-label"><GitBranch size={15} aria-hidden="true" /><h2 id="execution-title">Delivery execution</h2><span className="count">{deliveries.length}</span></span><span className="muted small">Per destination</span></div>
    {deliveries.length > 0 && <div className="destination-list" aria-label="Choose delivery">{deliveries.map((item) => <button type="button" className={`destination ${item.id === selectedId ? "selected" : ""}`} key={item.id} aria-pressed={item.id === selectedId} onClick={() => onSelect(item.id)}><span className="destination-top"><Send size={13} aria-hidden="true" /><strong>Destination {item.destination_id}</strong><ArrowUpRight size={12} className="destination-arrow" aria-hidden="true" /></span><span className="destination-bottom"><Signal status={item.id === delivery?.id ? delivery.status : item.status} /><span className="mono muted">#{item.id}</span></span></button>)}</div>}
    {resource.error ? <Fault error={resource.error} onRetry={refresh} /> : !delivery ? <Empty icon={<CircleHelp size={23} />} title={deliveries.length ? "Select a delivery" : "Captured. No deliveries recorded."}>{deliveries.length ? "Choose a destination to inspect its execution evidence." : "This submission is stored, but there are no delivery records to inspect."}</Empty> : <div className="execution-body" key={delivery.id}>
      <div className="execution-identity"><span className="mono">DELIVERY / {delivery.id}</span><div className="button-group">{ACTIVE_STATUSES.includes(delivery.status) && <span className="live-label"><Radio size={12} aria-hidden="true" />Updating · 2s</span>}<CopyButton value={String(delivery.id)} label="Copy delivery ID" compact /></div></div>
      <div className={`outcome outcome-${delivery.status}`}><div className="outcome-heading"><Signal status={delivery.status} />{delivery.failure_type && <span className="failure-type">{delivery.failure_type === "permanent" ? "Permanent failure" : "Retries exhausted"}</span>}</div>{delivery.status !== "failed" && <p>{explanations[delivery.status]}</p>}
        {delivery.last_error && <div className="current-error"><span className="evidence-label">Last recorded error <CopyButton value={delivery.last_error} label="Copy last error" compact /></span><pre>{delivery.last_error}</pre></div>}
        {delivery.next_retry_at && <div className="outcome-time"><span>Next retry</span><Time value={delivery.next_retry_at} /></div>}
        {delivery.delivered_at && <div className="outcome-time"><span>Delivered</span><Time value={delivery.delivered_at} /></div>}
      </div>
      <ReplayControl deliveryId={delivery.id} destinationId={delivery.destination_id} eligible={delivery.status === "failed" || delivery.status === "unknown"} onQueued={refresh} />
      <div className="execution-facts"><span>Created <Time value={delivery.created_at} /></span><span><strong>{delivery.attempt_count}</strong> {delivery.attempt_count === 1 ? "attempt" : "attempts"}</span></div>
      <AttemptTrace attempts={delivery.attempts} />
    </div>}
  </section>;
}
