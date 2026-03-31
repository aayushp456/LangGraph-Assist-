"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import {
  Database,
  Upload,
  Search,
  Trash2,
  FileText,
  Plus,
  ArrowLeft,
  CheckCircle,
  XCircle,
  Loader2,
  BookOpen,
  Layers,
  Zap,
} from "lucide-react";
import { useWebSocket } from "../../hooks/useWebSocket";
import DebugPanel, { useDebugLog } from "../../components/DebugPanel";
import { fetchWithTimeout, getApiUrl } from "@/lib/runtime-config";

const CATEGORIES = ["BUG", "PERFORMANCE", "API_ISSUE", "SECURITY", "INFRASTRUCTURE", "FEATURE_REQUEST", "GENERAL_INQUIRY"];

interface KBStats {
  total_articles: number;
  categories: Record<string, number>;
  vector_store: {
    initialized: boolean;
    provider?: string;
    total_vectors?: number;
    dimension?: number;
    index_fullness?: number;
    error?: string;
  };
}

interface SearchResult {
  id: string;
  score: number;
  text: string;
  metadata: Record<string, unknown>;
}

interface KBArticle {
  article_id: string;
  title: string;
  content: string;
  category: string;
  product?: string;
  tags?: string[];
  is_active?: boolean;
  created_at: string;
}

export default function KnowledgeBasePage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();

  // Auth guard — admin only
  useEffect(() => {
    if (authLoading) return;
    if (!user || user.role !== "admin") {
      router.push("/login");
    }
  }, [user, authLoading, router]);

  // Stats
  const [stats, setStats] = useState<KBStats | null>(null);

  // Add document form
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [category, setCategory] = useState("GENERAL");
  const [addLoading, setAddLoading] = useState(false);
  const [addResult, setAddResult] = useState<{ success: boolean; message: string } | null>(null);

  // File upload
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadResult, setUploadResult] = useState<{ success: boolean; message: string } | null>(null);

  // Search
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchDone, setSearchDone] = useState(false);

  // Articles list
  const [articles, setArticles] = useState<KBArticle[]>([]);
  const [articlesLoading, setArticlesLoading] = useState(false);

  // Clear
  const [clearLoading, setClearLoading] = useState(false);

  // Active tab
  const [activeTab, setActiveTab] = useState<"add" | "upload" | "search" | "browse">("add");

  // Debug logging
  const { logs, addLog } = useDebugLog();

  // Last-known-good stats ref to prevent false "Offline" on fetch failure
  const lastGoodStats = useRef<KBStats | null>(null);
  const statsFetchInFlight = useRef(false);
  const articlesFetchInFlight = useRef(false);
  const hasRefreshedOnWsConnect = useRef(false);

  // WebSocket connection
  const { status: wsStatus } = useWebSocket({
    subscriptions: ["kb:updated"],
    onEvent: (event) => {
      if (event.type === "subscribed") {
        return;
      }

      addLog("info", "WS", `Event: ${event.type}`);
      if (event.type === "kb:updated") {
        fetchStats();
        fetchArticles();
      }
    },
  });

  // Initial load
  useEffect(() => {
    addLog("info", "KB", "Initial data load");
    fetchStats();
    fetchArticles();
  }, []);

  useEffect(() => {
    if (wsStatus !== "connected" || hasRefreshedOnWsConnect.current) {
      return;
    }

    hasRefreshedOnWsConnect.current = true;
    addLog("success", "WS", "Connected; refreshing knowledge base data");
    fetchStats();
    fetchArticles();
  }, [wsStatus]);

  useEffect(() => {
    if (wsStatus === "connected") {
      return;
    }

    const interval = setInterval(() => {
      addLog("info", "KB", "Fallback poll (60s)");
      fetchStats();
      fetchArticles();
    }, 60000);

    return () => clearInterval(interval);
  }, [wsStatus]);

  const fetchStats = async () => {
    if (statsFetchInFlight.current) {
      return;
    }

    statsFetchInFlight.current = true;
    const t0 = performance.now();
    try {
      const res = await fetchWithTimeout(`${getApiUrl()}/api/kb/stats`, {}, 10000);
      const data = await res.json();
      setStats(data);
      lastGoodStats.current = data;
      addLog("success", "KB", `Stats loaded (${(performance.now() - t0).toFixed(0)}ms)`);
    } catch (error) {
      addLog("error", "KB", `Stats fetch failed: ${error}`);
      // Preserve last-known-good stats instead of showing Offline
      if (lastGoodStats.current && !stats) {
        setStats(lastGoodStats.current);
      }
    } finally {
      statsFetchInFlight.current = false;
    }
  };

  const fetchArticles = async () => {
    if (articlesFetchInFlight.current) {
      return;
    }

    articlesFetchInFlight.current = true;
    setArticlesLoading(true);
    const t0 = performance.now();
    try {
      const res = await fetchWithTimeout(`${getApiUrl()}/api/kb/list?limit=100`, {}, 10000);
      const data = await res.json();
      setArticles(data.items || []);
      addLog("success", "KB", `Articles loaded: ${(data.items || []).length} (${(performance.now() - t0).toFixed(0)}ms)`);
    } catch (error) {
      addLog("error", "KB", `Articles fetch failed: ${error}`);
    } finally {
      articlesFetchInFlight.current = false;
      setArticlesLoading(false);
    }
  };

  const handleAddDocument = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;

    setAddLoading(true);
    setAddResult(null);

    try {
      const res = await fetch(`${getApiUrl()}/api/kb/index`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: content.trim(),
          title: title.trim() || null,
          category,
        }),
      });

      const data = await res.json();

      if (res.ok) {
        setAddResult({ success: true, message: data.message || "Document indexed successfully" });
        setTitle("");
        setContent("");
        setCategory("GENERAL");
        fetchStats();
        fetchArticles();
      } else {
        setAddResult({ success: false, message: data.detail || "Indexing failed" });
      }
    } catch (error) {
      setAddResult({ success: false, message: `Error: ${error}` });
    } finally {
      setAddLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadLoading(true);
    setUploadResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("category", category);

      const res = await fetch(`${getApiUrl()}/api/kb/index/file`, {
        method: "POST",
        body: formData,
      });

      const data = await res.json();

      if (res.ok) {
        const msg = data.successful !== undefined
          ? `Imported ${data.successful}/${data.total} documents`
          : data.message || "File indexed successfully";
        setUploadResult({ success: true, message: msg });
        fetchStats();
        fetchArticles();
      } else {
        setUploadResult({ success: false, message: data.detail || "Upload failed" });
      }
    } catch (error) {
      setUploadResult({ success: false, message: `Error: ${error}` });
    } finally {
      setUploadLoading(false);
      e.target.value = "";
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setSearchLoading(true);
    setSearchDone(false);

    try {
      const res = await fetch(`${getApiUrl()}/api/kb/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: searchQuery.trim(),
          top_k: 5,
        }),
      });

      const data = await res.json();
      setSearchResults(data.results || []);
      setSearchDone(true);
    } catch (error) {
      console.error("Search failed:", error);
      setSearchResults([]);
      setSearchDone(true);
    } finally {
      setSearchLoading(false);
    }
  };

  const handleClearKB = async () => {
    if (!confirm("Are you sure? This will delete ALL knowledge base data from MongoDB and Pinecone.")) return;

    setClearLoading(true);
    try {
      const res = await fetch(`${getApiUrl()}/api/kb/clear`, { method: "DELETE" });
      if (res.ok) {
        fetchStats();
        fetchArticles();
        setSearchResults([]);
      }
    } catch (error) {
      console.error("Clear failed:", error);
    } finally {
      setClearLoading(false);
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 0.8) return "text-green-400 bg-green-500/15";
    if (score >= 0.5) return "text-yellow-400 bg-yellow-500/15";
    return "text-red-400 bg-red-500/15";
  };

  const getCategoryColor = (cat: string) => {
    const colors: Record<string, string> = {
      BUG: "bg-red-500/15 text-red-400",
      API_ISSUE: "bg-orange-500/15 text-orange-400",
      PERFORMANCE: "bg-yellow-500/15 text-yellow-400",
      FEATURE: "bg-blue-500/15 text-blue-400",
      GENERAL: "bg-slate-500/15 text-slate-400",
    };
    return colors[cat] || "bg-slate-500/15 text-slate-400";
  };

  return (
    <div className="min-h-screen bg-[#0b0f1a]">
      {/* Header */}
      <header className="bg-gradient-to-r from-indigo-600/20 to-purple-600/20 border-b border-white/5">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              href="/dashboard"
              className="flex items-center gap-1 text-slate-400 hover:text-slate-200 transition-colors text-sm"
            >
              <ArrowLeft className="w-4 h-4" />
              Dashboard
            </Link>
            <div className="h-6 w-px bg-white/10" />
            <div className="flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-indigo-400" />
              <h1 className="text-xl font-semibold text-white">Knowledge Base</h1>
            </div>
          </div>
          <button
            onClick={handleClearKB}
            disabled={clearLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-red-400 hover:bg-red-500/15 rounded-lg transition-colors border border-red-500/30"
          >
            {clearLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
            Clear All
          </button>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-6">
        {/* Stats Cards */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="bg-[#111827] rounded-xl border border-white/5 p-4">
            <div className="flex items-center gap-2 mb-1">
              <FileText className="w-4 h-4 text-blue-400" />
              <span className="text-sm text-slate-400">Documents</span>
            </div>
            <p className="text-2xl font-bold text-white">
              {stats?.total_articles ?? "\u2014"}
            </p>
          </div>
          <div className="bg-[#111827] rounded-xl border border-white/5 p-4">
            <div className="flex items-center gap-2 mb-1">
              <Layers className="w-4 h-4 text-purple-400" />
              <span className="text-sm text-slate-400">Vectors</span>
            </div>
            <p className="text-2xl font-bold text-white">
              {stats?.vector_store?.total_vectors ?? "\u2014"}
            </p>
          </div>
          <div className="bg-[#111827] rounded-xl border border-white/5 p-4">
            <div className="flex items-center gap-2 mb-1">
              <Database className="w-4 h-4 text-green-400" />
              <span className="text-sm text-slate-400">Store</span>
            </div>
            <p className="text-lg font-semibold text-white">
              {stats == null ? (
                <span className="text-slate-500">Checking...</span>
              ) : stats.vector_store?.initialized ? (
                <span className="text-green-400">Pinecone ✓</span>
              ) : (
                <span className="text-red-400">Offline</span>
              )}
            </p>
          </div>
          <div className="bg-[#111827] rounded-xl border border-white/5 p-4">
            <div className="flex items-center gap-2 mb-1">
              <Zap className="w-4 h-4 text-amber-400" />
              <span className="text-sm text-slate-400">Dimensions</span>
            </div>
            <p className="text-2xl font-bold text-white">
              {stats?.vector_store?.dimension ?? "\u2014"}
            </p>
          </div>
        </div>

        {/* Categories breakdown */}
        {stats?.categories && Object.keys(stats.categories).length > 0 && (
          <div className="flex gap-2 mb-6 flex-wrap">
            {Object.entries(stats.categories).map(([cat, count]) => (
              <span key={cat} className={`px-3 py-1 rounded-full text-xs font-medium ${getCategoryColor(cat)}`}>
                {cat}: {count}
              </span>
            ))}
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 mb-6 bg-white/[0.03] rounded-lg p-1 w-fit border border-white/5">
          {[
            { id: "add" as const, label: "Add Document", icon: Plus },
            { id: "upload" as const, label: "Upload File", icon: Upload },
            { id: "search" as const, label: "Test Search", icon: Search },
            { id: "browse" as const, label: "Browse", icon: FileText },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-all ${
                activeTab === tab.id
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="bg-[#111827] rounded-xl border border-white/5">
          {/* ADD DOCUMENT TAB */}
          {activeTab === "add" && (
            <form onSubmit={handleAddDocument} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Title</label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. API returns 500 on file upload"
                  className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/40 outline-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Category</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-slate-200 focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/40 outline-none"
                >
                  {CATEGORIES.map((cat) => (
                    <option key={cat} value={cat} className="bg-[#111827] text-slate-200">
                      {cat}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Content</label>
                <textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  rows={8}
                  placeholder="Paste the full article, runbook, troubleshooting guide, or FAQ content here..."
                  className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/40 outline-none resize-y"
                  required
                />
              </div>

              <div className="flex items-center gap-3">
                <button
                  type="submit"
                  disabled={addLoading || !content.trim()}
                  className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {addLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                  Index Document
                </button>

                {addResult && (
                  <div
                    className={`flex items-center gap-1.5 text-sm ${
                      addResult.success ? "text-green-400" : "text-red-400"
                    }`}
                  >
                    {addResult.success ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                    {addResult.message}
                  </div>
                )}
              </div>
            </form>
          )}

          {/* UPLOAD FILE TAB */}
          {activeTab === "upload" && (
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Category for imported documents</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-slate-200 focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/40 outline-none"
                >
                  {CATEGORIES.map((cat) => (
                    <option key={cat} value={cat} className="bg-[#111827] text-slate-200">
                      {cat}
                    </option>
                  ))}
                </select>
              </div>

              <div className="border-2 border-dashed border-white/10 rounded-xl p-8 text-center hover:border-indigo-500/40 transition-colors">
                <Upload className="w-10 h-10 text-slate-500 mx-auto mb-3" />
                <p className="text-sm text-slate-300 mb-1">Upload a JSON, CSV, or TXT file</p>
                <p className="text-xs text-slate-500 mb-4">
                  JSON: array of {`{title, content, category}`} objects &bull; CSV: columns for title, content &bull; TXT: plain text
                </p>
                <label className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-500 transition-colors cursor-pointer">
                  {uploadLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                  {uploadLoading ? "Uploading..." : "Choose File"}
                  <input
                    type="file"
                    accept=".json,.csv,.txt"
                    onChange={handleFileUpload}
                    className="hidden"
                    disabled={uploadLoading}
                  />
                </label>
              </div>

              {uploadResult && (
                <div
                  className={`flex items-center gap-1.5 text-sm ${
                    uploadResult.success ? "text-green-400" : "text-red-400"
                  }`}
                >
                  {uploadResult.success ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                  {uploadResult.message}
                </div>
              )}

              <div className="bg-white/[0.03] rounded-lg p-4 border border-white/5">
                <h3 className="text-sm font-medium text-slate-300 mb-2">JSON Format Example</h3>
                <pre className="text-xs text-slate-400 bg-white/[0.03] p-3 rounded border border-white/5 overflow-x-auto">
{`[
  {
    "title": "API returns 500 on large payloads",
    "content": "When uploading files larger than 10MB, the API may return a 500 error. This is caused by the default request body size limit. Solution: Increase MAX_BODY_SIZE in the server config to 50MB.",
    "category": "API_ISSUE"
  },
  {
    "title": "High memory usage after deployment",
    "content": "If memory usage spikes after deploying v2.3, check for the known memory leak in the WebSocket handler. Workaround: restart the service every 24h until patch v2.3.1 is applied.",
    "category": "PERFORMANCE"
  }
]`}
                </pre>
              </div>
            </div>
          )}

          {/* SEARCH TAB */}
          {activeTab === "search" && (
            <div className="p-6 space-y-4">
              <form onSubmit={handleSearch} className="flex gap-2">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Test a search query, e.g. 'API returning 500 error'"
                  className="flex-1 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/40 outline-none"
                />
                <button
                  type="submit"
                  disabled={searchLoading || !searchQuery.trim()}
                  className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-500 transition-colors disabled:opacity-50"
                >
                  {searchLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                  Search
                </button>
              </form>

              {searchDone && searchResults.length === 0 && (
                <div className="text-center py-8 text-slate-500">
                  <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No results found. Make sure you have indexed some documents first.</p>
                </div>
              )}

              {searchResults.length > 0 && (
                <div className="space-y-3">
                  <p className="text-sm text-slate-400">{searchResults.length} results</p>
                  {searchResults.map((result, idx) => (
                    <div key={result.id || idx} className="border border-white/5 rounded-lg p-4 hover:border-indigo-500/30 transition-colors bg-white/[0.03]">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono text-slate-500">#{idx + 1}</span>
                          {typeof result.metadata?.category === "string" && (
                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${getCategoryColor(result.metadata.category)}`}>
                              {result.metadata.category}
                            </span>
                          )}
                          {typeof result.metadata?.title === "string" && (
                            <span className="text-sm font-medium text-slate-200">{result.metadata.title}</span>
                          )}
                        </div>
                        <span className={`px-2 py-0.5 rounded text-xs font-semibold ${getScoreColor(result.score)}`}>
                          {(result.score * 100).toFixed(1)}%
                        </span>
                      </div>
                      <p className="text-sm text-slate-300 leading-relaxed">{result.text}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* BROWSE TAB */}
          {activeTab === "browse" && (
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <p className="text-sm text-slate-400">{articles.length} articles in database</p>
                <button
                  onClick={fetchArticles}
                  disabled={articlesLoading}
                  className="text-sm text-indigo-400 hover:text-indigo-300"
                >
                  {articlesLoading ? "Loading..." : "Refresh"}
                </button>
              </div>

              {articles.length === 0 ? (
                <div className="text-center py-12 text-slate-500">
                  <BookOpen className="w-10 h-10 mx-auto mb-3 opacity-50" />
                  <p className="text-sm">No articles yet. Add documents using the tabs above.</p>
                </div>
              ) : (
                <div className="space-y-2 max-h-[500px] overflow-y-auto">
                  {articles.map((article) => (
                      <div key={article.article_id} className="border border-white/5 rounded-lg p-3 hover:bg-white/[0.03] transition-colors">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs text-slate-500 font-mono">{article.article_id}</span>
                          {article.category && (
                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${getCategoryColor(article.category)}`}>
                              {article.category}
                            </span>
                          )}
                          {article.title && (
                            <span className="text-sm font-medium text-slate-200">{article.title}</span>
                          )}
                          <span className="text-xs text-slate-500 ml-auto">
                            {new Date(article.created_at).toLocaleDateString()}
                          </span>
                        </div>
                        <p className="text-xs text-slate-400 line-clamp-2">{article.content}</p>
                      </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* What to include guide */}
        <div className="mt-6 bg-[#111827] rounded-xl border border-white/5 p-6">
          <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-indigo-400" />
            What to include in your Knowledge Base
          </h2>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="space-y-2">
              <div className="flex items-start gap-2">
                <span className="px-2 py-0.5 rounded text-xs font-medium bg-red-500/15 text-red-400 mt-0.5">BUG</span>
                <p className="text-slate-300">Known bugs, crash reports, error patterns, workarounds</p>
              </div>
              <div className="flex items-start gap-2">
                <span className="px-2 py-0.5 rounded text-xs font-medium bg-orange-500/15 text-orange-400 mt-0.5">API_ISSUE</span>
                <p className="text-slate-300">Error codes (4xx/5xx), auth failures, rate limits, endpoint docs</p>
              </div>
              <div className="flex items-start gap-2">
                <span className="px-2 py-0.5 rounded text-xs font-medium bg-yellow-500/15 text-yellow-400 mt-0.5">PERFORMANCE</span>
                <p className="text-slate-300">Slow queries, timeouts, memory leaks, scaling guides</p>
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex items-start gap-2">
                <span className="px-2 py-0.5 rounded text-xs font-medium bg-blue-500/15 text-blue-400 mt-0.5">FEATURE</span>
                <p className="text-slate-300">Feature flags, deprecations, migration guides, release notes</p>
              </div>
              <div className="flex items-start gap-2">
                <span className="px-2 py-0.5 rounded text-xs font-medium bg-slate-500/15 text-slate-400 mt-0.5">GENERAL</span>
                <p className="text-slate-300">Runbooks, architecture docs, escalation criteria, SLA policies</p>
              </div>
            </div>
          </div>
        </div>
      </div>
      <DebugPanel wsStatus={wsStatus} logs={logs} />
    </div>
  );
}
