/** Cloudflare Worker entry point for the vinext-starter template. */
import { handleImageOptimization, DEFAULT_DEVICE_SIZES, DEFAULT_IMAGE_SIZES } from "vinext/server/image-optimization";
import handler from "vinext/server/app-router-entry";
import {
  buildGeminiRequest,
  extractGeminiText,
  parsePublicAiRequest,
  publicCitationFor,
  validateModelExplanation,
} from "../lib/public-ai";

interface Env {
  ASSETS: Fetcher;
  GEMINI_API_KEY?: string;
  GEMINI_MODEL?: string;
  IMAGES: {
    input(stream: ReadableStream): {
      transform(options: Record<string, unknown>): {
        output(options: { format: string; quality: number }): Promise<{ response(): Response }>;
      };
    };
  };
}

interface ExecutionContext {
  waitUntil(promise: Promise<unknown>): void;
  passThroughOnException(): void;
}

const DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite";
const AI_TIMEOUT_MS = 15_000;
const RATE_LIMIT_WINDOW_MS = 10 * 60 * 1_000;
const RATE_LIMIT_MAX_REQUESTS = 5;
const RATE_LIMIT_MAX_CLIENTS = 500;
const rateLimits = new Map<string, { count: number; resetAt: number }>();

const jsonResponse = (
  body: object,
  status = 200,
  extraHeaders?: HeadersInit,
): Response =>
  Response.json(body, {
    status,
    headers: {
      "Cache-Control": "no-store",
      "Content-Security-Policy": "default-src 'none'",
      "Cross-Origin-Resource-Policy": "same-origin",
      "Referrer-Policy": "no-referrer",
      "X-Content-Type-Options": "nosniff",
      ...extraHeaders,
    },
  });

function rateLimitRetryAfter(request: Request): number | null {
  const now = Date.now();
  const clientId =
    request.headers.get("CF-Connecting-IP")?.trim() || "local-client";
  const current = rateLimits.get(clientId);
  if (!current || current.resetAt <= now) {
    if (rateLimits.size >= RATE_LIMIT_MAX_CLIENTS) {
      for (const [key, value] of rateLimits) {
        if (value.resetAt <= now) rateLimits.delete(key);
      }
      if (rateLimits.size >= RATE_LIMIT_MAX_CLIENTS) {
        rateLimits.delete(rateLimits.keys().next().value as string);
      }
    }
    rateLimits.set(clientId, {
      count: 1,
      resetAt: now + RATE_LIMIT_WINDOW_MS,
    });
    return null;
  }
  if (current.count >= RATE_LIMIT_MAX_REQUESTS) {
    return Math.max(1, Math.ceil((current.resetAt - now) / 1_000));
  }
  current.count += 1;
  return null;
}

function withPageSecurityHeaders(response: Response): Response {
  const headers = new Headers(response.headers);
  headers.set(
    "Content-Security-Policy",
    "default-src 'self'; base-uri 'none'; connect-src 'self'; font-src 'self'; form-action 'none'; frame-ancestors 'none'; img-src 'self' data:; object-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; upgrade-insecure-requests",
  );
  headers.set("Cross-Origin-Opener-Policy", "same-origin");
  headers.set("Cross-Origin-Resource-Policy", "same-origin");
  headers.set(
    "Permissions-Policy",
    "camera=(), geolocation=(), microphone=(), payment=(), usb=()",
  );
  headers.set("Referrer-Policy", "no-referrer");
  headers.set("Strict-Transport-Security", "max-age=31536000");
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("X-Frame-Options", "DENY");
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

async function handleAiExplanation(
  request: Request,
  env: Env,
): Promise<Response> {
  if (request.method !== "POST") {
    return jsonResponse({ error: "Yalnızca POST isteği kabul edilir." }, 405);
  }

  const requestUrl = new URL(request.url);
  const origin = request.headers.get("Origin");
  if (origin && origin !== requestUrl.origin) {
    return jsonResponse({ error: "Çapraz kaynak isteği reddedildi." }, 403);
  }
  if (!request.headers.get("content-type")?.toLowerCase().startsWith("application/json")) {
    return jsonResponse({ error: "İstek application/json olmalıdır." }, 415);
  }
  if (!env.GEMINI_API_KEY) {
    return jsonResponse(
      {
        error:
          "Public AI henüz etkinleştirilmedi. Deterministik sonuç kullanılmaya devam ediyor.",
        code: "AI_NOT_CONFIGURED",
      },
      503,
    );
  }

  let groundingRequest: ReturnType<typeof parsePublicAiRequest>;
  try {
    groundingRequest = parsePublicAiRequest(await request.text());
  } catch (error) {
    return jsonResponse(
      { error: error instanceof Error ? error.message : "Geçersiz AI isteği." },
      400,
    );
  }

  const retryAfter = rateLimitRetryAfter(request);
  if (retryAfter !== null) {
    return jsonResponse(
      {
        error:
          "AI açıklama sınırına ulaşıldı. Deterministik sonuç kullanılmaya devam edebilir.",
        code: "AI_RATE_LIMITED",
      },
      429,
      { "Retry-After": String(retryAfter) },
    );
  }

  const configuredModel = env.GEMINI_MODEL?.trim();
  const model =
    configuredModel === DEFAULT_GEMINI_MODEL
      ? configuredModel
      : DEFAULT_GEMINI_MODEL;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), AI_TIMEOUT_MS);
  let providerResponse: Response;
  try {
    providerResponse = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-goog-api-key": env.GEMINI_API_KEY,
        },
        body: JSON.stringify(buildGeminiRequest(groundingRequest)),
        redirect: "error",
        signal: controller.signal,
      },
    );
  } catch {
    clearTimeout(timeout);
    return jsonResponse(
      {
        error:
          "AI açıklaması zamanında alınamadı. Deterministik sonuç geçerliliğini koruyor.",
        code: "AI_PROVIDER_UNAVAILABLE",
      },
      503,
    );
  }
  clearTimeout(timeout);

  if (!providerResponse.ok) {
    return jsonResponse(
      {
        error:
          providerResponse.status === 429
            ? "Ücretsiz AI kotası şu anda dolu. Deterministik sonuç kullanılabilir."
            : "AI sağlayıcısı şu anda yanıt veremiyor. Deterministik sonuç kullanılabilir.",
        code: providerResponse.status === 429 ? "AI_QUOTA_EXCEEDED" : "AI_PROVIDER_ERROR",
      },
      providerResponse.status === 429 ? 429 : 503,
    );
  }

  try {
    const providerPayload: unknown = await providerResponse.json();
    const explanation = validateModelExplanation(
      extractGeminiText(providerPayload),
      groundingRequest,
      model,
    );
    return jsonResponse({
      explanation,
      citation: publicCitationFor(groundingRequest.category),
    });
  } catch {
    return jsonResponse(
      {
        error:
          "AI çıktısı kanıt doğrulamasını geçemedi. Deterministik sonuç korundu.",
        code: "AI_OUTPUT_REJECTED",
      },
      422,
    );
  }
}

// Image security config. SVG sources with .svg extension auto-skip the
// optimization endpoint on the client side (served directly, no proxy).
// To route SVGs through the optimizer (with security headers), set
// dangerouslyAllowSVG: true in next.config.js and uncomment below:
// const imageConfig: ImageConfig = { dangerouslyAllowSVG: true };

const worker = {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/_vinext/image") {
      const allowedWidths = [...DEFAULT_DEVICE_SIZES, ...DEFAULT_IMAGE_SIZES];
      const response = await handleImageOptimization(request, {
        fetchAsset: (path) => env.ASSETS.fetch(new Request(new URL(path, request.url))),
        transformImage: async (body, { width, format, quality }) => {
          const result = await env.IMAGES.input(body).transform(width > 0 ? { width } : {}).output({ format, quality });
          return result.response();
        },
      }, allowedWidths);
      return withPageSecurityHeaders(response);
    }

    if (url.pathname === "/api/ai-explain") {
      return handleAiExplanation(request, env);
    }

    return withPageSecurityHeaders(await handler.fetch(request, env, ctx));
  },
};

export default worker;
