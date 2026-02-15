"use client";

import { useMemo, useState } from "react";

type RouteResponse = {
  category: string;
  confidence: number;
  top_matches?: Array<{
    id?: string | null;
    score?: number | null;
    metadata?: Record<string, unknown>;
    text?: string;
  }>;
};

type RetrieveResponse = {
  results: Array<{
    id?: string | null;
    text: string;
    metadata?: Record<string, unknown>;
    score: number;
  }>;
};

type IndexResponse = {
  indexed: number;
};

type SummarizeResponse = {
  summary: string;
};

function getBackendUrl() {
  return (
    process.env.NEXT_PUBLIC_BACKEND_URL?.trim() || "http://127.0.0.1:8000"
  );
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${getBackendUrl()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }

  return (await res.json()) as T;
}

export default function Home() {
  const backendUrl = useMemo(() => getBackendUrl(), []);

  const [summarizeText, setSummarizeText] = useState(
    "I have been trying to reset my password but the link in the email is not working."
  );
  const [summary, setSummary] = useState<string>("");

  const [routeMessage, setRouteMessage] = useState("I forgot my password");
  const [routeResult, setRouteResult] = useState<RouteResponse | null>(null);

  const [indexJson, setIndexJson] = useState(
    JSON.stringify(
      {
        items: [
          {
            text: "How to reset password",
            metadata: { type: "faq", category: "account" },
          },
          {
            text: "Account locked after multiple failed attempts",
            metadata: { type: "support", priority: "high" },
          },
        ],
      },
      null,
      2
    )
  );
  const [indexedCount, setIndexedCount] = useState<number | null>(null);

  const [retrieveQuery, setRetrieveQuery] = useState("I forgot my password");
  const [retrieveTopK, setRetrieveTopK] = useState(2);
  const [retrieveResult, setRetrieveResult] = useState<RetrieveResponse | null>(
    null
  );

  const [loading, setLoading] = useState<
    null | "summarize" | "route" | "index" | "retrieve"
  >(null);
  const [error, setError] = useState<string>("");

  return (
    <div className="min-h-screen p-8">
      <div className="mx-auto max-w-5xl space-y-8">
        <header className="space-y-2">
          <h1 className="text-3xl font-semibold">Support Copilot</h1>
          <p className="text-sm opacity-80">
            Backend: <span className="font-mono">{backendUrl}</span>
          </p>
        </header>

        {error ? (
          <div className="rounded-md border border-red-500/40 bg-red-500/10 p-4 text-sm">
            <div className="font-semibold">Request error</div>
            <div className="mt-1 whitespace-pre-wrap font-mono">{error}</div>
          </div>
        ) : null}

        <section className="grid gap-6 md:grid-cols-2">
          <div className="rounded-lg border p-5">
            <h2 className="text-lg font-semibold">Summarize</h2>
            <p className="mt-1 text-sm opacity-80">POST /summarize</p>
            <textarea
              className="mt-3 w-full rounded-md border bg-transparent p-3 text-sm"
              rows={6}
              value={summarizeText}
              onChange={(e) => setSummarizeText(e.target.value)}
            />
            <div className="mt-3 flex items-center gap-2">
              <button
                className="rounded-md bg-blue-600 px-3 py-2 text-sm text-white disabled:opacity-60"
                disabled={loading !== null}
                onClick={async () => {
                  setError("");
                  setLoading("summarize");
                  try {
                    const res = await postJSON<SummarizeResponse>("/summarize", {
                      text: summarizeText,
                    });
                    setSummary(res.summary);
                  } catch (e) {
                    setError(e instanceof Error ? e.message : String(e));
                  } finally {
                    setLoading(null);
                  }
                }}
              >
                {loading === "summarize" ? "Summarizing..." : "Summarize"}
              </button>
              <button
                className="rounded-md border px-3 py-2 text-sm disabled:opacity-60"
                disabled={loading !== null}
                onClick={() => setSummary("")}
              >
                Clear
              </button>
            </div>

            {summary ? (
              <pre className="mt-4 whitespace-pre-wrap rounded-md border bg-black/5 p-3 text-sm">
                {summary}
              </pre>
            ) : null}
          </div>

          <div className="rounded-lg border p-5">
            <h2 className="text-lg font-semibold">Route</h2>
            <p className="mt-1 text-sm opacity-80">POST /route</p>
            <textarea
              className="mt-3 w-full rounded-md border bg-transparent p-3 text-sm"
              rows={6}
              value={routeMessage}
              onChange={(e) => setRouteMessage(e.target.value)}
            />
            <div className="mt-3 flex items-center gap-2">
              <button
                className="rounded-md bg-blue-600 px-3 py-2 text-sm text-white disabled:opacity-60"
                disabled={loading !== null}
                onClick={async () => {
                  setError("");
                  setLoading("route");
                  try {
                    const res = await postJSON<RouteResponse>("/route", {
                      message: routeMessage,
                    });
                    setRouteResult(res);
                  } catch (e) {
                    setError(e instanceof Error ? e.message : String(e));
                  } finally {
                    setLoading(null);
                  }
                }}
              >
                {loading === "route" ? "Routing..." : "Route"}
              </button>
              <button
                className="rounded-md border px-3 py-2 text-sm disabled:opacity-60"
                disabled={loading !== null}
                onClick={() => setRouteResult(null)}
              >
                Clear
              </button>
            </div>

            {routeResult ? (
              <pre className="mt-4 overflow-auto rounded-md border bg-black/5 p-3 text-sm">
                {JSON.stringify(routeResult, null, 2)}
              </pre>
            ) : null}
          </div>
        </section>

        <section className="grid gap-6 md:grid-cols-2">
          <div className="rounded-lg border p-5">
            <h2 className="text-lg font-semibold">Index (Knowledge Base)</h2>
            <p className="mt-1 text-sm opacity-80">POST /index</p>
            <textarea
              className="mt-3 w-full rounded-md border bg-transparent p-3 font-mono text-xs"
              rows={10}
              value={indexJson}
              onChange={(e) => setIndexJson(e.target.value)}
            />
            <div className="mt-3 flex items-center gap-2">
              <button
                className="rounded-md bg-blue-600 px-3 py-2 text-sm text-white disabled:opacity-60"
                disabled={loading !== null}
                onClick={async () => {
                  setError("");
                  setLoading("index");
                  try {
                    const parsed = JSON.parse(indexJson);
                    const res = await postJSON<IndexResponse>("/index", parsed);
                    setIndexedCount(res.indexed);
                  } catch (e) {
                    setError(e instanceof Error ? e.message : String(e));
                  } finally {
                    setLoading(null);
                  }
                }}
              >
                {loading === "index" ? "Indexing..." : "Index"}
              </button>
              <button
                className="rounded-md border px-3 py-2 text-sm disabled:opacity-60"
                disabled={loading !== null}
                onClick={() => setIndexedCount(null)}
              >
                Clear
              </button>
              {indexedCount !== null ? (
                <span className="text-sm opacity-80">Indexed: {indexedCount}</span>
              ) : null}
            </div>
          </div>

          <div className="rounded-lg border p-5">
            <h2 className="text-lg font-semibold">Retrieve (Semantic Search)</h2>
            <p className="mt-1 text-sm opacity-80">POST /retrieve</p>
            <label className="mt-3 block text-sm">Query</label>
            <input
              className="mt-1 w-full rounded-md border bg-transparent p-2 text-sm"
              value={retrieveQuery}
              onChange={(e) => setRetrieveQuery(e.target.value)}
            />

            <label className="mt-3 block text-sm">Top K</label>
            <input
              type="number"
              min={1}
              max={20}
              className="mt-1 w-full rounded-md border bg-transparent p-2 text-sm"
              value={retrieveTopK}
              onChange={(e) => setRetrieveTopK(Number(e.target.value))}
            />

            <div className="mt-3 flex items-center gap-2">
              <button
                className="rounded-md bg-blue-600 px-3 py-2 text-sm text-white disabled:opacity-60"
                disabled={loading !== null}
                onClick={async () => {
                  setError("");
                  setLoading("retrieve");
                  try {
                    const res = await postJSON<RetrieveResponse>("/retrieve", {
                      query: retrieveQuery,
                      top_k: retrieveTopK,
                    });
                    setRetrieveResult(res);
                  } catch (e) {
                    setError(e instanceof Error ? e.message : String(e));
                  } finally {
                    setLoading(null);
                  }
                }}
              >
                {loading === "retrieve" ? "Retrieving..." : "Retrieve"}
              </button>
              <button
                className="rounded-md border px-3 py-2 text-sm disabled:opacity-60"
                disabled={loading !== null}
                onClick={() => setRetrieveResult(null)}
              >
                Clear
              </button>
            </div>

            {retrieveResult ? (
              <pre className="mt-4 overflow-auto rounded-md border bg-black/5 p-3 text-sm">
                {JSON.stringify(retrieveResult, null, 2)}
              </pre>
            ) : null}
          </div>
        </section>
      </div>
    </div>
  );
}