import { expect, test } from "@playwright/test";

const form = "00000000-0000-4000-8000-000000000001";
const cases = [
  { locale: "en-US", timezoneId: "America/Los_Angeles", viewport: { width: 1440, height: 960 } },
  { locale: "uk-UA", timezoneId: "Europe/Kyiv", viewport: { width: 390, height: 844 } },
  { locale: "ja-JP", timezoneId: "Asia/Tokyo", viewport: { width: 768, height: 1024 } },
];

for (const settings of cases) {
  test.describe(`Hydration: ${settings.locale}, ${settings.timezoneId}`, () => {
    test.use(settings);

    test("preserves SSR attributes and reports no console hydration errors", async ({ page, request }, testInfo) => {
      await request.post("http://127.0.0.1:8101/__control", { data: {} });

      // React attribute mismatches use console.error, not necessarily pageerror.
      // Install both listeners before loading any application JavaScript.
      const diagnostics: string[] = [];
      page.on("console", (message) => {
        if (message.type() === "error" || message.type() === "warning") {
          diagnostics.push(`${message.type()}: ${message.text()}`);
        }
      });
      page.on("pageerror", (error) => diagnostics.push(error.stack ?? error.message));

      let releaseScripts!: () => void;
      const scriptsReady = new Promise<void>((resolve) => { releaseScripts = resolve; });
      await page.route(/\/_next\/static\/.*\.js(?:\?.*)?$/, async (route) => {
        await scriptsReady;
        await route.continue();
      });

      const snapshot = () => page.evaluate(() => ({
        root: Object.fromEntries([...document.documentElement.attributes].map((attribute) => [attribute.name, attribute.value])),
        icon: Object.fromEntries([...document.querySelector(".command-source svg")!.attributes].map((attribute) => [attribute.name, attribute.value])),
        times: [...document.querySelectorAll(".desk time")].map((element) => ({
          datetime: element.getAttribute("datetime"),
          title: element.getAttribute("title"),
          text: element.textContent,
        })),
        mobileView: document.querySelector(".desk[data-mobile-view]")?.getAttribute("data-mobile-view"),
      }));

      const response = await page.goto(`/?form=${form}&submission=23&delivery=230`, { waitUntil: "commit" });
      let serverSnapshot: Awaited<ReturnType<typeof snapshot>>;
      try {
        const html = await response!.text();
        expect(html).toContain('<html lang="en">');
        expect(html).not.toMatch(/data-darkreader|--darkreader-inline/);
        await page.locator(".submission-title h2").waitFor({ state: "attached" });
        serverSnapshot = await snapshot();
        expect(serverSnapshot.root).toEqual({ lang: "en" });
        expect(serverSnapshot.times.length).toBeGreaterThan(0);
      } finally {
        releaseScripts();
      }

      // Enrichment only starts in a client effect. Completion proves hydration
      // ran; a visible server-rendered heading alone does not prove that.
      // The stream stays mounted but is hidden in the phone investigation view.
      await expect(page.locator(".stream-results")).toContainText("Delivery evidence loaded");
      await page.getByRole("button", { name: "Switch form", exact: true }).click();
      await expect(page.getByRole("dialog")).toBeVisible();
      await page.keyboard.press("Escape");

      expect(await snapshot()).toEqual(serverSnapshot);
      expect(diagnostics).toEqual([]);
      await testInfo.attach("ssr-hydration-comparison", {
        body: JSON.stringify({ settings, serverSnapshot, diagnostics }, null, 2),
        contentType: "application/json",
      });
    });
  });
}
