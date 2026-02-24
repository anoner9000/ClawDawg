import { test, expect } from "@playwright/test";

test("dashboard home renders key panels", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("ClawDawg Command Center")).toBeVisible();
  await expect(page.getByText("Recent Tasks")).toBeVisible();
  await expect(page.getByText("Governance Status")).toBeVisible();
});
