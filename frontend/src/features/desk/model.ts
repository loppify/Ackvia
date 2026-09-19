import type { DeliveryDetail, DeliveryStatus, Form, SubmissionDetail, SubmissionSummary } from "@/lib/types";

export const PAGE_SIZE = 20;
export const ACTIVE_STATUSES: DeliveryStatus[] = ["pending", "processing", "awaiting_retry"];

export type ResourceError = { title: string; message: string; status?: number };
export type Resource<T> = { data: T | null; error: ResourceError | null };
export type Query = Record<string, string | string[] | undefined>;
export type DeskContext = { form: string; submission?: number; delivery?: number; offset: number; formsOffset: number };
export type DeskSnapshot = {
  context: DeskContext;
  forms: Resource<Form[]>;
  moreForms: boolean;
  submissions: Resource<SubmissionSummary[]>;
  moreSubmissions: boolean;
  submission: Resource<SubmissionDetail>;
  delivery: Resource<DeliveryDetail>;
  checkedAt: string;
  linkedSelection: boolean;
};

export function first(value: Query[string]): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export function numericId(value: string | undefined): number | null {
  if (!value || !/^\d+$/.test(value)) return null;
  const id = Number(value);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}

export function offsetValue(value: Query[string]): number {
  const raw = first(value);
  if (!raw || !/^\d+$/.test(raw)) return 0;
  const number = Number(raw);
  return Number.isSafeInteger(number) && number <= 2147483647 ? number : 0;
}

export function deskUrl(context: Partial<DeskContext>): string {
  const params = new URLSearchParams();
  if (context.form) params.set("form", context.form);
  if (context.submission !== undefined) params.set("submission", String(context.submission));
  if (context.delivery !== undefined) params.set("delivery", String(context.delivery));
  if (context.offset) params.set("offset", String(context.offset));
  if (context.formsOffset) params.set("formsOffset", String(context.formsOffset));
  return params.size ? `/?${params}` : "/";
}

export type EvidenceState = "attention" | "active" | "delivered" | "captured";
export function evidenceState(submission: SubmissionDetail): EvidenceState {
  const deliveries = submission.deliveries;
  if (deliveries.some((d) => d.status === "failed" || d.status === "unknown")) return "attention";
  if (deliveries.some((d) => ACTIVE_STATUSES.includes(d.status))) return "active";
  if (deliveries.length && deliveries.every((d) => d.status === "succeeded")) return "delivered";
  return "captured";
}

export function payloadPreview(payload: unknown): string {
  if (!payload || typeof payload !== "object") return JSON.stringify(payload) ?? "Captured payload";
  const entries = Object.entries(payload);
  const entry = entries.find(([, value]) => typeof value === "string" && value.trim())
    ?? entries.find(([, value]) => value !== null && typeof value !== "object");
  return entry ? `${entry[0]}: ${String(entry[1])}` : `${entries.length} captured fields`;
}

export const statusLabels: Record<DeliveryStatus, string> = {
  pending: "Pending",
  processing: "Processing",
  awaiting_retry: "Awaiting retry",
  succeeded: "Succeeded",
  failed: "Failed",
  unknown: "Unknown",
};

export function dateTime(value: string, mode: "full" | "time" | "date" = "full"): string {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return value;
  const day = new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(date);
  const time = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false, timeZone: "UTC" }).format(date);
  return mode === "time" ? time : mode === "date" ? day : `${day}, ${time} UTC`;
}

export function duration(start: string, end: string | null): string {
  if (!end) return "Not finished";
  const milliseconds = new Date(end).getTime() - new Date(start).getTime();
  if (!Number.isFinite(milliseconds) || milliseconds < 0) return "Unavailable";
  return milliseconds < 1000 ? `${milliseconds} ms` : `${(milliseconds / 1000).toFixed(2)} s`;
}
