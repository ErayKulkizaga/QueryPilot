import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import test from "node:test";

async function loadWorker() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker;
}

async function render() {
  const worker = await loadWorker();
  return worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the QueryPilot public demo shell", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  assert.equal(response.headers.get("x-frame-options"), "DENY");
  assert.equal(response.headers.get("referrer-policy"), "no-referrer");
  assert.match(
    response.headers.get("content-security-policy") ?? "",
    /frame-ancestors 'none'/,
  );

  const html = await response.text();
  assert.match(html, /<html[^>]*lang="tr"/i);
  assert.match(html, /<title>QueryPilot Public Demo · QueryPilot<\/title>/i);
  assert.match(html, /Yavaş sorgunun/);
  assert.match(html, /Plan analizi tarayıcıda/);
  assert.match(html, /AI açıklaması isteğe bağlı/);
  assert.match(html, /Hazır senaryolar/);
  assert.match(html, /EXPLAIN JSON/);
  assert.match(html, /Bir senaryo seçin ve analizi başlatın/);
  assert.match(html, /V2 · Sentetik kanıt laboratuvarı/);
  assert.match(html, /Öneri üretilmedi/);
  assert.match(html, /Warm cache/);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton/i);
});

test("client bundle contains no server credential surface", async () => {
  const clientDirectory = new URL("../dist/client/", import.meta.url);
  const paths = await readdir(clientDirectory, { recursive: true });
  const scripts = paths.filter((path) => path.endsWith(".js"));
  const bundle = (
    await Promise.all(
      scripts.map((path) => readFile(new URL(path, clientDirectory), "utf8")),
    )
  ).join("\n");

  assert.doesNotMatch(
    bundle,
    /GEMINI_API_KEY|generativelanguage\.googleapis\.com|AIza[0-9A-Za-z_-]{20,}/,
  );
});

const groundedRequest = {
  category: "potential_missing_index",
  severity: "high",
  summary:
    "customers üzerinde yapılan sıralı tarama, incelenen satırların çoğunu eledi.",
  evidence: [
    "Düğüm: Seq Scan on customers",
    "Filtreyle elenen satır: 19.999",
    "Filtre seçiciliği: %0,01",
  ],
};

test("public AI endpoint fails closed when its server credential is absent", async () => {
  const worker = await loadWorker();
  const response = await worker.fetch(
    new Request("http://localhost/api/ai-explain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(groundedRequest),
    }),
    {},
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );

  assert.equal(response.status, 503);
  assert.equal((await response.json()).code, "AI_NOT_CONFIGURED");
});

test("public AI endpoint accepts only a grounded provider response", async () => {
  const worker = await loadWorker();
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () =>
    Response.json({
      candidates: [
        {
          content: {
            parts: [
              {
                text: JSON.stringify({
                  summary:
                    "Sıralı tarama, seçici filtre sırasında gereksiz satır taraması oluşturuyor.",
                  recommendation:
                    "Filtreyi destekleyen indeks adayını test ortamında ölçün ve yazma maliyetini yeni planla karşılaştırın.",
                  evidence_ids: ["evidence-1", "evidence-2"],
                  citation_ids: [
                    "pg-indexes-01:selective-predicates:public",
                  ],
                }),
              },
            ],
          },
        },
      ],
    });

  try {
    const response = await worker.fetch(
      new Request("http://localhost/api/ai-explain", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Origin: "http://localhost",
        },
        body: JSON.stringify(groundedRequest),
      }),
      {
        GEMINI_API_KEY: "test-only-key",
        GEMINI_MODEL: "gemini-test",
      },
      {
        waitUntil() {},
        passThroughOnException() {},
      },
    );

    assert.equal(response.status, 200);
    const payload = await response.json();
    assert.equal(payload.explanation.model, "gemini-3.1-flash-lite");
    assert.equal(payload.citation.documentId, "pg-indexes-01");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("public AI endpoint limits repeated provider calls per client", async () => {
  const worker = await loadWorker();
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () =>
    Response.json({
      candidates: [
        {
          content: {
            parts: [
              {
                text: JSON.stringify({
                  summary:
                    "Sıralı tarama, seçici filtre sırasında gereksiz satır taraması oluşturuyor.",
                  recommendation:
                    "Filtreyi destekleyen indeks adayını test ortamında ölçün ve yazma maliyetini yeni planla karşılaştırın.",
                  evidence_ids: ["evidence-1", "evidence-2"],
                  citation_ids: [
                    "pg-indexes-01:selective-predicates:public",
                  ],
                }),
              },
            ],
          },
        },
      ],
    });

  try {
    const responses = [];
    for (let index = 0; index < 6; index += 1) {
      responses.push(
        await worker.fetch(
          new Request("http://localhost/api/ai-explain", {
            method: "POST",
            headers: {
              "CF-Connecting-IP": "203.0.113.10",
              "Content-Type": "application/json",
              Origin: "http://localhost",
            },
            body: JSON.stringify(groundedRequest),
          }),
          {
            GEMINI_API_KEY: "test-only-key",
            GEMINI_MODEL: "gemini-test",
          },
          {
            waitUntil() {},
            passThroughOnException() {},
          },
        ),
      );
    }

    assert.deepEqual(
      responses.map((response) => response.status),
      [200, 200, 200, 200, 200, 429],
    );
    assert.ok(Number(responses[5].headers.get("retry-after")) > 0);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
