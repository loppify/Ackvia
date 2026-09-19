import { test, expect, type Page } from "@playwright/test";

const form = "00000000-0000-4000-8000-000000000001";
const context = `/?form=${form}`;
const control = "http://127.0.0.1:8101/__control";
const stateUrl = "http://127.0.0.1:8101/__state";

test.beforeEach(async ({ request }) => {
  await request.post(control, { data: {} });
});

async function open(page: Page, suffix = "") {
  await page.goto(`${context}${suffix}`);
  await expect(page.getByRole("heading", { name: /Submission #/ })).toBeVisible();
}

test("opens a source-scoped investigation and enriches a bounded page", async ({ page, request }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Submission #23", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Fixture · contact", exact: true })).toBeVisible();
  await expect(page.getByText("Delivery evidence loaded", { exact: true })).toBeVisible();
  await expect(page.locator(".stream-row")).toHaveCount(20);
  await expect(page.locator(".capture-strip")).toContainText("1 / 2 deliveries succeeded");
  await expect(page.locator(".destination")).toHaveCount(2);
  const state = await (await request.get(stateUrl)).json();
  expect(state.maxReads).toBeLessThanOrEqual(4);
  expect(state.requests.filter((entry: { path: string }) => entry.path.endsWith("/submissions"))[0].query).toEqual({ limit: "21", offset: "0" });
  expect(new Set(state.requests.filter((entry: { path: string }) => /^\/api\/submissions\//.test(entry.path)).map((entry: { path: string }) => entry.path)).size).toBe(20);
});

test("retains stream, payload mode, selection, and browser history across destinations", async ({ page }) => {
  await open(page, "&submission=23&delivery=230");
  await page.getByRole("button", { name: "Raw JSON", exact: true }).click();
  await page.getByRole("button", { name: /Destination 8/ }).click();
  await expect(page).toHaveURL(/delivery=231/);
  await expect(page.locator(".outcome-succeeded")).toBeVisible();
  await expect(page.getByRole("button", { name: "Raw JSON", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator('[data-submission="23"]')).toHaveAttribute("aria-current", "true");
  await page.goBack();
  await expect(page.locator(".outcome-failed")).toBeVisible();
  await expect(page.locator(".stream-row")).toHaveCount(20);
});

test("new arrivals cannot replace the investigation selected on entry", async ({ page, request }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/submission=23.*delivery=230/);
  await expect(page.getByText("Delivery evidence loaded", { exact: true })).toBeVisible();
  await request.post("http://127.0.0.1:8101/__advance");
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.locator(".stream-row").first()).toHaveAttribute("data-submission", "24");
  await expect(page.getByRole("heading", { name: "Submission #23", exact: true })).toBeVisible();
  await expect(page.locator('[data-submission="23"]')).toHaveAttribute("aria-current", "true");
});

test("existing deep links map to the workspace, preserving pagination", async ({ page }) => {
  for (const [path, expected] of [
    ["/forms", /form=/],
    [`/forms/${form}`, /form=/],
    [`/forms/${form}/submissions/22?offset=20`, /submission=22.*offset=20/],
    [`/forms/${form}/submissions/23/deliveries/230`, /submission=23.*delivery=230/],
  ] as const) {
    await page.goto(path);
    await expect(page).toHaveURL(expected);
    await expect(page.locator("main.desk-workspace")).toBeVisible();
  }
  await expect(page.locator(".outcome-failed")).toBeVisible();
});

test("paginates submissions with lookahead and browses every form page", async ({ page }) => {
  await open(page);
  await page.getByRole("button", { name: "Next submissions", exact: true }).click();
  await expect(page).toHaveURL(/offset=20/);
  await expect(page.locator(".stream-row")).toHaveCount(3);
  await expect(page.locator(".stream-pagination")).toContainText("21–23");
  await expect(page.getByRole("button", { name: "Next submissions", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Previous submissions", exact: true }).click();
  await expect(page.locator(".stream-row")).toHaveCount(20);
  await page.getByRole("button", { name: "Switch form", exact: false }).click();
  await expect(page.locator(".source-option")).toHaveCount(20);
  await page.getByRole("button", { name: "Next forms", exact: true }).click();
  await expect(page.locator(".source-option")).toHaveCount(4);
  await expect(page.getByRole("button", { name: "Fixture · contact", exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Fixture form 24/ }).click();
  await expect(page.getByText("No submissions yet", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Fixture form 24", exact: true })).toBeVisible();
});

test("filters the loaded page honestly and retains filters on refresh", async ({ page }) => {
  await open(page);
  await expect(page.getByText("Delivery evidence loaded", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Attention/ }).click();
  await expect(page.locator(".stream-row")).toHaveCount(3);
  await expect(page.getByText("3 matches on this page", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.getByRole("button", { name: /Attention/ })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("textbox", { name: "Search this page", exact: true }).fill("23");
  await expect(page.locator(".stream-row")).toHaveCount(1);
  await page.getByRole("textbox", { name: "Search this page", exact: true }).fill("not-in-this-page");
  await expect(page.getByText("No matches on this page", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Submission #23", exact: true })).toBeVisible();
});

test("explores nested arbitrary JSON, empty values, raw data, search, and copy", async ({ page, context: browserContext }) => {
  await browserContext.grantPermissions(["clipboard-read", "clipboard-write"]);
  await open(page, "&submission=23");
  await page.getByRole("button", { name: "Expand all", exact: true }).click();
  await expect(page.locator(".json-null").first()).toHaveText("null");
  await expect(page.getByText("retained", { exact: true })).toBeVisible();
  await expect(page.getByText("Empty array", { exact: true })).toBeVisible();
  await expect(page.getByText("Empty object", { exact: true })).toBeVisible();
  await expect(page.locator(".payload-content img, .payload-content script")).toHaveCount(0);
  await page.getByRole("textbox", { name: "Find in payload", exact: true }).fill("proof");
  await expect(page.getByText("retained", { exact: true })).toBeVisible();
  await page.getByRole("textbox", { name: "Find in payload", exact: true }).fill("notpresent");
  await expect(page.getByText("No matching keys or values.")).toBeVisible();
  await page.getByRole("textbox", { name: "Find in payload", exact: true }).clear();
  await page.getByRole("button", { name: "Raw JSON", exact: true }).click();
  await expect(page.locator(".raw-json")).toContainText('"score": 0');
  await page.getByRole("button", { name: "Copy payload", exact: true }).click();
  expect(JSON.parse(await page.evaluate(() => navigator.clipboard.readText())).meta.consent).toBe(true);
  await open(page, "&submission=15");
  await expect(page.getByText("No captured fields", { exact: true })).toBeVisible();
});

test("keeps original chronological attempt numbers in newest-first history", async ({ page }) => {
  await open(page, "&submission=23&delivery=230");
  await expect(page.locator(".attempt-number")).toHaveText(["04", "03", "02", "01"]);
  await page.locator(".attempt summary").first().click();
  await expect(page.locator(".attempt").first()).toContainText("Manual replay");
  await expect(page.locator(".attempt").first()).toContainText("#2304");
  await expect(page.locator(".attempt").first()).toContainText("1.00 s");
  await page.locator(".attempt summary").last().click();
  await expect(page.locator(".attempt").last()).toContainText("Automatic");
  await expect(page.locator(".attempt").last()).toContainText("Retryable failure");
});

test("renders all six delivery states, exhaustion, unrecorded result, and no deliveries", async ({ page }) => {
  for (const [id, status] of [[23, "failed"], [22, "succeeded"], [21, "unknown"], [20, "awaiting_retry"], [19, "processing"], [18, "pending"]] as const) {
    await open(page, `&submission=${id}&delivery=${id * 10}`);
    await expect(page.locator(`.outcome-${status}`)).toBeVisible();
    await expect(page.getByRole("button", { name: "Replay delivery", exact: true })).toHaveCount(status === "failed" || status === "unknown" ? 1 : 0);
  }
  await expect(page.getByText("No attempts recorded yet.", { exact: false })).toBeVisible();
  await open(page, "&submission=19");
  await page.locator(".attempt summary").click();
  await expect(page.getByText("No result recorded", { exact: true })).toBeVisible();
  await expect(page.getByText("Not finished", { exact: true })).toBeVisible();
  await open(page, "&submission=16");
  await expect(page.getByText("Retries exhausted", { exact: true })).toBeVisible();
  await open(page, "&submission=17");
  await expect(page.getByText("Captured. No deliveries recorded.")).toBeVisible();
  await expect(page.getByText("Safely captured", { exact: true })).toBeVisible();
});

test("replay requires confirmation, shows pending, preserves history, and polls to success", async ({ page, request }) => {
  await open(page, "&submission=23&delivery=230");
  await page.getByRole("button", { name: "Replay delivery", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("does not confirm delivery");
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  expect((await (await request.get(stateUrl)).json()).replayCalls).toBe(0);
  await page.getByRole("button", { name: "Replay delivery", exact: true }).click();
  await page.getByRole("button", { name: "Queue replay", exact: true }).click();
  await expect(page.getByRole("button", { name: "Queueing replay…", exact: true })).toBeDisabled();
  await expect(page.getByText("Replay queued. Queueing alone does not confirm provider delivery.")).toBeVisible();
  await expect(page.locator(".outcome-pending")).toBeVisible();
  await expect(page.locator(".attempt-number")).toHaveText(["04", "03", "02", "01"]);
  await page.locator(".attempt summary").last().click();
  await page.getByRole("button", { name: "Raw JSON", exact: true }).click();
  await expect(page.locator(".outcome-succeeded")).toBeVisible({ timeout: 12000 });
  await expect(page.locator(".attempt-number")).toHaveText(["05", "04", "03", "02", "01"]);
  await expect(page.locator(".attempt details").last()).toHaveAttribute("open", "");
  await expect(page.getByRole("button", { name: "Raw JSON", exact: true })).toHaveAttribute("aria-pressed", "true");
  const before = (await (await request.get(stateUrl)).json()).requests.filter((entry: { path: string }) => entry.path === "/api/deliveries/230").length;
  await page.waitForTimeout(2500);
  const after = (await (await request.get(stateUrl)).json()).requests.filter((entry: { path: string }) => entry.path === "/api/deliveries/230").length;
  expect(after).toBe(before);
  expect((await (await request.get(stateUrl)).json()).replayCalls).toBe(1);
});

for (const [status, message] of [[404, "This delivery no longer exists."], [409, "This delivery is not replayable in its current state."], [500, "We couldn't queue the delivery replay."]] as const) {
  test(`replay ${status} is an actionable error without fabricated success`, async ({ page, request }) => {
    await request.post(control, { data: { replayStatus: status } });
    await open(page, "&submission=23&delivery=230");
    await page.getByRole("button", { name: "Replay delivery", exact: true }).click();
    await page.getByRole("button", { name: "Queue replay", exact: true }).click();
    await expect(page.getByRole("dialog").getByRole("alert")).toHaveText(message);
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByRole("button", { name: "Queue replay", exact: true })).toBeEnabled();
    await expect(page.getByText("Replay queued.", { exact: false })).toHaveCount(0);
  });
}

test("empty forms and submissions remain distinct from API errors", async ({ page, request }) => {
  await request.post(control, { data: { scenario: "empty-forms" } });
  await page.goto("/");
  await expect(page.getByText("Your evidence starts here", { exact: true })).toBeVisible();
  await expect(page.locator(".desk").getByRole("alert")).toHaveCount(0);
  await request.post(control, { data: { scenario: "empty-submissions" } });
  await page.goto(context);
  await expect(page.getByText("No submissions yet", { exact: true })).toBeVisible();
  await request.post(control, { data: { scenario: "forms-error" } });
  await page.goto("/");
  await expect(page.locator(".desk").getByRole("alert")).toContainText("Forms unavailable");
  await expect(page.getByText("No submissions yet", { exact: true })).toHaveCount(0);
  await request.post(control, { data: { scenario: "submissions-error" } });
  await page.goto(context);
  await expect(page.locator(".desk").getByRole("alert")).toContainText("Submissions unavailable");
});

test("isolates submission, delivery, and row evidence failures", async ({ page, request }) => {
  await request.post(control, { data: { failSubmission: 22, failDelivery: 230 } });
  await open(page, "&submission=23&delivery=230");
  await expect(page.locator(".desk").getByRole("alert")).toContainText("Delivery unavailable");
  await expect(page.getByRole("heading", { name: "Captured payload", exact: true })).toBeVisible();
  await expect(page.locator('[data-submission="22"]')).toContainText("Evidence unavailable");
  await page.locator('[data-submission="22"]').click();
  await expect(page.locator(".investigation").getByRole("alert")).toContainText("Submission unavailable");
  await expect(page.locator(".stream-row")).toHaveCount(20);
});

test("rejects invalid IDs and mismatched deep links", async ({ page }) => {
  for (const [query, message] of [
    ["&submission=23&delivery=220", "Delivery context does not match"],
    ["&submission=abc", "Submission ID is invalid"],
    ["&submission=9999", "Submission not found"],
    ["&submission=23&delivery=9999", "Delivery not found"],
  ]) {
    await page.goto(context + query);
    await expect(page.locator(".desk").getByRole("alert")).toContainText(message);
    await expect(page.getByRole("button", { name: "Replay delivery", exact: true })).toHaveCount(0);
  }
  await page.goto("/route-that-does-not-exist");
  await expect(page.getByRole("heading", { name: "This route doesn’t exist." })).toBeVisible();
});

test("keyboard navigation, dialog focus, search, and escape work", async ({ page }) => {
  await open(page);
  await expect(page.getByText("Delivery evidence loaded", { exact: true })).toBeVisible();
  await page.keyboard.press("Control+k");
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Find a form on this page", exact: true })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.keyboard.press("/");
  await expect(page.getByRole("textbox", { name: "Search this page", exact: true })).toBeFocused();
  await page.locator('[data-submission="23"]').focus();
  await page.keyboard.press("ArrowDown");
  await expect(page.getByRole("heading", { name: "Submission #22", exact: true })).toBeVisible();
  await expect(page.locator('[data-submission="22"]')).toBeFocused();
  await page.keyboard.press("?");
  await expect(page.getByRole("dialog")).toHaveAttribute("aria-label", "Move through the evidence");
  await page.keyboard.press("Escape");
  await expect(page.locator('[data-submission="22"]')).toBeFocused();
});

test("loading appears while the server is fetching evidence", async ({ page, request }) => {
  await request.post(control, { data: { readDelay: 450 } });
  await page.goto(context, { waitUntil: "commit" });
  await expect(page.getByRole("status", { name: "Loading investigation desk" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Submission #23", exact: true })).toBeVisible();
});

test("mobile controls are named and payload/stream context survives pane switching", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, "&submission=23&delivery=230");
  await page.getByRole("button", { name: "Switch form", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Find a form on this page" })).toBeFocused();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Captured payload", exact: true }).click();
  await page.getByRole("button", { name: "Raw JSON", exact: true }).click();
  await page.getByRole("button", { name: "Stream", exact: true }).click();
  await expect(page.locator('[data-submission="23"]')).toHaveAttribute("aria-current", "true");
  await page.getByRole("button", { name: "Investigation #23" }).click();
  await expect(page.getByRole("button", { name: "Raw JSON", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.keyboard.press("/");
  await expect(page.getByRole("textbox", { name: "Search this page", exact: true })).toBeFocused();
});

test("responsive desktop, laptop, tablet, mobile, long strings, and reduced motion", async ({ page, request }, testInfo) => {
  await request.post(control, { data: { scenario: "long" } });
  await open(page, "&submission=23&delivery=230");
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  for (const [name, width, height] of [["desktop", 1920, 1080], ["laptop", 1366, 768], ["tablet", 768, 1024], ["mobile", 390, 844], ["small-mobile", 320, 740]] as const) {
    await page.setViewportSize({ width, height });
    await expect(page.locator(".outcome-failed")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
    if (width < 1200) {
      await page.getByRole("button", { name: "Captured payload", exact: true }).click();
      await expect(page.getByRole("heading", { name: "Captured payload", exact: true })).toBeVisible();
      await page.getByRole("button", { name: "Raw JSON", exact: true }).click();
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
      await page.getByRole("button", { name: /Delivery & attempts/ }).click();
    }
    await page.screenshot({ path: testInfo.outputPath(`${name}.png`), fullPage: true });
  }
  await page.emulateMedia({ reducedMotion: "reduce" });
  await open(page, "&submission=19&delivery=190");
  expect(await page.locator(".signal-processing .spin").first().evaluate((element) => getComputedStyle(element).animationName)).toBe("none");
  expect(errors).toEqual([]);
});
