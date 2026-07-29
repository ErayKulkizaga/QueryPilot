import assert from "node:assert/strict";
import test from "node:test";
import {
  regressionReasons,
  SYNTHETIC_WORKLOAD,
} from "../lib/v2-showcase";

test("synthetic workload is ranked deterministically by total time", () => {
  assert.deepEqual(
    SYNTHETIC_WORKLOAD.map((query) => query.rank),
    [1, 2, 3],
  );
  assert.deepEqual(
    [...SYNTHETIC_WORKLOAD]
      .sort((left, right) => right.totalTimeMs - left.totalTimeMs)
      .map((query) => query.id),
    SYNTHETIC_WORKLOAD.map((query) => query.id),
  );
});

test("regression evidence requires measured thresholds", () => {
  assert.equal(regressionReasons(SYNTHETIC_WORKLOAD[0]).length, 3);
  assert.deepEqual(regressionReasons(SYNTHETIC_WORKLOAD[1]), []);
  assert.deepEqual(regressionReasons(SYNTHETIC_WORKLOAD[2]), []);
});
