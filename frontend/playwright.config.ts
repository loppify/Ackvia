import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  expect: { timeout: 10000 },
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:3100",
    viewport: { width: 1440, height: 960 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: "node tests/fixture-api.mjs",
      url: "http://127.0.0.1:8101/__state",
      reuseExistingServer: false,
    },
    {
      command: "npm run start -- --port 3100",
      env: { ACKVIA_API_BASE_URL: "http://127.0.0.1:8101" },
      url: "http://127.0.0.1:3100",
      reuseExistingServer: false,
    },
  ],
});
