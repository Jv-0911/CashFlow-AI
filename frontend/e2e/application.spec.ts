import { test, expect } from "@playwright/test";

test("real forecast, scenario and fallback analysis render with explicit demo labels", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "A clearer view of your cash." }),
  ).toBeVisible();
  await expect(page.getByText("Opening cash", { exact: false })).toBeVisible();
  await expect(
    page.getByText("Reserve pressure from", { exact: false }),
  ).toBeVisible();
  await expect(page.getByText("SYNTHETIC DEMO", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Forecast", exact: true }).click();
  await expect(page.locator("tbody tr")).toHaveCount(14);
  await page.getByLabel("Forecast horizon").selectOption("7");
  await expect(page.locator("tbody tr")).toHaveCount(7);
  await page.getByRole("button", { name: "What-if lab", exact: true }).click();
  await page.getByRole("button", { name: "Run scenario" }).click();
  await expect(
    page.getByRole("heading", { name: "Baseline vs. your scenario" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Recovery", exact: true }).click();
  await page.getByRole("button", { name: "Analyze recovery" }).click();
  await expect(
    page.getByText("Deterministic analysis · no AI provider"),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Prepare action" }).first(),
  ).toBeDisabled();
  await page.screenshot({
    path: "test-results/recovery-desktop.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("mobile dashboard remains usable without horizontal overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Cash flow outlook" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/dashboard-mobile.png",
    fullPage: true,
  });
});

test("malformed or unreachable API hides financial values and supports retry", async ({
  page,
}) => {
  await page.route("**/api/v1/dashboard*", (route) =>
    route.fulfill({
      json: { forecast: { days: [{ closing_balance_cents: 1.5 }] } },
    }),
  );
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("unexpected response");
  await expect(page.getByText("Opening cash", { exact: false })).toHaveCount(0);
  await page.unroute("**/api/v1/dashboard*");
  await page.getByRole("button", { name: "Refresh safely" }).click();
  await expect(
    page.getByRole("heading", { name: "Cash flow outlook" }),
  ).toBeVisible();
  await page.route("**/api/v1/dashboard*", (route) => route.abort("failed"));
  await page.getByRole("button", { name: "↻ Refresh", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Connection interrupted");
  await expect(page.getByText("Opening cash", { exact: false })).toHaveCount(0);
});

test("browser approval, fake invoice send, pending observation, and fresh verification", async ({
  page,
}) => {
  await page.goto("http://127.0.0.1:8011");
  await page
    .getByLabel("Administrator password")
    .fill("e2e-only-" + process.env.CASHFLOW_E2E_RUN_ID);
  await page.getByRole("button", { name: "Sign in securely" }).click();
  await expect(
    page.getByRole("heading", { name: "Cash flow outlook" }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/dashboard-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Recovery", exact: true }).click();
  await page.getByRole("button", { name: "Prepare action" }).first().click();
  await page.getByRole("button", { name: "Review approval" }).click();
  await expect(
    page.getByRole("button", { name: "Record approval" }),
  ).toBeDisabled();
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Record approval" }).click();
  await page.route("**/api/v1/invoices", (route) =>
    route.fulfill({
      status: 503,
      json: {
        error: {
          code: "PAYMENT_STATUS_UNAVAILABLE",
          message: "Provider unavailable. No payment is verified.",
        },
      },
    }),
  );
  await page.getByRole("button", { name: "Create Sandbox draft" }).click();
  await expect(page.getByRole("alert")).toContainText("Provider unavailable");
  await expect(page.getByText("approved", { exact: true })).toBeVisible();
  await expect(page.getByText("verified paid", { exact: true })).toHaveCount(0);
  await page.unroute("**/api/v1/invoices");
  await page.getByRole("button", { name: "Create Sandbox draft" }).click();
  await page.getByRole("button", { name: "Send Sandbox invoice" }).click();
  await expect(page.getByText("invoice sent", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Ledger", exact: true }).click();
  await page.getByRole("button", { name: "Verify with PayPal" }).click();
  await expect(
    page.getByText("payment pending", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Verify with PayPal" }).click();
  await expect(page.getByText("verified paid", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await expect(page.locator(".metric.accent strong")).toHaveText("$3,200.00");
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByLabel("Administrator password")).toBeVisible();
});
