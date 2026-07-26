export type IssueCategory =
  | "potential_missing_index"
  | "expensive_nested_loop"
  | "disk_based_sort"
  | "cardinality_misestimation"
  | "no_clear_issue";

export type Severity = "low" | "medium" | "high";

export interface Citation {
  documentId: string;
  title: string;
  section: string;
  url: string;
}

export interface AnalysisResult {
  category: IssueCategory;
  categoryLabel: string;
  severity: Severity;
  severityLabel: string;
  summary: string;
  evidence: string[];
  recommendation: string;
  recommendationSql?: string;
  citation?: Citation;
  insufficientContext: boolean;
  inspectedNodes: number;
}

interface Finding extends Omit<AnalysisResult, "inspectedNodes"> {
  confidence: number;
}

type JsonObject = Record<string, unknown>;

const MAX_JSON_LENGTH = 200_000;
const MAX_PLAN_NODES = 250;

const CATEGORY_LABELS: Record<IssueCategory, string> = {
  potential_missing_index: "Eksik indeks sinyali",
  expensive_nested_loop: "Pahalı nested loop",
  disk_based_sort: "Diske taşan sıralama",
  cardinality_misestimation: "Satır tahmin hatası",
  no_clear_issue: "Belirgin sorun bulunamadı",
};

const SEVERITY_LABELS: Record<Severity, string> = {
  low: "Düşük",
  medium: "Orta",
  high: "Yüksek",
};

const CITATIONS: Record<Exclude<IssueCategory, "no_clear_issue">, Citation> = {
  potential_missing_index: {
    documentId: "pg-indexes-01",
    title: "PostgreSQL Indexes",
    section: "Indexes and selective predicates",
    url: "https://www.postgresql.org/docs/current/indexes.html",
  },
  expensive_nested_loop: {
    documentId: "pg-joins-01",
    title: "Using EXPLAIN",
    section: "Join plans and repeated inner execution",
    url: "https://www.postgresql.org/docs/current/using-explain.html",
  },
  disk_based_sort: {
    documentId: "pg-sorting-01",
    title: "Resource Consumption",
    section: "work_mem and temporary sort storage",
    url: "https://www.postgresql.org/docs/current/runtime-config-resource.html#GUC-WORK-MEM",
  },
  cardinality_misestimation: {
    documentId: "pg-statistics-01",
    title: "Planner Statistics",
    section: "Statistics used by the query planner",
    url: "https://www.postgresql.org/docs/current/planner-stats.html",
  },
};

const isObject = (value: unknown): value is JsonObject =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const numberValue = (
  node: JsonObject,
  key: string,
  fallback = 0,
): number => {
  const value = node[key];
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
};

const textValue = (node: JsonObject, key: string): string => {
  const value = node[key];
  return typeof value === "string" ? value : "";
};

const formatNumber = (value: number): string =>
  new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 1 }).format(value);

const categoryFinding = (
  category: Exclude<IssueCategory, "no_clear_issue">,
  severity: Severity,
  confidence: number,
  summary: string,
  evidence: string[],
  recommendation: string,
  recommendationSql?: string,
): Finding => ({
  category,
  categoryLabel: CATEGORY_LABELS[category],
  severity,
  severityLabel: SEVERITY_LABELS[severity],
  confidence,
  summary,
  evidence,
  recommendation,
  recommendationSql,
  citation: CITATIONS[category],
  insufficientContext: false,
});

function extractRoot(parsed: unknown): {
  root: JsonObject;
  executionTime: number;
} {
  const envelope = Array.isArray(parsed) ? parsed[0] : parsed;
  if (!isObject(envelope)) {
    throw new Error("EXPLAIN JSON bir nesne veya nesne dizisi olmalıdır.");
  }

  if (isObject(envelope.Plan)) {
    return {
      root: envelope.Plan,
      executionTime: numberValue(envelope, "Execution Time"),
    };
  }

  if (typeof envelope["Node Type"] === "string") {
    return { root: envelope, executionTime: 0 };
  }

  throw new Error(
    'Plan kökü bulunamadı. JSON içinde "Plan" veya "Node Type" alanı olmalıdır.',
  );
}

function flattenPlan(root: JsonObject): JsonObject[] {
  const nodes: JsonObject[] = [];
  const stack: JsonObject[] = [root];

  while (stack.length > 0) {
    const node = stack.pop();
    if (!node) continue;
    nodes.push(node);
    if (nodes.length > MAX_PLAN_NODES) {
      throw new Error(
        `Plan en fazla ${MAX_PLAN_NODES} düğüm içerebilir.`,
      );
    }

    const children = node.Plans;
    if (!Array.isArray(children)) continue;
    for (let index = children.length - 1; index >= 0; index -= 1) {
      const child = children[index];
      if (!isObject(child)) {
        throw new Error("Plan içindeki her alt düğüm bir JSON nesnesi olmalıdır.");
      }
      stack.push(child);
    }
  }

  return nodes;
}

function safeIndexSql(node: JsonObject): string | undefined {
  const relation = textValue(node, "Relation Name");
  const filter = textValue(node, "Filter");
  const identifier = /^[A-Za-z_][A-Za-z0-9_]*$/;
  const columnMatch = filter.match(
    /\(?([A-Za-z_][A-Za-z0-9_]*)\s*(?:=|<=|>=|<|>)/,
  );
  if (!identifier.test(relation) || !columnMatch) return undefined;
  const column = columnMatch[1];
  if (!identifier.test(column)) return undefined;
  return `CREATE INDEX idx_${relation}_${column} ON ${relation} (${column});`;
}

function missingIndexFindings(nodes: JsonObject[]): Finding[] {
  const findings: Finding[] = [];
  for (const node of nodes) {
    if (textValue(node, "Node Type") !== "Seq Scan") continue;
    const filter = textValue(node, "Filter");
    if (!filter) continue;

    const loops = Math.max(numberValue(node, "Actual Loops", 1), 1);
    const actualRows = numberValue(node, "Actual Rows") * loops;
    const removed = numberValue(node, "Rows Removed by Filter") * loops;
    const examined = actualRows + removed;
    const selectivity = actualRows / Math.max(examined, 1);
    if (!(removed >= 5_000 || (examined >= 1_000 && selectivity <= 0.1))) {
      continue;
    }

    const relation =
      textValue(node, "Relation Name") ||
      textValue(node, "Alias") ||
      "bir tablo";
    const severity: Severity = removed >= 10_000 ? "high" : "medium";
    findings.push(
      categoryFinding(
        "potential_missing_index",
        severity,
        Math.min(0.98, 0.72 + (1 - selectivity) * 0.2),
        `${relation} üzerinde yapılan sıralı tarama, incelenen satırların çoğunu eledi.`,
        [
          `Düğüm: Seq Scan on ${relation}`,
          `Filtreyle elenen satır: ${formatNumber(removed)}`,
          `Filtre seçiciliği: %${formatNumber(selectivity * 100)}`,
        ],
        "Seçici filtreyle başlayan bir indeksi inceleyin. Uygulamadan önce yazma maliyetini ve yeni planı karşılaştırın.",
        safeIndexSql(node),
      ),
    );
  }
  return findings;
}

function nestedLoopFindings(nodes: JsonObject[]): Finding[] {
  const findings: Finding[] = [];
  for (const node of nodes) {
    if (textValue(node, "Node Type") !== "Nested Loop") continue;
    const children = Array.isArray(node.Plans)
      ? node.Plans.filter(isObject)
      : [];
    if (children.length < 2) continue;
    const inner = children[1];
    const innerLoops = numberValue(inner, "Actual Loops");
    const totalTime = numberValue(node, "Actual Total Time");
    if (
      innerLoops < 100 ||
      !(totalTime >= 5 || innerLoops >= 1_000)
    ) {
      continue;
    }

    const severity: Severity = innerLoops >= 5_000 ? "high" : "medium";
    findings.push(
      categoryFinding(
        "expensive_nested_loop",
        severity,
        Math.min(0.96, 0.7 + innerLoops / 50_000),
        "Nested loop, iç planı çok sayıda tekrar çalıştırıyor.",
        [
          `Nested Loop toplam süresi: ${formatNumber(totalTime)} ms`,
          `İç düğüm: ${textValue(inner, "Node Type") || "Bilinmiyor"}`,
          `İç plan tekrarı: ${formatNumber(innerLoops)}`,
        ],
        "Join anahtarlarındaki indeksleri, join seçiciliğini ve istatistikleri inceleyin. Join türünü zorlamadan alternatif planları karşılaştırın.",
      ),
    );
  }
  return findings;
}

function diskSortFindings(nodes: JsonObject[]): Finding[] {
  const findings: Finding[] = [];
  for (const node of nodes) {
    if (textValue(node, "Node Type") !== "Sort") continue;
    const method = textValue(node, "Sort Method");
    const spaceType = textValue(node, "Sort Space Type");
    const tempBlocks =
      numberValue(node, "Temp Read Blocks") +
      numberValue(node, "Temp Written Blocks");
    const usesDisk =
      method.toLowerCase().includes("external") ||
      spaceType.toLowerCase() === "disk" ||
      tempBlocks > 0;
    if (!usesDisk) continue;

    const usedKb = numberValue(node, "Sort Space Used");
    const severity: Severity =
      usedKb >= 100_000 || tempBlocks >= 10_000 ? "high" : "medium";
    findings.push(
      categoryFinding(
        "disk_based_sort",
        severity,
        0.96,
        "Sıralama işlemi çalışma belleğinden geçici disk alanına taştı.",
        [
          `Sort Method: ${method || "Bilinmiyor"}`,
          `Sort Space Type: ${spaceType || "Bilinmiyor"}`,
          `Sort Space Used: ${formatNumber(usedKb)} kB`,
        ],
        "Önce sıralamaya giren satırları azaltın ve sıralamayı destekleyen bir indeksi değerlendirin. work_mem ayarını yalnızca plan karşılaştırmasından sonra sorgu oturumu düzeyinde inceleyin.",
      ),
    );
  }
  return findings;
}

function cardinalityFindings(nodes: JsonObject[]): Finding[] {
  let strongest:
    | { node: JsonObject; errorFactor: number; ratio: number }
    | undefined;

  for (const node of nodes) {
    const planned = numberValue(node, "Plan Rows");
    const actual = numberValue(node, "Actual Rows");
    if (planned <= 0) continue;
    const ratio = actual / planned;
    if (!(ratio >= 10 || ratio <= 0.1)) continue;
    const errorFactor = Math.max(ratio, 1 / Math.max(ratio, 0.000001));
    if (!strongest || errorFactor > strongest.errorFactor) {
      strongest = { node, errorFactor, ratio };
    }
  }

  if (!strongest) return [];
  const { node, errorFactor } = strongest;
  const severity: Severity = errorFactor >= 100 ? "high" : "medium";
  return [
    categoryFinding(
      "cardinality_misestimation",
      severity,
      Math.min(0.97, 0.7 + errorFactor / 1_000),
      "Planlayıcının satır tahminiyle gözlenen satır sayısı belirgin biçimde farklı.",
      [
        `Düğüm: ${textValue(node, "Node Type") || "Bilinmiyor"}`,
        `Planlanan satır: ${formatNumber(numberValue(node, "Plan Rows"))}`,
        `Gerçek satır: ${formatNumber(numberValue(node, "Actual Rows"))}`,
        `Tahmin hatası: ${formatNumber(errorFactor)}x`,
      ],
      "İstatistikleri yenileyin; veri korelasyonu ve dağılım çarpıklığını inceleyin. Kanıt destekliyorsa daha yüksek istatistik hedeflerini veya extended statistics seçeneğini değerlendirin.",
    ),
  ];
}

const severityScore: Record<Severity, number> = {
  low: 1,
  medium: 2,
  high: 3,
};

const categoryPriority: Record<IssueCategory, number> = {
  potential_missing_index: 4,
  disk_based_sort: 3,
  expensive_nested_loop: 2,
  cardinality_misestimation: 1,
  no_clear_issue: 0,
};

export function analyzeExplainJson(rawJson: string): AnalysisResult {
  if (!rawJson.trim()) {
    throw new Error("Analiz edilecek EXPLAIN JSON verisini girin.");
  }
  if (rawJson.length > MAX_JSON_LENGTH) {
    throw new Error("EXPLAIN JSON en fazla 200 KB olabilir.");
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(rawJson);
  } catch {
    throw new Error("Geçerli bir JSON girin.");
  }

  const { root, executionTime } = extractRoot(parsed);
  const nodes = flattenPlan(root);
  const findings = [
    ...missingIndexFindings(nodes),
    ...nestedLoopFindings(nodes),
    ...diskSortFindings(nodes),
    ...cardinalityFindings(nodes),
  ];

  if (findings.length === 0) {
    return {
      category: "no_clear_issue",
      categoryLabel: CATEGORY_LABELS.no_clear_issue,
      severity: "low",
      severityLabel: SEVERITY_LABELS.low,
      summary: "Yapılandırılmış kurallar güçlü bir performans sinyali bulmadı.",
      evidence: [
        `İncelenen plan düğümü: ${nodes.length}`,
        `Execution Time: ${formatNumber(executionTime)} ms`,
      ],
      recommendation:
        "Bu plandan hareketle şema değişikliği yapmayın. Sorgu hâlâ yavaşsa temsili iş yükünden ek kanıt toplayın.",
      insufficientContext: true,
      inspectedNodes: nodes.length,
    };
  }

  findings.sort(
    (left, right) =>
      severityScore[right.severity] - severityScore[left.severity] ||
      categoryPriority[right.category] - categoryPriority[left.category] ||
      right.confidence - left.confidence,
  );

  const primary = findings[0];
  return {
    category: primary.category,
    categoryLabel: primary.categoryLabel,
    severity: primary.severity,
    severityLabel: primary.severityLabel,
    summary: primary.summary,
    evidence: primary.evidence,
    recommendation: primary.recommendation,
    recommendationSql: primary.recommendationSql,
    citation: primary.citation,
    insufficientContext: primary.insufficientContext,
    inspectedNodes: nodes.length,
  };
}
