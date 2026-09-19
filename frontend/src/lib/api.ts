import type {
  ApiError,
  DeliveryDetail,
  Form,
  SubmissionDetail,
  SubmissionSummary,
  UUID,
  ValidationError,
} from "@/lib/types";

type PaginationParams = {
  limit?: number;
  offset?: number;
};

export class AckviaApiError extends Error {
  readonly status: number;
  readonly detail: ApiError["detail"] | null;

  constructor(status: number, detail: ApiError["detail"] | null) {
    super(detailMessage(detail) ?? `Ackvia API request failed (${status})`);
    this.name = "AckviaApiError";
    this.status = status;
    this.detail = detail;
  }
}

function getApiBaseUrl(): string {
  const baseUrl = process.env.ACKVIA_API_BASE_URL;

  if (!baseUrl) {
    throw new Error("ACKVIA_API_BASE_URL is not configured");
  }

  return baseUrl.replace(/\/$/, "");
}

function buildQuery(params: PaginationParams): string {
  const query = new URLSearchParams();

  if (params.limit !== undefined) {
    query.set("limit", String(params.limit));
  }

  if (params.offset !== undefined) {
    query.set("offset", String(params.offset));
  }

  const value = query.toString();
  return value ? `?${value}` : "";
}

function detailMessage(detail: ApiError["detail"] | null): string | null {
  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail.map((error) => error.msg).join(", ");
  }

  return null;
}

function extractDetail(payload: unknown): ApiError["detail"] | null {
  if (typeof payload === "string") {
    return payload || null;
  }

  if (!payload || typeof payload !== "object" || !("detail" in payload)) {
    return null;
  }

  const detail = payload.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail as ValidationError[];
  }

  return null;
}

async function readErrorDetail(response: Response): Promise<ApiError["detail"] | null> {
  const body = await response.text();

  if (!body) {
    return null;
  }

  try {
    return extractDetail(JSON.parse(body));
  } catch {
    return body;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    signal: init?.signal ?? AbortSignal.timeout(15000),
    cache: "no-store",
    headers: {
      Accept: "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw new AckviaApiError(response.status, await readErrorDetail(response));
  }

  return response.json() as Promise<T>;
}

export function listForms(params: PaginationParams = {}): Promise<Form[]> {
  return request<Form[]>(`/api/forms${buildQuery(params)}`);
}

export function listFormSubmissions(
  formId: UUID,
  params: PaginationParams = {},
): Promise<SubmissionSummary[]> {
  return request<SubmissionSummary[]>(
    `/api/forms/${encodeURIComponent(formId)}/submissions${buildQuery(params)}`,
  );
}

export function getSubmission(submissionId: number): Promise<SubmissionDetail> {
  return request<SubmissionDetail>(
    `/api/submissions/${encodeURIComponent(String(submissionId))}`,
  );
}

export function getDelivery(deliveryId: number): Promise<DeliveryDetail> {
  return request<DeliveryDetail>(
    `/api/deliveries/${encodeURIComponent(String(deliveryId))}`,
  );
}

export function replayDelivery(deliveryId: number): Promise<DeliveryDetail> {
  return request<DeliveryDetail>(
    `/api/deliveries/${encodeURIComponent(String(deliveryId))}/replay`,
    { method: "POST" },
  );
}
