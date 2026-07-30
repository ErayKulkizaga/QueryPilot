"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  analyzeExplainJson,
  type AnalysisResult,
  type Severity,
} from "../lib/analyzer";
import { DEMO_FIXTURES } from "../lib/fixtures";
import {
  publicAiRequestFromAnalysis,
  type PublicAiExplanation,
} from "../lib/public-ai";
import {
  regressionReasons,
  SYNTHETIC_WORKLOAD,
} from "../lib/v2-showcase";

type InputMode = "samples" | "json";

const severityClass: Record<Severity, string> = {
  low: "severity-low",
  medium: "severity-medium",
  high: "severity-high",
};

function CheckIcon() {
  return <span aria-hidden="true">✓</span>;
}

function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <span className="brand-glyph">
        <span className="brand-glyph-node brand-glyph-root" />
        <span className="brand-glyph-path" />
        <span className="brand-glyph-node brand-glyph-top" />
        <span className="brand-glyph-node brand-glyph-bottom" />
      </span>
    </span>
  );
}

interface AiCitation {
  chunkId: string;
  documentId: string;
  title: string;
  section: string;
  url: string;
}

function ResultPanel({
  result,
  aiExplanation,
  aiCitation,
  aiError,
  aiLoading,
  onRequestAi,
}: {
  result: AnalysisResult;
  aiExplanation: PublicAiExplanation | null;
  aiCitation: AiCitation | null;
  aiError: string;
  aiLoading: boolean;
  onRequestAi: () => void;
}) {
  return (
    <section className="result-panel" aria-live="polite">
      <div className="result-heading">
        <div>
          <p className="eyebrow">Deterministik sonuç</p>
          <h2>{result.categoryLabel}</h2>
        </div>
        <span className={`severity ${severityClass[result.severity]}`}>
          {result.severityLabel}
        </span>
      </div>

      <p className="result-summary">{result.summary}</p>

      {result.insufficientContext && (
        <div className="no-answer">
          <strong>Öneri üretilmedi.</strong>
          <span> Kural motoru yeterli plan kanıtı bulamadı.</span>
        </div>
      )}

      <div className="result-grid">
        <div className="result-card">
          <h3>Plan kanıtı</h3>
          <ul>
            {result.evidence.map((item) => (
              <li key={item}>
                <CheckIcon />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="result-card recommendation-card">
          <h3>{result.insufficientContext ? "Sonraki adım" : "Öneri"}</h3>
          <p>{result.recommendation}</p>
          {result.recommendationSql && (
            <pre>
              <code>{result.recommendationSql}</code>
            </pre>
          )}
        </div>
      </div>

      <div className="result-footer">
        <span>{result.inspectedNodes} plan düğümü incelendi</span>
        {result.citation && (
          <a href={result.citation.url} target="_blank" rel="noreferrer">
            {result.citation.title} · {result.citation.documentId}
            <span aria-hidden="true">↗</span>
          </a>
        )}
      </div>

      {!result.insufficientContext && (
        <section className="ai-enrichment" aria-live="polite">
          <div className="ai-enrichment-heading">
            <div>
              <p className="eyebrow">İsteğe bağlı AI + RAG</p>
              <h3>Kanıtı doğal dille açıkla</h3>
            </div>
            {!aiExplanation && (
              <button
                className="secondary-button"
                type="button"
                onClick={onRequestAi}
                disabled={aiLoading}
              >
                {aiLoading ? "AI açıklıyor…" : "AI + RAG ile açıkla"}
              </button>
            )}
          </div>
          <p className="ai-privacy-note">
            Planın tamamı gönderilmez. Yalnızca yukarıdaki kısa kanıt özeti,
            seçilen PostgreSQL kaynağıyla birlikte bulut modeline iletilir.
          </p>

          {aiError && (
            <div className="ai-message ai-message-error" role="alert">
              {aiError}
            </div>
          )}

          {aiExplanation && (
            <div className="ai-answer">
              <div>
                <span>AI açıklaması</span>
                <p>{aiExplanation.summary}</p>
              </div>
              <div>
                <span>Kanıta bağlı değerlendirme</span>
                <p>{aiExplanation.recommendation}</p>
              </div>
              <div className="ai-answer-footer">
                <span>
                  Google Gemini · {aiExplanation.model} · çıktı doğrulandı
                </span>
                {aiCitation && (
                  <a href={aiCitation.url} target="_blank" rel="noreferrer">
                    {aiCitation.title} · {aiCitation.documentId}
                    <span aria-hidden="true">↗</span>
                  </a>
                )}
              </div>
            </div>
          )}
        </section>
      )}
    </section>
  );
}

export function QueryPilotDemo() {
  const [mode, setMode] = useState<InputMode>("samples");
  const [fixtureId, setFixtureId] = useState(DEMO_FIXTURES[0].id);
  const activeFixture = useMemo(
    () =>
      DEMO_FIXTURES.find((fixture) => fixture.id === fixtureId) ??
      DEMO_FIXTURES[0],
    [fixtureId],
  );
  const [customJson, setCustomJson] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState("");
  const [analysisRun, setAnalysisRun] = useState(0);
  const [status, setStatus] = useState(
    "Bir senaryo seçin ve analizi başlatın.",
  );
  const [aiExplanation, setAiExplanation] =
    useState<PublicAiExplanation | null>(null);
  const [aiCitation, setAiCitation] = useState<AiCitation | null>(null);
  const [aiError, setAiError] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const resultRef = useRef<HTMLDivElement>(null);
  const [workloadId, setWorkloadId] = useState(SYNTHETIC_WORKLOAD[0].id);
  const selectedWorkload =
    SYNTHETIC_WORKLOAD.find((query) => query.id === workloadId) ??
    SYNTHETIC_WORKLOAD[0];
  const selectedRegressionReasons = regressionReasons(selectedWorkload);

  const inputJson = mode === "samples" ? activeFixture.json : customJson;

  useEffect(() => {
    if (analysisRun === 0 || !resultRef.current) return;
    resultRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    resultRef.current.focus({ preventScroll: true });
  }, [analysisRun]);

  function analyze() {
    try {
      setResult(analyzeExplainJson(inputJson));
      setAiExplanation(null);
      setAiCitation(null);
      setAiError("");
      setAiLoading(false);
      setError("");
      setAnalysisRun((current) => current + 1);
      setStatus("Analiz tamamlandı. Sonuç aşağıda gösteriliyor.");
    } catch (caught) {
      setResult(null);
      setStatus("Plan analiz edilemedi.");
      setError(
        caught instanceof Error
          ? caught.message
          : "Plan analiz edilirken beklenmeyen bir hata oluştu.",
      );
    }
  }

  function chooseFixture(id: string) {
    setFixtureId(id);
    const fixture = DEMO_FIXTURES.find((item) => item.id === id);
    if (fixture) {
      setResult(null);
      setError("");
      setAiExplanation(null);
      setAiCitation(null);
      setAiError("");
      setStatus(
        `"${fixture.title}" seçildi. Sonucu görmek için Planı analiz et düğmesine basın.`,
      );
    }
  }

  function chooseMode(nextMode: InputMode) {
    setMode(nextMode);
    setResult(null);
    setError("");
    setAiExplanation(null);
    setAiCitation(null);
    setAiError("");
    if (nextMode === "json") {
      setStatus(
        customJson
          ? "JSON hazır. Analizi başlatabilirsiniz."
          : "Bir EXPLAIN JSON yapıştırın veya örnek planı yükleyin.",
      );
    } else {
      setStatus(
        `"${activeFixture.title}" seçili. Sonucu görmek için analizi başlatın.`,
      );
    }
  }

  function loadExampleJson() {
    setCustomJson(DEMO_FIXTURES[0].json);
    setResult(null);
    setError("");
    setAiExplanation(null);
    setAiCitation(null);
    setAiError("");
    setStatus("Örnek EXPLAIN JSON yüklendi. Şimdi analizi başlatabilirsiniz.");
  }

  async function requestAiExplanation() {
    if (!result || aiLoading) return;
    const requestBody = publicAiRequestFromAnalysis(result);
    if (!requestBody) {
      setAiError("AI açıklaması için yeterli deterministik plan kanıtı yok.");
      return;
    }

    setAiLoading(true);
    setAiError("");
    try {
      const response = await fetch("/api/ai-explain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      });
      const payload: unknown = await response.json();
      if (
        !response.ok ||
        typeof payload !== "object" ||
        payload === null ||
        !("explanation" in payload)
      ) {
        const message =
          typeof payload === "object" &&
          payload !== null &&
          "error" in payload &&
          typeof payload.error === "string"
            ? payload.error
            : "AI açıklaması alınamadı. Deterministik sonuç geçerliliğini koruyor.";
        throw new Error(message);
      }
      setAiExplanation(payload.explanation as PublicAiExplanation);
      setAiCitation(
        "citation" in payload ? (payload.citation as AiCitation) : null,
      );
    } catch (caught) {
      setAiExplanation(null);
      setAiCitation(null);
      setAiError(
        caught instanceof Error
          ? caught.message
          : "AI açıklaması alınamadı. Deterministik sonuç geçerliliğini koruyor.",
      );
    } finally {
      setAiLoading(false);
    }
  }

  return (
    <main>
      <header className="site-header">
        <a className="brand" href="#top" aria-label="QueryPilot ana sayfa">
          <BrandMark />
          <span>QueryPilot</span>
        </a>
        <div className="header-actions">
          <span className="privacy-pill">
            Plan analizi tarayıcıda
          </span>
          <a className="text-link" href="#nasıl-çalışır">
            Nasıl çalışır?
          </a>
          <a className="text-link" href="#v2-kanıt">
            V2 kanıtı
          </a>
        </div>
      </header>

      <div id="top" className="hero-shell">
        <section className="hero">
          <div className="hero-copy">
            <p className="eyebrow">PostgreSQL plan analizi · Public demo</p>
            <h1>
              Yavaş sorgunun
              <span> kanıtını bulun.</span>
            </h1>
            <p className="hero-description">
              QueryPilot, EXPLAIN JSON planını doğrudan tarayıcınızda inceler.
              Kanıt bulunduğunda isteğe bağlı AI + RAG açıklaması sunar.
            </p>
            <div className="hero-points">
              <span><CheckIcon /> AI açıklaması isteğe bağlı</span>
              <span><CheckIcon /> SQL çalıştırılmaz</span>
              <span><CheckIcon /> Kaynaklar allowlist ile bağlı</span>
            </div>
          </div>
          <aside className="hero-proof">
            <p className="proof-label">Ölçülen MVP sonucu</p>
            <div className="proof-metric">
              <strong>12/12</strong>
              <span>Kural tanısı</span>
            </div>
            <div className="proof-metric">
              <strong>9/9</strong>
              <span>Retrieval Hit@3</span>
            </div>
            <div className="proof-metric">
              <strong>0</strong>
              <span>Model iddiası</span>
            </div>
            <p className="proof-note">
              Sonuçlar sentetik değerlendirme setine aittir.
            </p>
          </aside>
        </section>

        <section className="workbench" aria-labelledby="workbench-title">
          <div className="workbench-header">
            <div>
              <p className="eyebrow">Canlı analiz</p>
              <h2 id="workbench-title">Bir plan seçin veya JSON yapıştırın</h2>
            </div>
            <div className="mode-switch" role="tablist" aria-label="Plan kaynağı">
              <button
                type="button"
                role="tab"
                aria-selected={mode === "samples"}
                className={mode === "samples" ? "active" : ""}
                onClick={() => chooseMode("samples")}
              >
                Hazır senaryolar
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={mode === "json"}
                className={mode === "json" ? "active" : ""}
                onClick={() => chooseMode("json")}
              >
                EXPLAIN JSON
              </button>
            </div>
          </div>

          {mode === "samples" ? (
            <div className="fixture-grid">
              {DEMO_FIXTURES.map((fixture) => (
                <button
                  key={fixture.id}
                  type="button"
                  className={`fixture-card ${
                    fixture.id === fixtureId ? "selected" : ""
                  }`}
                  onClick={() => chooseFixture(fixture.id)}
                >
                  <span className="fixture-topline">{fixture.expectedLabel}</span>
                  <strong>{fixture.title}</strong>
                  <span>{fixture.description}</span>
                </button>
              ))}
            </div>
          ) : (
            <div className="json-input">
              <label htmlFor="explain-json">PostgreSQL EXPLAIN (FORMAT JSON)</label>
              <textarea
                id="explain-json"
                value={customJson}
                onChange={(event) => setCustomJson(event.target.value)}
                spellCheck={false}
                placeholder={'[\n  {\n    "Plan": {\n      "Node Type": "Seq Scan",\n      ...\n    }\n  }\n]'}
              />
              <div className="input-help">
                <span>En fazla 200 KB ve 250 plan düğümü</span>
                <button type="button" onClick={loadExampleJson}>
                  Örnek EXPLAIN yükle
                </button>
              </div>
            </div>
          )}

          <div className="analyze-row">
            <div>
              <button className="primary-button" type="button" onClick={analyze}>
                Planı analiz et
                <span aria-hidden="true">→</span>
              </button>
              <p className="analysis-status" role="status">{status}</p>
            </div>
            <p>Plan cihazınızda analiz edilir; AI yalnızca kısa kanıt özetini alır.</p>
          </div>

          {error && <div className="error-message" role="alert">{error}</div>}
          {result && (
            <div
              key={analysisRun}
              ref={resultRef}
              className="result-anchor"
              tabIndex={-1}
            >
              <ResultPanel
                result={result}
                aiExplanation={aiExplanation}
                aiCitation={aiCitation}
                aiError={aiError}
                aiLoading={aiLoading}
                onRequestAi={requestAiExplanation}
              />
            </div>
          )}
        </section>
      </div>

      <section id="v2-kanıt" className="v2-section">
        <div className="v2-heading">
          <div>
            <p className="eyebrow">V2 · Sentetik kanıt laboratuvarı</p>
            <h2>Önce pahalı sorguyu bul. Sonra değişimi ölç.</h2>
          </div>
          <p>
            Bu gösterim kayıtlı sentetik verilerle tamamen tarayıcıda çalışır.
            Veritabanına bağlanmaz, SQL çalıştırmaz ve plan kanıtı olmadan öneri
            üretmez.
          </p>
        </div>

        <div className="v2-layout">
          <nav className="workload-list" aria-label="Sentetik iş yükü sıralaması">
            {SYNTHETIC_WORKLOAD.map((query) => (
              <button
                key={query.id}
                type="button"
                className={query.id === workloadId ? "selected" : ""}
                onClick={() => setWorkloadId(query.id)}
              >
                <span className="workload-rank">#{query.rank}</span>
                <span>
                  <strong>{query.label}</strong>
                  <small>
                    {query.calls} çağrı · {query.totalTimeMs.toFixed(1)} ms toplam
                  </small>
                </span>
              </button>
            ))}
          </nav>

          <article className="regression-card" aria-live="polite">
            <div className="regression-topline">
              <div>
                <p className="eyebrow">Seçili iş yükü adayı</p>
                <h3>{selectedWorkload.label}</h3>
              </div>
              <span className="evidence-only">Öneri üretilmedi</span>
            </div>
            <pre>
              <code>{selectedWorkload.normalizedSql}</code>
            </pre>
            <p className="parameter-note">
              `$1` temsilî değer girilmeden yerel sürümde otomatik çalıştırılmaz.
            </p>

            <div className="comparison-metrics">
              <div>
                <span>Baseline</span>
                <strong>{selectedWorkload.baselineTimeMs.toFixed(2)} ms</strong>
              </div>
              <div>
                <span>Güncel</span>
                <strong>{selectedWorkload.currentTimeMs.toFixed(2)} ms</strong>
              </div>
              <div>
                <span>Ölçüm grubu</span>
                <strong>Warm cache</strong>
              </div>
            </div>

            {selectedRegressionReasons.length > 0 ? (
              <div className="regression-result regression-found">
                <strong>Kanıt eşiğini aşan regresyon bulundu.</strong>
                <ul>
                  {selectedRegressionReasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className="regression-result regression-clear">
                <strong>Tanımlı eşiklere göre regresyon bulunmadı.</strong>
                <p>Küçük süre farkları tek başına uyarı üretmez.</p>
              </div>
            )}
          </article>
        </div>
      </section>

      <section id="nasıl-çalışır" className="explain-section">
        <div className="section-heading">
          <p className="eyebrow">Güvenlik mimarisi</p>
          <h2>Önce kanıt, sonra öneri.</h2>
          <p>
            Public demo, tarayıcıdaki güvenilir çekirdeği isteğe bağlı bulut
            AI açıklamasıyla birleştirir. Gerçek veritabanı ve Foundry Local
            modeli tam yerel sürümde kalır.
          </p>
        </div>
        <div className="steps">
          <article>
            <span>01</span>
            <h3>Planı ayrıştır</h3>
            <p>JSON yapısı sınırlandırılır ve plan ağacı güvenli biçimde dolaşılır.</p>
          </article>
          <article>
            <span>02</span>
            <h3>Kuralları çalıştır</h3>
            <p>Dört performans sinyali yalnızca ölçülebilir plan alanlarıyla aranır.</p>
          </article>
          <article>
            <span>03</span>
            <h3>Kaynağı getir</h3>
            <p>Kategoriye uygun PostgreSQL bilgi parçası güvenilir listeden seçilir.</p>
          </article>
          <article>
            <span>04</span>
            <h3>AI çıktısını doğrula</h3>
            <p>Bilinmeyen kanıt, kaynak ve sayılar reddedilir; gerekirse çekirdek sonuç korunur.</p>
          </article>
        </div>
      </section>

      <footer>
        <div className="brand">
          <BrandMark />
          <span>QueryPilot</span>
        </div>
        <p>Güvenli, açıklanabilir ve offline-first PostgreSQL plan analizi.</p>
        <span>Public demo · İsteğe bağlı bulut AI</span>
      </footer>
    </main>
  );
}
