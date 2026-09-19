// Test-only HTTP fixture. Never imported by application code or used as a fallback.
import { createServer } from "node:http";

const formId = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const forms = Array.from({ length: 24 }, (_, index) => ({ id: formId(index + 1), title: index === 0 ? "Fixture · contact" : `Fixture form ${index + 1}` }));
const timestamp = (id, seconds = 0) => new Date(Date.UTC(2026, 8, 18, 9, id, seconds)).toISOString();
let options;
let deliveries;
let requests;
let replayCalls;
let activeReads;
let maxReads;
let timers = [];

function attempt(id, index, result, trigger) {
  return { id: id * 100 + index, created_at: timestamp(id, index * 2), finished_at: result === null ? null : timestamp(id, index * 2 + 1), result, error: result?.includes("failure") ? "Fixture destination rejected the request" : result === "unknown" ? "Provider acknowledgement not recorded" : null, trigger };
}

function reset(config = {}) {
  for (const timer of timers) clearTimeout(timer);
  timers = [];
  options = { scenario: "normal", replayDelay: 650, ...config };
  requests = [];
  replayCalls = 0;
  activeReads = 0;
  maxReads = 0;
  deliveries = {};
  for (let id = 1; id <= 24; id++) {
    const status = ({ 23: "failed", 22: "succeeded", 21: "unknown", 20: "awaiting_retry", 19: "processing", 18: "pending", 16: "failed" })[id] ?? "succeeded";
    const attempts = id === 18 ? [] : id === 23 ? [
      attempt(id, 1, "retryable_failure", "automatic"),
      attempt(id, 2, "retryable_failure", "retry"),
      attempt(id, 3, "permanent_failure", "retry"),
      attempt(id, 4, "permanent_failure", "manual_replay"),
    ] : [attempt(id, 1, status === "processing" ? null : status === "unknown" ? "unknown" : status === "awaiting_retry" ? "retryable_failure" : status === "failed" ? "retryable_failure" : "succeeded", "automatic")];
    deliveries[id * 10] = {
      id: id * 10, submission_id: id, destination_id: 7, status,
      attempt_count: attempts.length,
      last_error: status === "failed" ? (options.scenario === "long" ? `Long fixture error: ${"unbroken_error_string_".repeat(150)}\nProvider evidence line two.` : "Fixture destination rejected the request") : status === "unknown" ? "Provider acknowledgement not recorded" : null,
      next_retry_at: status === "awaiting_retry" ? timestamp(id + 1) : null,
      delivered_at: status === "succeeded" ? timestamp(id, 9) : null,
      created_at: timestamp(id), failure_type: status === "failed" ? id === 16 ? "retries_exhausted" : "permanent" : null,
      attempts,
    };
  }
  deliveries[231] = { ...deliveries[220], id: 231, submission_id: 23, destination_id: 8 };
  forms[0].title = options.scenario === "long" ? `Fixture long form ${"title_".repeat(60)}` : "Fixture · contact";
}

function payload(id) {
  if (id === 15) return {};
  return {
    name: `Fixture submission ${id}`,
    email: `fixture-${id}@example.test`,
    message: options.scenario === "long" ? "long_value_".repeat(250) : "A captured fixture, used only by the browser tests.",
    meta: { source: "website", consent: true, score: 0, absent: null, blank: "", tags: ["priority", 7, false, null, { nested: "value" }], deeper: { level: { proof: "retained" } }, emptyObject: {}, emptyArray: [] },
    "<script>alert('escaped')</script>": "<img src=x onerror=alert(1)>",
  };
}

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
reset();

createServer(async (request, response) => {
  const url = new URL(request.url, "http://127.0.0.1:8101");
  function send(body, status = 200) {
    response.writeHead(status, { "Content-Type": "application/json", "Cache-Control": "no-store" });
    response.end(JSON.stringify(body));
  }
  if (url.pathname === "/__control" && request.method === "POST") {
    let body = "";
    for await (const chunk of request) body += chunk;
    reset(JSON.parse(body || "{}"));
    return send({ ok: true });
  }
  if (url.pathname === "/__state") return send({ requests, replayCalls, maxReads, deliveries });
  if (url.pathname === "/__advance" && request.method === "POST") {
    options.newSubmission = true;
    return send({ ok: true });
  }
  requests.push({ path: url.pathname, query: Object.fromEntries(url.searchParams), method: request.method });
  if (options.readDelay) await wait(options.readDelay);
  if (url.pathname === "/api/forms") {
    if (options.scenario === "forms-error") return send({ detail: "Fixture API unavailable" }, 503);
    if (options.scenario === "empty-forms") return send([]);
    const offset = Number(url.searchParams.get("offset") ?? 0);
    const limit = Number(url.searchParams.get("limit") ?? 20);
    return send(forms.slice(offset, offset + limit));
  }
  const form = url.pathname.match(/^\/api\/forms\/([^/]+)\/submissions$/);
  if (form) {
    if (!forms.some((entry) => entry.id === form[1])) return send({ detail: "Form not found" }, 404);
    if (options.scenario === "submissions-error") return send({ detail: "Fixture submissions unavailable" }, 503);
    if (options.scenario === "empty-submissions" || form[1] !== formId(1)) return send([]);
    const offset = Number(url.searchParams.get("offset") ?? 0);
    const limit = Number(url.searchParams.get("limit") ?? 20);
    const total = options.newSubmission ? 24 : 23;
    return send(Array.from({ length: total }, (_, i) => ({ id: total - i, created_at: timestamp(total - i) })).slice(offset, offset + limit));
  }
  const submission = url.pathname.match(/^\/api\/submissions\/(\d+)$/);
  if (submission) {
    const id = Number(submission[1]);
    if (id > 24 || id < 1) return send({ detail: "Submission not found" }, 404);
    if (options.failSubmission === id) return send({ detail: "Fixture evidence unavailable" }, 503);
    activeReads++;
    maxReads = Math.max(maxReads, activeReads);
    await wait(40);
    activeReads--;
    const items = id === 17 ? [] : id === 23 ? [deliveries[230], deliveries[231]] : [deliveries[id * 10]];
    return send({ id, created_at: timestamp(id), payload: payload(id), deliveries: items.map(({ id, destination_id, status, attempt_count, last_error, next_retry_at, delivered_at }) => ({ id, destination_id, status, attempt_count, last_error, next_retry_at, delivered_at })) });
  }
  const delivery = url.pathname.match(/^\/api\/deliveries\/(\d+)(\/replay)?$/);
  if (delivery) {
    const id = Number(delivery[1]);
    const item = deliveries[id];
    if (!item) return send({ detail: "Delivery not found" }, 404);
    if (delivery[2]) {
      replayCalls++;
      await wait(options.replayDelay);
      if (options.replayStatus) return send({ detail: "Fixture replay error" }, options.replayStatus);
      if (!["failed", "unknown"].includes(item.status)) return send({ detail: "Delivery is not replayable" }, 409);
      item.status = "pending";
      item.failure_type = null;
      item.last_error = null;
      timers.push(setTimeout(() => { item.status = "processing"; }, 1200));
      timers.push(setTimeout(() => {
        item.status = "succeeded";
        item.delivered_at = timestamp(item.submission_id, 55);
        item.attempts.push(attempt(item.submission_id, item.attempts.length + 1, "succeeded", "manual_replay"));
        item.attempt_count = item.attempts.length;
      }, 3400));
      return send(item, 202);
    }
    if (options.failDelivery === id) return send({ detail: "Fixture delivery unavailable" }, 503);
    return send(item);
  }
  send({ detail: "Fixture route not found" }, 404);
}).listen(8101, "127.0.0.1", () => console.log("Test fixture API listening on 8101"));
