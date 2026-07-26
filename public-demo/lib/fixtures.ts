export interface DemoFixture {
  id: string;
  title: string;
  description: string;
  expectedLabel: string;
  json: string;
}

const format = (value: unknown): string => JSON.stringify(value, null, 2);

export const DEMO_FIXTURES: DemoFixture[] = [
  {
    id: "missing-index",
    title: "Seçici filtre",
    description: "Müşteri e-postası aranırken satırların çoğu eleniyor.",
    expectedLabel: "Eksik indeks",
    json: format([
      {
        Plan: {
          "Node Type": "Seq Scan",
          "Relation Name": "customers",
          "Plan Rows": 1,
          "Actual Rows": 1,
          "Actual Loops": 1,
          "Rows Removed by Filter": 24999,
          Filter: "(email = 'demo@example.com'::text)",
        },
        "Execution Time": 3.7,
      },
    ]),
  },
  {
    id: "nested-loop",
    title: "Tekrarlanan join",
    description: "Nested loop içindeki indeks taraması binlerce kez çalışıyor.",
    expectedLabel: "Nested loop",
    json: format([
      {
        Plan: {
          "Node Type": "Nested Loop",
          "Plan Rows": 1200,
          "Actual Rows": 1200,
          "Actual Loops": 1,
          "Actual Total Time": 48.2,
          Plans: [
            {
              "Node Type": "Seq Scan",
              "Relation Name": "customers",
              "Plan Rows": 1200,
              "Actual Rows": 1200,
              "Actual Loops": 1,
            },
            {
              "Node Type": "Index Scan",
              "Relation Name": "orders",
              "Index Name": "idx_orders_customer_id",
              "Plan Rows": 1,
              "Actual Rows": 1,
              "Actual Loops": 6200,
            },
          ],
        },
        "Execution Time": 49.1,
      },
    ]),
  },
  {
    id: "disk-sort",
    title: "Diske taşan sort",
    description: "Sıralama çalışma belleğini aşarak geçici disk kullanıyor.",
    expectedLabel: "Disk sort",
    json: format([
      {
        Plan: {
          "Node Type": "Sort",
          "Plan Rows": 85000,
          "Actual Rows": 85000,
          "Actual Loops": 1,
          "Sort Method": "external merge",
          "Sort Space Used": 24576,
          "Sort Space Type": "Disk",
          Plans: [
            {
              "Node Type": "Seq Scan",
              "Relation Name": "orders",
              "Plan Rows": 85000,
              "Actual Rows": 85000,
              "Actual Loops": 1,
            },
          ],
        },
        "Execution Time": 182.4,
      },
    ]),
  },
  {
    id: "cardinality",
    title: "Tahmin sapması",
    description: "Planlanan ve gerçek satır sayıları arasında büyük fark var.",
    expectedLabel: "Tahmin hatası",
    json: format([
      {
        Plan: {
          "Node Type": "Bitmap Heap Scan",
          "Relation Name": "support_events",
          "Plan Rows": 10,
          "Actual Rows": 5000,
          "Actual Loops": 1,
        },
        "Execution Time": 24.6,
      },
    ]),
  },
  {
    id: "healthy",
    title: "Sağlıklı arama",
    description: "Birincil anahtar üzerinden tek satırlık hızlı erişim.",
    expectedLabel: "Güçlü sinyal yok",
    json: format([
      {
        Plan: {
          "Node Type": "Index Scan",
          "Relation Name": "customers",
          "Index Name": "customers_pkey",
          "Plan Rows": 1,
          "Actual Rows": 1,
          "Actual Loops": 1,
        },
        "Execution Time": 0.08,
      },
    ]),
  },
];
