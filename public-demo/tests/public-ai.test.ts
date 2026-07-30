import assert from "node:assert/strict";
import test from "node:test";
import { analyzeExplainJson } from "../lib/analyzer";
import { DEMO_FIXTURES } from "../lib/fixtures";
import {
  buildGeminiRequest,
  parsePublicAiRequest,
  publicAiRequestFromAnalysis,
  validateModelExplanation,
} from "../lib/public-ai";

function missingIndexRequest() {
  const fixture = DEMO_FIXTURES.find((item) => item.id === "missing-index");
  assert.ok(fixture);
  const request = publicAiRequestFromAnalysis(
    analyzeExplainJson(fixture.json),
  );
  assert.ok(request);
  return request;
}

test("public AI is unavailable when deterministic evidence is insufficient", () => {
  const fixture = DEMO_FIXTURES.find((item) => item.id === "healthy");
  assert.ok(fixture);
  assert.equal(
    publicAiRequestFromAnalysis(analyzeExplainJson(fixture.json)),
    null,
  );
});

test("public AI request rejects unknown or no-answer categories", () => {
  assert.throws(
    () =>
      parsePublicAiRequest(
        JSON.stringify({
          category: "no_clear_issue",
          severity: "low",
          summary: "Yeterli uzunlukta bir deterministik özet.",
          evidence: ["Plan kanıtı mevcut değil."],
        }),
      ),
    /kanıtlı bir kategori/,
  );
  assert.throws(
    () =>
      parsePublicAiRequest(
        JSON.stringify({
          category: "invented_issue",
          severity: "high",
          summary: "Yeterli uzunlukta bir deterministik özet.",
          evidence: ["İcat edilmiş plan kanıtı."],
        }),
      ),
    /kanıtlı bir kategori/,
  );
});

test("Gemini prompt contains application-owned evidence and citation IDs", () => {
  const prompt = JSON.stringify(buildGeminiRequest(missingIndexRequest()));
  assert.match(prompt, /evidence-1/);
  assert.match(prompt, /pg-indexes-01:selective-predicates:public/);
  assert.doesNotMatch(prompt, /EXPLAIN \(FORMAT JSON\)/);
});

test("valid grounded model output is accepted", () => {
  const request = missingIndexRequest();
  const output = JSON.stringify({
    summary:
      "Sıralı tarama, seçici filtre sırasında çok sayıda satırı eleyerek gereksiz çalışma oluşturuyor.",
    recommendation:
      "Filtreyi destekleyen indeks adayını test ortamında ölçün ve yazma maliyetini yeni planla birlikte karşılaştırın.",
    evidence_ids: ["evidence-1", "evidence-2"],
    citation_ids: ["pg-indexes-01:selective-predicates:public"],
  });

  const explanation = validateModelExplanation(
    output,
    request,
    "gemini-test",
  );

  assert.equal(explanation.provider, "gemini");
  assert.equal(explanation.model, "gemini-test");
});

test("unknown citations and invented numbers are rejected", () => {
  const request = missingIndexRequest();
  const base = {
    summary:
      "Sıralı tarama, seçici filtre sırasında çok sayıda satırı eleyerek gereksiz çalışma oluşturuyor.",
    recommendation:
      "Filtreyi destekleyen indeks adayını test ortamında ölçün ve yeni planla birlikte karşılaştırın.",
    evidence_ids: ["evidence-1"],
    citation_ids: ["invented-source"],
  };

  assert.throws(
    () =>
      validateModelExplanation(
        JSON.stringify(base),
        request,
        "gemini-test",
      ),
    /bilinmeyen bir kaynak/,
  );

  assert.throws(
    () =>
      validateModelExplanation(
        JSON.stringify({
          ...base,
          summary:
            "Bu plan kesin olarak 999 kat hızlanacaktır ve doğrudan uygulanmalıdır.",
          citation_ids: ["pg-indexes-01:selective-predicates:public"],
        }),
        request,
        "gemini-test",
      ),
    /olmayan sayısal değer/,
  );
});
