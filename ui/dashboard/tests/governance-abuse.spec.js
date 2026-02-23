import { test, expect } from "@playwright/test";

test("home intel feed clamps limit and rejects invalid filters", async ({ request }) => {
  const clamped = await request.get("/api/home-intel/feed?limit=9999");
  expect(clamped.ok()).toBeTruthy();
  const clampedBody = await clamped.json();
  expect(clampedBody.ok).toBeTruthy();
  expect(clampedBody.filters.limit).toBe(50);

  const invalid = await request.get("/api/home-intel/feed?actor=%3Cscript%3E");
  expect(invalid.ok()).toBeTruthy();
  const invalidBody = await invalid.json();
  expect(invalidBody.ok).toBeFalsy();
  expect(invalidBody.error).toContain("Invalid actor");
});

test("task drawer rejects path-like task ids", async ({ request }) => {
  const res = await request.get("/partials/task-drawer?task_id=../../etc/passwd");
  expect(res.status()).toBe(400);
  const body = await res.text();
  expect(body).toContain("Invalid task id");
});

test("ui audit endpoint validates payload shape", async ({ request }) => {
  const bad = await request.post("/actions/ui-audit", { data: { event_type: "###" } });
  expect(bad.ok()).toBeTruthy();
  const badBody = await bad.json();
  expect(badBody.ok).toBeFalsy();
  expect(badBody.error).toBe("invalid_event_type");

  const good = await request.post("/actions/ui-audit", {
    data: {
      event_type: "UI_TEST_AUDIT",
      result: "ok",
      reason: "smoke",
      detail: "playwright",
      action_id: "test_suite",
    },
  });
  expect(good.ok()).toBeTruthy();
  const goodBody = await good.json();
  expect(goodBody.ok).toBeTruthy();
});
