"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { AlertCircle, Check, CheckCircle2, CircleDashed, CircleHelp, Copy, LoaderCircle, RotateCw, X, XCircle } from "lucide-react";
import type { DeliveryStatus } from "@/lib/types";
import { dateTime, statusLabels, type ResourceError } from "./model";

export function Mark() {
  return <svg aria-hidden="true" width="29" height="29" viewBox="0 0 40 40"><path d="M7 29 19 9h6L13 29Zm14-9 7-11h6L21 31h-6Z" fill="currentColor" /></svg>;
}

export function Signal({ status }: { status: DeliveryStatus }) {
  const Icon = { pending: CircleDashed, processing: LoaderCircle, awaiting_retry: RotateCw, succeeded: CheckCircle2, failed: XCircle, unknown: CircleHelp }[status];
  return <span className={`signal signal-${status}`}><Icon size={13} aria-hidden="true" className={status === "processing" ? "spin" : undefined} />{statusLabels[status]}</span>;
}

export function Time({ value, mode = "full" }: { value: string; mode?: "full" | "time" | "date" }) {
  return <time dateTime={value} title={dateTime(value)}>{dateTime(value, mode)}</time>;
}

export function CopyButton({ value, label = "Copy", compact = false }: { value: string | (() => string); label?: string; compact?: boolean }) {
  const [feedback, setFeedback] = useState<"copied" | "failed" | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);
  async function copy() {
    try {
      await navigator.clipboard.writeText(typeof value === "function" ? value() : value);
      setFeedback("copied");
    } catch { setFeedback("failed"); }
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setFeedback(null), 2400);
  }
  return <span className="copy-control"><button type="button" className={compact ? "icon-button" : "button button-quiet"} title={label} aria-label={label} onClick={copy}>
    {feedback === "copied" ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
    {!compact && <span>{feedback === "copied" ? "Copied" : label}</span>}
  </button><span className={feedback === "failed" ? "copy-error" : "sr-only"} role="status">{feedback === "copied" ? `${label}: copied` : feedback === "failed" ? "Copy unavailable. Select and copy the text." : ""}</span></span>;
}

export function Fault({ error, onRetry }: { error: ResourceError; onRetry?: () => void }) {
  return <div className="fault" role="alert"><AlertCircle size={19} aria-hidden="true" /><div><strong>{error.title}</strong><p>{error.message}</p>{onRetry && <button className="button" type="button" onClick={onRetry}><RotateCw size={13} aria-hidden="true" />Try again</button>}</div></div>;
}

export function Empty({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return <div className="empty"><div className="empty-icon" aria-hidden="true">{icon}</div><strong>{title}</strong><p>{children}</p></div>;
}

export function Dialog({ title, children, onClose, className = "" }: { title: string; children: ReactNode; onClose: () => void; className?: string }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    const previous = document.activeElement;
    dialog?.showModal();
    dialog?.querySelector<HTMLElement>("[data-dialog-focus]")?.focus();
    return () => {
      dialog?.close();
      if (previous instanceof HTMLElement) previous.focus();
    };
  }, []);
  return <dialog ref={ref} aria-label={title} className={`desk-dialog ${className}`} onCancel={(event) => { event.preventDefault(); onClose(); }} onClick={(event) => {
    if (event.target !== event.currentTarget) return;
    const rect = event.currentTarget.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) onClose();
  }}><div className="dialog-heading"><strong>{title}</strong><button type="button" className="icon-button" aria-label="Close dialog" onClick={onClose}><X size={16} /></button></div>{children}</dialog>;
}
