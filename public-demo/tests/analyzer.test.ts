import assert from "node:assert/strict";
import test from "node:test";
import { analyzeExplainJson } from "../lib/analyzer";
import { DEMO_FIXTURES } from "../lib/fixtures";

const expectedCategories = new Map([
  ["missing-index", "potential_missing_index"],
  ["nested-loop", "expensive_nested_loop"],
  ["disk-sort", "disk_based_sort"],
  ["cardinality", "cardinality_misestimation"],
  ["healthy", "no_clear_issue"],
]);

test("all public fixtures produce their expected deterministic category", () => {
  for (const fixture of DEMO_FIXTURES) {
    const result = analyzeExplainJson(fixture.json);
    assert.equal(result.category, expectedCategories.get(fixture.id));
  }
});

test("healthy plans do not produce an optimization suggestion", () => {
  const fixture = DEMO_FIXTURES.find((item) => item.id === "healthy");
  assert.ok(fixture);

  const result = analyzeExplainJson(fixture.json);

  assert.equal(result.insufficientContext, true);
  assert.equal(result.citation, undefined);
  assert.match(result.recommendation, /şema değişikliği yapmayın/i);
});

test("citations are category-bound and cannot come from input JSON", () => {
  const fixture = DEMO_FIXTURES.find((item) => item.id === "missing-index");
  assert.ok(fixture);
  const parsed = JSON.parse(fixture.json);
  parsed[0].Plan.Citation = {
    documentId: "invented-source-99",
    url: "https://example.invalid",
  };

  const result = analyzeExplainJson(JSON.stringify(parsed));

  assert.equal(result.citation?.documentId, "pg-indexes-01");
  assert.match(result.citation?.url ?? "", /^https:\/\/www\.postgresql\.org\//);
});

test("rejects oversized and malformed input before analysis", () => {
  assert.throws(() => analyzeExplainJson("{broken"), /Geçerli bir JSON/);
  assert.throws(
    () => analyzeExplainJson(`"${"x".repeat(200_001)}"`),
    /en fazla 200 KB/,
  );
});

test("rejects plans exceeding the public node limit", () => {
  let plan: Record<string, unknown> = {
    "Node Type": "Index Scan",
    "Plan Rows": 1,
    "Actual Rows": 1,
  };
  for (let index = 0; index < 251; index += 1) {
    plan = {
      "Node Type": "Result",
      "Plan Rows": 1,
      "Actual Rows": 1,
      Plans: [plan],
    };
  }

  assert.throws(
    () => analyzeExplainJson(JSON.stringify([{ Plan: plan }])),
    /en fazla 250 düğüm/,
  );
});
