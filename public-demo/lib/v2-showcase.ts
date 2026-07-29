export interface WorkloadShowcase {
  id: string;
  rank: number;
  label: string;
  normalizedSql: string;
  calls: number;
  totalTimeMs: number;
  meanTimeMs: number;
  baselineTimeMs: number;
  currentTimeMs: number;
  baselineCost: number;
  currentCost: number;
  measurementGroup: "warm_cache";
  accessPathBefore: string;
  accessPathAfter: string;
}

export const SYNTHETIC_WORKLOAD: WorkloadShowcase[] = [
  {
    id: "orders-total",
    rank: 1,
    label: "Sipariş toplamı",
    normalizedSql:
      "SELECT customer_id, sum(total_amount) FROM orders WHERE created_at >= $1 GROUP BY customer_id",
    calls: 18,
    totalTimeMs: 1278.4,
    meanTimeMs: 71.02,
    baselineTimeMs: 38.4,
    currentTimeMs: 71.02,
    baselineCost: 1840.2,
    currentCost: 2816.8,
    measurementGroup: "warm_cache",
    accessPathBefore: "Bitmap Heap Scan",
    accessPathAfter: "Seq Scan",
  },
  {
    id: "customer-id",
    rank: 2,
    label: "Müşteri kimlik araması",
    normalizedSql: "SELECT id, email FROM customers WHERE id = $1",
    calls: 420,
    totalTimeMs: 37.8,
    meanTimeMs: 0.09,
    baselineTimeMs: 0.08,
    currentTimeMs: 0.09,
    baselineCost: 8.31,
    currentCost: 8.31,
    measurementGroup: "warm_cache",
    accessPathBefore: "Index Scan",
    accessPathAfter: "Index Scan",
  },
  {
    id: "support-count",
    rank: 3,
    label: "Destek olayı sayımı",
    normalizedSql:
      "SELECT event_type, count(*) FROM support_events WHERE created_at >= $1 GROUP BY event_type",
    calls: 9,
    totalTimeMs: 24.3,
    meanTimeMs: 2.7,
    baselineTimeMs: 2.5,
    currentTimeMs: 2.7,
    baselineCost: 912.4,
    currentCost: 912.4,
    measurementGroup: "warm_cache",
    accessPathBefore: "Seq Scan",
    accessPathAfter: "Seq Scan",
  },
];

export function regressionReasons(item: WorkloadShowcase): string[] {
  const reasons: string[] = [];
  const timeDelta = item.currentTimeMs - item.baselineTimeMs;
  if (
    item.currentTimeMs >= item.baselineTimeMs * 1.5 &&
    timeDelta >= 1
  ) {
    reasons.push(
      `Çalışma süresi ${item.baselineTimeMs.toFixed(2)} ms değerinden ${item.currentTimeMs.toFixed(2)} ms değerine çıktı.`,
    );
  }
  if (item.currentCost >= item.baselineCost * 1.25) {
    reasons.push(
      `Kök plan maliyeti ${item.baselineCost.toFixed(2)} değerinden ${item.currentCost.toFixed(2)} değerine çıktı.`,
    );
  }
  if (
    item.accessPathBefore.includes("Index") ||
    item.accessPathBefore.includes("Bitmap")
  ) {
    if (item.accessPathAfter === "Seq Scan") {
      reasons.push("İndeks destekli erişim sequential scan planına dönüştü.");
    }
  }
  return reasons;
}
