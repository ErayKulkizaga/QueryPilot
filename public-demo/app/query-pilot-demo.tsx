"use client";

import { useMemo, useState } from "react";
import {
  analyzeExplainJson,
  type AnalysisResult,
  type Severity,
} from "../lib/analyzer";
import { DEMO_FIXTURES } from "../lib/fixtures";

type InputMode = "samples" | "json";

const severityClass: Record<Severity, string> = {
  low: "severity-low",
  medium: "severity-medium",
  high: "severity-high",
};

function CheckIcon() {
  return <span aria-hidden="true">✓</span>;
}

function ResultPanel({ result }: { result: AnalysisResult }) {
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
            <span className="source-dot" aria-hidden="true" />
            {result.citation.title} · {result.citation.documentId}
            <span aria-hidden="true">↗</span>
          </a>
        )}
      </div>
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
  const [result, setResult] = useState<AnalysisResult | null>(() =>
    analyzeExplainJson(DEMO_FIXTURES[0].json),
  );
  const [error, setError] = useState("");

  const inputJson = mode === "samples" ? activeFixture.json : customJson;

  function analyze() {
    try {
      setResult(analyzeExplainJson(inputJson));
      setError("");
    } catch (caught) {
      setResult(null);
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
      setResult(analyzeExplainJson(fixture.json));
      setError("");
    }
  }

  return (
    <main>
      <header className="site-header">
        <a className="brand" href="#top" aria-label="QueryPilot ana sayfa">
          <span className="brand-mark" aria-hidden="true">Q</span>
          <span>QueryPilot</span>
        </a>
        <div className="header-actions">
          <span className="privacy-pill">
            <span className="pulse" aria-hidden="true" />
            Veriniz tarayıcıdan çıkmaz
          </span>
          <a className="text-link" href="#nasıl-çalışır">
            Nasıl çalışır?
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
              Güçlü plan kanıtı yoksa optimizasyon önerisi üretmez.
            </p>
            <div className="hero-points">
              <span><CheckIcon /> LLM ve bulut çağrısı yok</span>
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
                onClick={() => setMode("samples")}
              >
                Hazır senaryolar
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={mode === "json"}
                className={mode === "json" ? "active" : ""}
                onClick={() => setMode("json")}
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
                  <span className="fixture-topline">
                    <span className="fixture-indicator" aria-hidden="true" />
                    {fixture.expectedLabel}
                  </span>
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
                <span>İçerik cihazınızdan gönderilmez</span>
              </div>
            </div>
          )}

          <div className="analyze-row">
            <button className="primary-button" type="button" onClick={analyze}>
              Planı analiz et
              <span aria-hidden="true">→</span>
            </button>
            <p>
              Analiz, açık ve denetlenebilir eşiklerle cihazınızda tamamlanır.
            </p>
          </div>

          {error && <div className="error-message" role="alert">{error}</div>}
          {result && <ResultPanel result={result} />}
        </section>
      </div>

      <section id="nasıl-çalışır" className="explain-section">
        <div className="section-heading">
          <p className="eyebrow">Güvenlik mimarisi</p>
          <h2>Önce kanıt, sonra öneri.</h2>
          <p>
            Public demo, QueryPilot’ın güvenilir çekirdeğini gösterir. Gerçek
            veritabanı bağlantısı ve yerel model tam masaüstü sürümünde kalır.
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
            <h3>Kanıtı bağla</h3>
            <p>Öneri ve resmi PostgreSQL kaynağı kategori allowlist’inden gelir.</p>
          </article>
          <article>
            <span>04</span>
            <h3>Gerekirse sus</h3>
            <p>Güçlü sinyal bulunmazsa şema değişikliği önerilmez.</p>
          </article>
        </div>
      </section>

      <footer>
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">Q</span>
          <span>QueryPilot</span>
        </div>
        <p>Güvenli, açıklanabilir ve offline-first PostgreSQL plan analizi.</p>
        <span>Public demo · Sentetik veriler</span>
      </footer>
    </main>
  );
}
