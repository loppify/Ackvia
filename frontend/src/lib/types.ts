export type UUID = string;
export type DateTimeString = string;

export interface Form {
  id: UUID;
  title: string;
}

export interface SubmissionSummary {
  id: number;
  created_at: DateTimeString;
}

export interface SubmissionDetail extends SubmissionSummary {
  payload: Record<string, unknown>;
  deliveries: DeliverySummary[];
}

export type DeliveryStatus =
  | "pending"
  | "succeeded"
  | "failed"
  | "unknown"
  | "awaiting_retry"
  | "processing";

export type FailureType = "permanent" | "retries_exhausted";

export type DeliveryAttemptResult =
  | "succeeded"
  | "retryable_failure"
  | "permanent_failure"
  | "unknown";

export type DeliveryTrigger = "automatic" | "retry" | "manual_replay";

export interface DeliverySummary {
  id: number;
  destination_id: number;
  status: DeliveryStatus;
  attempt_count: number;
  last_error: string | null;
  next_retry_at: DateTimeString | null;
  delivered_at: DateTimeString | null;
}

export interface DeliveryAttempt {
  id: number;
  created_at: DateTimeString;
  finished_at: DateTimeString | null;
  result: DeliveryAttemptResult | null;
  error: string | null;
  trigger: DeliveryTrigger;
}

export interface DeliveryDetail extends DeliverySummary {
  submission_id: number;
  failure_type: FailureType | null;
  created_at: DateTimeString;
  attempts: DeliveryAttempt[];
}

export interface ValidationError {
  type: string;
  loc: Array<string | number>;
  msg: string;
  input: unknown;
  ctx?: Record<string, unknown>;
}

export interface ApiError {
  detail: string | ValidationError[];
}
