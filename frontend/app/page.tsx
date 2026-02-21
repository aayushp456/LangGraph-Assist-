"use client";

import { useEffect, useMemo, useState } from "react";

import BarChart, { type BarDatum } from "./components/BarChart";

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

type Ticket = {
  id: number;
  subject: string;
  status: string;
  sentiment: string;
};

type InsightsResponse = {
  route: { category?: string | null; confidence?: number | null };
  summary: string;
  sentiment: { label: string; score: number };
  top_matches: Array<{
    id?: string | null;
    score?: number | null;
    metadata?: Record<string, unknown>;
    text?: string;
  }>;
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

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(getBackendUrl() + path, { method: "GET" });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return (await res.json()) as T;
}

async function patchJSON<T>(path: string, body: unknown): Promise<T> {
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

export default function Page() {
const backendUrl = useMemo(() => getBackendUrl(), []);

const [tickets, setTickets] = useState<Ticket[]>([]);
const [selectedTicketId, setSelectedTicketId] = useState<number | null>(null);
const selectedTicket = useMemo(
    () => tickets.find((t) => t.id === selectedTicketId) ?? null,
    [tickets, selectedTicketId]
  );

  // Work queue: tickets that have been processed (insights run)
  const [queue, setQueue] = useState<Ticket[]>([]);

  // Triage stats
  const [triageStats, setTriageStats] = useState<Array<{
    category: string;
    count: number;
    active: number;
    urgent: number;
  }>>([]);

  const [insights, setInsights] = useState<InsightsResponse | null>(null);
  const [categoryCounts, setCategoryCounts] = useState<Record<string, number>>(
    {}
  );

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
    null | "summarize" | "route" | "index" | "retrieve" | "tickets" | "insights" | "update-status"
  >(null);
  const [error, setError] = useState<string>("");
  const [lastInsightsTime, setLastInsightsTime] = useState<number>(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setError("");
      setLoading("tickets");
      try {
        const t = await getJSON<Ticket[]>("/tickets");
        if (cancelled) return;
        setTickets(t);
        setSelectedTicketId((prev) => prev ?? (t[0]?.id ?? null));
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Fetch triage stats
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const stats = await getJSON<typeof triageStats>("/triage");
        if (cancelled) return;
        setTriageStats(stats);
      } catch (e) {
        if (cancelled) return;
        console.error("Failed to fetch triage stats:", e);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const chartData: BarDatum[] = useMemo(() => {
    const entries = Object.entries(categoryCounts);
    if (!entries.length) return [];
    return entries
      .map(([label, value]) => ({ label, value }))
      .sort((a, b) => b.value - a.value);
  }, [categoryCounts]);

  return (
    <div className="min-h-screen p-8">
      <div className="mx-auto max-w-5xl space-y-8">
        <header className="space-y-2">
          <h1 className="text-3xl font-semibold">Support Copilot</h1>
          <p className="text-sm opacity-80">
            Backend: <span className="font-mono">{backendUrl}</span>
          </p>
        </header>

        <section className="grid gap-6 md:grid-cols-3">
          {/* New Tickets */}
          <div className="rounded-lg border p-5 md:col-span-1">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold">New Tickets</h2>
                <p className="mt-1 text-sm opacity-80">GET /tickets</p>
              </div>
              <button
                className="rounded-md border px-3 py-2 text-sm disabled:opacity-60"
                disabled={loading !== null}
                onClick={async () => {
                  setError("");
                  setLoading("tickets");
                  try {
                    const t = await getJSON<Ticket[]>("/tickets");
                    setTickets(t);
                    setSelectedTicketId((prev) => prev ?? (t[0]?.id ?? null));
                  } catch (e) {
                    setError(e instanceof Error ? e.message : String(e));
                  } finally {
                    setLoading(null);
                  }
                }}
              >
                {loading === "tickets" ? "Loading..." : "Refresh"}
              </button>
            </div>

            <div className="mt-3 max-h-[420px] overflow-auto rounded-md border">
              {tickets
                .filter((t) => t.status === "new")
                .map((t) => (
                  <div
                    key={t.id}
                    className={`block w-full border-b p-3 text-left text-sm hover:bg-black/5 ${
                      t.id === selectedTicketId ? "bg-black/5" : ""
                    }`}
                    role="button"
                    tabIndex={0}
                    onClick={() => {
                      setSelectedTicketId(t.id);
                      setInsights(null);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setSelectedTicketId(t.id);
                        setInsights(null);
                      }
                    }}
                  >
                    <div className="font-semibold">#{t.id}</div>
                    <div className="opacity-80">{t.subject}</div>
                    <div className="mt-1 flex gap-2 text-xs opacity-70">
                      <span>Status: {t.status}</span>
                      <span>Sentiment: {t.sentiment}</span>
                    </div>
                  </div>
                ))}

              {!tickets.filter((t) => t.status === "new").length ? (
                <div className="p-3 text-sm opacity-70">No new tickets.</div>
              ) : null}
            </div>
          </div>

          <div className="rounded-lg border p-5 md:col-span-2">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold">Work Queue</h2>
                <p className="mt-1 text-sm opacity-80">Processed tickets</p>
              </div>
            </div>

            <div className="mt-3 max-h-[420px] overflow-auto rounded-md border">
              {queue.length ? (
                queue.map((t) => (
                  <div
                    key={t.id}
                    className="block w-full border-b p-3 text-left text-sm"
                  >
                    <div className="font-semibold">#{t.id}</div>
                    <div className="opacity-80">{t.subject}</div>
                    <div className="mt-1 flex gap-2 text-xs opacity-70">
                      <span>Status: {t.status}</span>
                      <span>Sentiment: {t.sentiment}</span>
                    </div>
                    <div className="mt-2 flex gap-1">
                      <select
                        className="rounded border border-gray-300 bg-transparent px-2 py-1 text-xs"
                        value={t.status}
                        disabled={loading !== null}
                        onChange={async (e) => {
                          const newStatus = e.target.value;
                          setError("");
                          setLoading("update-status");
                          try {
                            await patchJSON("/tickets/status", {
                              ticket_id: t.id,
                              status: newStatus,
                            });
                            setQueue((prev) =>
                              prev.map((qt) =>
                                qt.id === t.id ? { ...qt, status: newStatus } : qt
                              )
                            );
                          } catch (e) {
                            setError(e instanceof Error ? e.message : String(e));
                          } finally {
                            setLoading(null);
                          }
                        }}
                      >
                        <option value="new">New</option>
                        <option value="assigned">Assigned</option>
                        <option value="in_progress">In Progress</option>
                        <option value="resolved">Resolved</option>
                        <option value="escalated">Escalated</option>
                      </select>
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-3 text-sm opacity-70">
                  Run insights on new tickets to add them to the queue.
                </div>
              )}
            </div>
          </div>

          <div className="rounded-lg border p-5 md:col-span-2">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold">JSON Insights</h2>
                <p className="mt-1 text-sm opacity-80">POST /insights</p>
              </div>
              <button
                className="rounded-md bg-blue-600 px-3 py-2 text-sm text-white disabled:opacity-60"
                disabled={loading !== null || !selectedTicket}
                onClick={async () => {
                  if (!selectedTicket) return;
                  // Rate limit: only allow insights every 5 seconds
                  const now = Date.now();
                  if (now - lastInsightsTime < 5000) {
                    setError("Please wait a few seconds before running insights again.");
                    return;
                  }
                  setError("");
                  setLastInsightsTime(now);
                  setLoading("insights");
                  try {
                    const res = await postJSON<InsightsResponse>("/insights", {
                      text: selectedTicket.subject,
                      top_k: 5,
                      ticket_id: selectedTicket.id,
                    });
                    setInsights(res);
                    const cat = res.route?.category || "UNKNOWN";
                    setCategoryCounts((prev) => ({
                      ...prev,
                      [cat]: (prev[cat] ?? 0) + 1,
                    }));
                    // Move ticket to queue with status 'assigned'
                    const updatedTicket = { ...selectedTicket, status: "assigned" as const };
                    setQueue((prev) => [...prev, updatedTicket]);
                    // Remove from new tickets list
                    setTickets((prev) => prev.filter((t) => t.id !== selectedTicket.id));
                    setSelectedTicketId(null);
                    setInsights(null);
                  } catch (e) {
                    setError(e instanceof Error ? e.message : String(e));
                  } finally {
                    setLoading(null);
                  }
                }}
              >
                {loading === "insights" ? "Running..." : "Run Insights"}
              </button>
            </div>

            {selectedTicket ? (
              <div className="mt-3 rounded-md border p-3 text-sm">
                <div className="font-semibold">Selected ticket</div>
                <div className="mt-1 opacity-80">{selectedTicket.subject}</div>
              </div>
            ) : (
              <div className="mt-3 text-sm opacity-70">
                Select a ticket to run insights.
              </div>
            )}

            {insights ? (
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <div className="rounded-md border p-3">
                  <div className="text-sm font-semibold">Route</div>
                  <pre className="mt-2 overflow-auto rounded-md bg-black/5 p-2 text-xs">
                    {JSON.stringify(insights.route, null, 2)}
                  </pre>
                </div>

                <div className="rounded-md border p-3">
                  <div className="text-sm font-semibold">Sentiment</div>
                  <pre className="mt-2 overflow-auto rounded-md bg-black/5 p-2 text-xs">
                    {JSON.stringify(insights.sentiment, null, 2)}
                  </pre>
                </div>

                <div className="rounded-md border p-3 md:col-span-2">
                  <div className="text-sm font-semibold">Summary</div>
                  <pre className="mt-2 whitespace-pre-wrap rounded-md bg-black/5 p-2 text-xs">
                    {insights.summary}
                  </pre>
                </div>

                <div className="rounded-md border p-3 md:col-span-2">
                  <div className="text-sm font-semibold">Top Matches</div>
                  <pre className="mt-2 overflow-auto rounded-md bg-black/5 p-2 text-xs">
                    {JSON.stringify(insights.top_matches, null, 2)}
                  </pre>
                </div>
              </div>
            ) : null}
          </div>
        </section>

        <section className="rounded-lg border p-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">Triage Overview</h2>
              <p className="mt-1 text-sm opacity-80">
                Tickets by routing category (live from DB)
              </p>
            </div>
          </div>
          <div className="mt-3 space-y-2">
            {triageStats.length ? (
              triageStats.map((stat) => (
                <div
                  key={stat.category}
                  className={`rounded-md border p-3 ${
                    stat.urgent > 0 ? "border-red-300 bg-red-50/30" : ""
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="font-semibold text-sm">{stat.category}</div>
                    <div className="text-sm opacity-80">
                      Total: {stat.count} | Active: {stat.active}
                      {stat.urgent > 0 && (
                        <span className="ml-2 text-red-600 font-semibold">
                          {stat.urgent} urgent
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-sm opacity-70">
                No tickets processed yet.
              </div>
            )}
          </div>
        </section>

        <section className="rounded-lg border p-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">Category Counts (This Session)</h2>
              <p className="mt-1 text-sm opacity-80">
                Updates when you click “Run Insights”
              </p>
            </div>
          </div>
          <div className="mt-3">
            {chartData.length ? (
              <BarChart data={chartData} height={260} />
            ) : (
              <div className="text-sm opacity-70">
                Run insights on a few tickets to populate the chart.
              </div>
            )}
          </div>
        </section>

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
