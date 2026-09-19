"use client";

import { useRef, useState, useTransition } from "react";
import { ArrowRight, CheckCircle2, LoaderCircle, RotateCcw } from "lucide-react";
import { queueDeliveryReplay } from "./replay-action";
import { Dialog } from "./primitives";

export function ReplayControl({ deliveryId, destinationId, eligible, onQueued }: { deliveryId: number; destinationId: number; eligible: boolean; onQueued: () => void }) {
  const [confirm, setConfirm] = useState(false);
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [queued, setQueued] = useState(false);
  const inFlight = useRef(false);
  function replay() {
    if (inFlight.current) return;
    inFlight.current = true;
    setError(null);
    startTransition(async () => {
      try {
        const result = await queueDeliveryReplay(deliveryId);
        if (result.ok) {
          setQueued(true);
          setConfirm(false);
          onQueued();
        } else { setError(result.message); }
      } catch { setError("We couldn't queue the delivery replay. Check your connection and try again."); }
      finally { inFlight.current = false; }
    });
  }
  return <>
    {eligible && <div className="recovery"><div><strong>Recover this delivery</strong><p>Queues a new attempt. Preserves history.</p></div><button type="button" className="button button-primary" onClick={() => { setError(null); setConfirm(true); }} disabled={pending}><RotateCcw size={14} aria-hidden="true" />Replay delivery</button></div>}
    {queued && <div className="queued-notice" role="status"><CheckCircle2 size={15} aria-hidden="true" /><span>Replay queued. Queueing alone does not confirm provider delivery.</span></div>}
    {confirm && <Dialog title={`Replay delivery #${deliveryId}`} onClose={() => { if (!pending) setConfirm(false); }} className="replay-dialog"><div className="dialog-content"><div className="replay-route"><span>Submission captured</span><ArrowRight size={15} aria-hidden="true" /><span>Destination {destinationId}</span></div><h2>Queue another attempt?</h2><p>The original submission and attempt history are preserved. Queueing a replay does not confirm delivery to the provider.</p>{error && <p className="action-error" role="alert">{error}</p>}<div className="dialog-actions"><button className="button" type="button" disabled={pending} onClick={() => setConfirm(false)}>Cancel</button><button className="button button-primary" type="button" disabled={pending} onClick={replay}>{pending ? <LoaderCircle size={14} className="spin" aria-hidden="true" /> : <RotateCcw size={14} aria-hidden="true" />}{pending ? "Queueing replay…" : "Queue replay"}</button></div></div></Dialog>}
  </>;
}
