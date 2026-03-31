"use client";

import { useState, useEffect, useMemo, useRef } from "react";
import { AlertCircle, Clock, CheckCircle, XCircle, Search, Filter, Sparkles, BookOpen, Shield, Bug, Zap, Server, Globe, Lightbulb, HelpCircle, Send, MessageSquare, LogOut } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useWebSocket } from "../../hooks/useWebSocket";
import DebugPanel, { useDebugLog } from "../../components/DebugPanel";
import { fetchWithTimeout, getApiUrl } from "@/lib/runtime-config";
import { useAuth } from "@/hooks/useAuth";

interface Ticket {
  ticket_id: string;
  subject: string;
  description?: string;
  status: string;
  category: string;
  severity?: string;
  priority?: string;
  product?: string;
  environment?: string;
  customer?: { email?: string; name?: string; company?: string };
  ai_analysis?: {
    sentiment?: string;
    sentiment_score?: number;
    summary?: string;
    routing?: { category?: string; confidence?: number; reason?: string; severity?: string };
    suggested_solution?: Record<string, unknown>;
    decision?: Record<string, unknown>;
    matched_kb_articles?: string[];
  };
  assigned_team?: string;
  tags?: string[];
  created_at?: string;
  priority_score?: number;
  priority_reasons?: string[];
}

interface TriageStat {
  category: string;
  count: number;
  new: number;
  in_progress: number;
  resolved: number;
  escalated: number;
  waiting_on_customer: number;
  forwarded: number;
  negative_sentiment: number;
}

interface RouteInfo {
  category?: string;
  confidence?: number;
  reason?: string;
  severity?: string;
}

interface SentimentInfo {
  sentiment?: string;
  label?: string;
  confidence?: number;
  score?: number;
}

interface DecisionInfo {
  action?: string;
  confidence?: number;
  reason?: string;
  next_steps?: string[];
  assigned_team?: string;
}

interface Solution {
  draft_reply: string;
  resolution_steps: string[];
  confidence: number;
  relevant_articles: { id?: string; title?: string; score?: number }[];
}

interface Insights {
  route: RouteInfo | null;
  sentiment: SentimentInfo | null;
  summary: string;
  solution?: Solution;
  decision?: DecisionInfo;
}

interface ConversationMessage {
  message_id: string;
  ticket_id: string;
  sender: "agent" | "customer" | "system";
  body: string;
  msg_type: "reply" | "note" | "status_change";
  email_status: string;
  created_at: string;
}

const CATEGORY_META: Record<string, { label: string; icon: string; color: string; borderColor: string }> = {
  BUG:              { label: "Bug",             icon: "bug",      color: "bg-red-500/15 text-red-400",        borderColor: "border-red-500/30" },
  PERFORMANCE:      { label: "Performance",     icon: "zap",      color: "bg-amber-500/15 text-amber-400",    borderColor: "border-amber-500/30" },
  API_ISSUE:        { label: "API Issue",       icon: "globe",    color: "bg-violet-500/15 text-violet-400",  borderColor: "border-violet-500/30" },
  SECURITY:         { label: "Security",        icon: "shield",   color: "bg-rose-500/15 text-rose-400",      borderColor: "border-rose-500/30" },
  INFRASTRUCTURE:   { label: "Infrastructure",  icon: "server",   color: "bg-sky-500/15 text-sky-400",        borderColor: "border-sky-500/30" },
  FEATURE_REQUEST:  { label: "Feature Request", icon: "lightbulb",color: "bg-emerald-500/15 text-emerald-400",borderColor: "border-emerald-500/30" },
  GENERAL_INQUIRY:  { label: "General Inquiry", icon: "help",     color: "bg-slate-500/15 text-slate-400",    borderColor: "border-slate-500/30" },
  UNPROCESSED:      { label: "Unprocessed",     icon: "help",     color: "bg-yellow-500/15 text-yellow-400",  borderColor: "border-yellow-500/30" },
};

const SEVERITY_COLOR: Record<string, string> = {
  SEV1: "bg-red-500/20 text-red-400 border border-red-500/30",
  SEV2: "bg-orange-500/20 text-orange-400 border border-orange-500/30",
  SEV3: "bg-yellow-500/20 text-yellow-400 border border-yellow-500/30",
  SEV4: "bg-slate-500/20 text-slate-400 border border-slate-500/30",
};

const CategoryIcon = ({ category, className }: { category: string; className?: string }) => {
  const meta = CATEGORY_META[category];
  const cn = className || "w-4 h-4";
  if (!meta) return <HelpCircle className={cn} />;
  switch (meta.icon) {
    case "bug": return <Bug className={cn} />;
    case "zap": return <Zap className={cn} />;
    case "globe": return <Globe className={cn} />;
    case "shield": return <Shield className={cn} />;
    case "server": return <Server className={cn} />;
    case "lightbulb": return <Lightbulb className={cn} />;
    default: return <HelpCircle className={cn} />;
  }
};

export default function DashboardPage() {
  const router = useRouter();
  const { user, loading: authLoading, logout } = useAuth();

  // Auth guard: redirect to login if not authenticated or wrong role
  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.push("/login");
      return;
    }
    if (user.role !== "agent" && user.role !== "admin") {
      router.push("/login");
    }
  }, [user, authLoading, router]);

  const [triageStats, setTriageStats] = useState<TriageStat[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [categoryTickets, setCategoryTickets] = useState<Ticket[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null);
  const [insights, setInsights] = useState<Insights | null>(null);
  const [priorityQueue, setPriorityQueue] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [apiError, setApiError] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationMessage[]>([]);
  const [replyText, setReplyText] = useState("");
  const [sendingReply, setSendingReply] = useState(false);
  const [closingTicket, setClosingTicket] = useState(false);
  const [detailTab, setDetailTab] = useState<"details" | "chat" | "conversation">("details");
  const [selectedTeam, setSelectedTeam] = useState<string>(() => {
    // Agents see their team by default, admins see all
    return "all";
  });
  const [showForwardForm, setShowForwardForm] = useState(false);
  const [forwardTeam, setForwardTeam] = useState("");
  const [forwardNote, setForwardNote] = useState("");
  const [forwarding, setForwarding] = useState(false);
  const [chatMessages, setChatMessages] = useState<{role: string; content: string; created_at?: string}[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const conversationEndRef = useRef<HTMLDivElement>(null);
  const insightsAbortRef = useRef<AbortController | null>(null);
  const triageFetchInFlight = useRef(false);
  const priorityFetchInFlight = useRef(false);
  const categoryFetchInFlight = useRef(false);
  const hasRefreshedOnWsConnect = useRef(false);
  const hasRunInitialLoad = useRef(false);

  // Debug logging
  const { logs, addLog } = useDebugLog();

  // WebSocket connection
  const { status: wsStatus } = useWebSocket({
    subscriptions: [
      "ticket:created",
      "ticket:updated",
      "triage:stats_updated",
      "insight:generated",
      "solution:suggested",
      "ticket:reply_sent",
      "ticket:resolved",
    ],
    onEvent: (event) => {
      if (event.type === "subscribed") {
        return;
      }

      addLog("info", "WS", `Event: ${event.type}`);
      if (
        event.type === "ticket:created" ||
        event.type === "ticket:updated" ||
        event.type === "triage:stats_updated"
      ) {
        fetchTriageStats();
        fetchPriorityQueue();
        if (selectedCategory) {
          fetchCategoryTickets(
            selectedCategory,
            statusFilter === "all" ? undefined : statusFilter
          );
        }
      }

      // Live conversation update
      if (event.type === "ticket:reply_sent" || event.type === "ticket:resolved") {
        const evtTicketId = (event.payload as Record<string, unknown>).ticket_id as string;
        if (selectedTicket && evtTicketId === selectedTicket.ticket_id) {
          fetchConversations(evtTicketId);
        }
      }

      // Insights arrived via WebSocket — merge with existing (solution may arrive separately)
      if (event.type === "insight:generated") {
        const evtTicketId = event.payload.ticket_id as string;
        if (selectedTicket && evtTicketId === selectedTicket.ticket_id) {
          const incoming = event.payload.insights as Insights;
          setInsights((prev) => prev ? { ...prev, ...incoming } : incoming);
          setLoading(null);
        }
      }
    },
  });

  // Initial load
  // Auto-set team from user role when auth loads
  useEffect(() => {
    if (!user) return;
    if (user.role === "agent" && user.team) {
      setSelectedTeam(user.team);
    }
  }, [user]);

  useEffect(() => {
    if (authLoading || !user) return;
    if (hasRunInitialLoad.current) {
      return;
    }

    hasRunInitialLoad.current = true;
    addLog("info", "Dashboard", "Initial data load");
    fetchTriageStats();
    fetchPriorityQueue();
  }, [authLoading, user]);

  // Re-fetch when team filter changes
  useEffect(() => {
    if (!hasRunInitialLoad.current) return;
    fetchTriageStats();
    fetchPriorityQueue();
    if (selectedCategory) {
      fetchCategoryTickets(selectedCategory, statusFilter === "all" ? undefined : statusFilter);
    }
  }, [selectedTeam]);

  // Refresh immediately when WS becomes healthy.
  useEffect(() => {
    if (wsStatus !== "connected" || hasRefreshedOnWsConnect.current) {
      return;
    }

    hasRefreshedOnWsConnect.current = true;
    addLog("success", "WS", "Connected; refreshing dashboard data");
    fetchTriageStats();
    fetchPriorityQueue();
    if (selectedCategory) {
      fetchCategoryTickets(
        selectedCategory,
        statusFilter === "all" ? undefined : statusFilter
      );
    }
  }, [wsStatus, selectedCategory, statusFilter]);

  // Poll only when websocket is not connected.
  useEffect(() => {
    if (wsStatus === "connected") {
      return;
    }

    const interval = setInterval(() => {
      addLog("info", "Dashboard", "Fallback poll (60s)");
      fetchTriageStats();
      fetchPriorityQueue();
    }, 60000);

    return () => clearInterval(interval);
  }, [wsStatus]);

  // Refresh category tickets when category selected
  useEffect(() => {
    if (selectedCategory) {
      fetchCategoryTickets(
        selectedCategory,
        statusFilter === "all" ? undefined : statusFilter
      );
    }
  }, [selectedCategory, statusFilter]);

  const fetchTriageStats = async () => {
    if (triageFetchInFlight.current) {
      return;
    }

    triageFetchInFlight.current = true;
    const t0 = performance.now();
    try {
      const res = await fetchWithTimeout(
        `${getApiUrl()}/api/tickets/stats/triage${selectedTeam !== "all" ? `?team=${selectedTeam}` : ""}`,
        {},
        10000
      );
      const data = await res.json();
      setTriageStats(Array.isArray(data) ? data : []);
      setApiError(null);
      addLog("success", "Dashboard", `Triage stats loaded (${(performance.now() - t0).toFixed(0)}ms)`);
    } catch (error) {
      const message = getDashboardErrorMessage(error);
      setApiError(message);
      addLog("error", "Dashboard", `Triage stats failed: ${message}`);
    } finally {
      triageFetchInFlight.current = false;
    }
  };

  const fetchPriorityQueue = async () => {
    if (priorityFetchInFlight.current) {
      return;
    }

    priorityFetchInFlight.current = true;
    const t0 = performance.now();
    try {
      const res = await fetchWithTimeout(
        `${getApiUrl()}/api/tickets/priority-queue${selectedTeam !== "all" ? `?team=${selectedTeam}` : ""}`,
        {},
        10000
      );
      const data = await res.json();
      setPriorityQueue(data.tickets || []);
      setApiError(null);
      addLog("success", "Dashboard", `Priority queue loaded: ${(data.tickets || []).length} tickets (${(performance.now() - t0).toFixed(0)}ms)`);
    } catch (error) {
      const message = getDashboardErrorMessage(error);
      setApiError((current) => current ?? message);
      addLog("error", "Dashboard", `Priority queue failed: ${message}`);
    } finally {
      priorityFetchInFlight.current = false;
    }
  };

  const fetchCategoryTickets = async (category: string, status?: string) => {
    if (categoryFetchInFlight.current) {
      return;
    }

    categoryFetchInFlight.current = true;
    setLoading("tickets");
    const t0 = performance.now();
    try {
      const teamParam = selectedTeam !== "all" ? `team=${selectedTeam}` : "";
      const params = [status ? `status=${status}` : "", teamParam].filter(Boolean).join("&");
      const url = `${getApiUrl()}/api/tickets/by-category/${category}${params ? `?${params}` : ""}`;
      const res = await fetchWithTimeout(url, {}, 10000);
      const data = await res.json();
      setCategoryTickets(data.tickets || []);
      addLog("success", "Dashboard", `${category} tickets loaded: ${(data.tickets || []).length} (${(performance.now() - t0).toFixed(0)}ms)`);
    } catch (error) {
      addLog("error", "Dashboard", `Category tickets failed: ${error}`);
    } finally {
      categoryFetchInFlight.current = false;
      setLoading(null);
    }
  };

  const fetchInsights = async (ticket: Ticket) => {
    setLoading("insights");
    try {
      const text = `${ticket.subject}\n\n${ticket.description || ""}`;
      const res = await fetchWithTimeout(
        `${getApiUrl()}/insights`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text,
            ticket_id: ticket.ticket_id,
            top_k: 5
          }),
          signal: insightsAbortRef.current?.signal,
        },
        120000
      );
      const data = await res.json();
      setInsights(data);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      addLog("error", "Dashboard", `Insights failed: ${error}`);
    } finally {
      setLoading(null);
    }
  };

  const updateTicketStatus = async (ticketId: string, newStatus: string) => {
    try {
      await fetchWithTimeout(
        `${getApiUrl()}/api/tickets/status`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ticket_id: ticketId, status: newStatus })
        },
        10000
      );

      // Refresh data
      fetchTriageStats();
      fetchPriorityQueue();
      if (selectedCategory) {
        fetchCategoryTickets(selectedCategory, statusFilter === "all" ? undefined : statusFilter);
      }
    } catch (error) {
      console.error("Failed to update ticket status:", error);
    }
  };

  const assignTicketTeam = async (ticketId: string, team: string) => {
    try {
      await fetchWithTimeout(
        `${getApiUrl()}/api/tickets/assign`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ticket_id: ticketId, assigned_team: team })
        },
        10000
      );
      // Update local state
      setSelectedTicket((prev) => prev ? { ...prev, assigned_team: team } : prev);
      // Update ticket in category list so dashboard reflects the change
      setCategoryTickets((prev) => prev.map((t) => t.ticket_id === ticketId ? { ...t, assigned_team: team } : t));
      setPriorityQueue((prev) => prev.map((t) => t.ticket_id === ticketId ? { ...t, assigned_team: team } : t));
      fetchTriageStats();
      addLog("success", "Dashboard", `Assigned ${ticketId} to ${team}`);
    } catch (error) {
      addLog("error", "Dashboard", `Assign failed: ${error}`);
    }
  };

  const forwardTicket = async () => {
    if (!selectedTicket || !forwardTeam || forwarding) return;
    setForwarding(true);
    try {
      await fetchWithTimeout(
        `${getApiUrl()}/api/tickets/${selectedTicket.ticket_id}/forward`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ team: forwardTeam, note: forwardNote })
        },
        10000
      );
      setSelectedTicket((prev) => prev ? { ...prev, status: "forwarded", assigned_team: forwardTeam } : prev);
      setCategoryTickets((prev) => prev.map((t) => t.ticket_id === selectedTicket.ticket_id ? { ...t, status: "forwarded", assigned_team: forwardTeam } : t));
      setShowForwardForm(false);
      setForwardTeam("");
      setForwardNote("");
      fetchTriageStats();
      fetchPriorityQueue();
      if (selectedCategory) {
        fetchCategoryTickets(selectedCategory, statusFilter === "all" ? undefined : statusFilter);
      }
      // Switch to conversation tab to show the forwarding note
      setDetailTab("conversation");
      fetchConversations(selectedTicket.ticket_id);
      addLog("success", "Dashboard", `Forwarded ${selectedTicket.ticket_id} to ${forwardTeam}`);
    } catch (error) {
      addLog("error", "Dashboard", `Forward failed: ${error}`);
    } finally {
      setForwarding(false);
    }
  };

  const fetchConversations = async (ticketId: string) => {
    try {
      const res = await fetchWithTimeout(
        `${getApiUrl()}/api/tickets/${ticketId}/conversations`,
        {},
        10000
      );
      const data = await res.json();
      setConversations(data.messages || []);
      addLog("success", "Dashboard", `Conversations loaded: ${(data.messages || []).length}`);
      // Auto-scroll to bottom
      setTimeout(() => conversationEndRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
    } catch (error) {
      addLog("error", "Dashboard", `Conversations failed: ${error}`);
    }
  };

  const sendReply = async () => {
    if (!selectedTicket || !replyText.trim() || sendingReply) return;
    setSendingReply(true);
    try {
      const res = await fetchWithTimeout(
        `${getApiUrl()}/api/tickets/${selectedTicket.ticket_id}/reply`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ body: replyText.trim() }),
        },
        15000
      );
      const data = await res.json();
      if (data.ok) {
        setReplyText("");
        addLog("success", "Dashboard", `Reply sent to ${selectedTicket.ticket_id}`);
        // Update selected ticket status locally
        setSelectedTicket((prev) => prev ? { ...prev, status: "waiting_on_customer" } : prev);
        // Refresh conversations
        fetchConversations(selectedTicket.ticket_id);
        // Refresh lists
        fetchTriageStats();
        fetchPriorityQueue();
        if (selectedCategory) {
          fetchCategoryTickets(selectedCategory, statusFilter === "all" ? undefined : statusFilter);
        }
      }
    } catch (error) {
      addLog("error", "Dashboard", `Reply failed: ${error}`);
    } finally {
      setSendingReply(false);
    }
  };

  const handleCloseTicket = async () => {
    if (!selectedTicket || closingTicket) return;
    setClosingTicket(true);
    try {
      const res = await fetchWithTimeout(
        `${getApiUrl()}/api/tickets/${selectedTicket.ticket_id}/close`,
        { method: "POST" },
        15000
      );
      const data = await res.json();
      if (data.ok) {
        addLog("success", "Dashboard", `Ticket ${selectedTicket.ticket_id} closed (${data.resolution_time_ms}ms resolution)`);
        setSelectedTicket((prev) => prev ? { ...prev, status: "resolved" } : prev);
        fetchConversations(selectedTicket.ticket_id);
        fetchTriageStats();
        fetchPriorityQueue();
        if (selectedCategory) {
          fetchCategoryTickets(selectedCategory, statusFilter === "all" ? undefined : statusFilter);
        }
      }
    } catch (error) {
      addLog("error", "Dashboard", `Close ticket failed: ${error}`);
    } finally {
      setClosingTicket(false);
    }
  };

  const fetchChatHistory = async (ticketId: string) => {
    try {
      const res = await fetchWithTimeout(`${getApiUrl()}/chat/${ticketId}`, {}, 5000);
      const data = await res.json();
      setChatMessages(data.messages || []);
    } catch {
      setChatMessages([]);
    }
  };

  const sendChatMessage = async () => {
    if (!selectedTicket || !chatInput.trim() || chatLoading) return;

    const userMessage = chatInput.trim();
    setChatInput("");
    setChatMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setChatLoading(true);

    try {
      const insightsContext = {
        summary: insights?.summary || "",
        category: insights?.route?.category || "",
        severity: insights?.route?.severity || "",
        sentiment: insights?.sentiment?.sentiment || insights?.sentiment?.label || "",
        resolution_steps: insights?.solution?.resolution_steps || [],
        draft_reply: insights?.solution?.draft_reply || "",
      };

      const res = await fetchWithTimeout(
        `${getApiUrl()}/chat`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ticket_id: selectedTicket.ticket_id,
            message: userMessage,
            insights_context: insightsContext,
            chat_history: chatMessages.slice(-10),
          }),
        },
        30000
      );
      const data = await res.json();
      setChatMessages((prev) => [...prev, { role: "assistant", content: data.response }]);
    } catch (error) {
      setChatMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Sorry, I couldn't process that. Please try again." },
      ]);
      addLog("error", "Chat", `Chat failed: ${error}`);
    } finally {
      setChatLoading(false);
      setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
    }
  };

  const handleTicketSelect = async (ticket: Ticket) => {
    insightsAbortRef.current?.abort();
    insightsAbortRef.current = new AbortController();
    setSelectedTicket(ticket);
    setInsights(null);
    setDetailTab("details");
    setReplyText("");
    setConversations([]);
    setChatMessages([]);
    setChatInput("");

    // Load conversations and chat history in parallel
    fetchConversations(ticket.ticket_id);
    fetchChatHistory(ticket.ticket_id);

    // Try cached insights first
    try {
      const cacheRes = await fetchWithTimeout(
        `${getApiUrl()}/insights/${ticket.ticket_id}`,
        {},
        5000
      );
      const cacheData = await cacheRes.json();
      if (cacheData.cached) {
        setInsights(cacheData);
        addLog("success", "Dashboard", `Loaded cached insights for ${ticket.ticket_id}`);
        return;
      }
    } catch {
      // Cache miss or error — fall through to generate
    }

    // No cache — generate fresh insights
    fetchInsights(ticket);
  };

  const filteredTickets = useMemo(() => {
    if (!searchQuery) return categoryTickets;
    const q = searchQuery.toLowerCase();
    return categoryTickets.filter(t =>
      t.subject.toLowerCase().includes(q) ||
      t.ticket_id.toLowerCase().includes(q) ||
      (t.description || "").toLowerCase().includes(q)
    );
  }, [categoryTickets, searchQuery]);

  const getCategoryColor = (category: string) => {
    const meta = CATEGORY_META[category];
    return meta ? `${meta.color} ${meta.borderColor}` : "bg-gray-100 text-gray-800 border-gray-300";
  };

  const getCategoryLabel = (category: string) => {
    return CATEGORY_META[category]?.label || category;
  };

  const getSentimentColor = (sentiment: string) => {
    const s = sentiment?.toLowerCase();
    if (s === "positive" || s === "very_positive") return "text-emerald-400";
    if (s === "negative" || s === "very_negative") return "text-red-400";
    return "text-slate-400";
  };

  const getSeverityBadge = (severity?: string) => {
    if (!severity) return null;
    const color = SEVERITY_COLOR[severity] || "bg-slate-200 text-slate-700";
    return <span className={`px-2 py-0.5 rounded text-xs font-bold ${color}`}>{severity}</span>;
  };

  const ticketSentiment = (ticket: Ticket) => ticket.ai_analysis?.sentiment || "unknown";
  const ticketConfidence = (ticket: Ticket) => ticket.ai_analysis?.routing?.confidence;

  const apiHost = getApiUrl();

  function getDashboardErrorMessage(error: unknown) {
    if (error instanceof DOMException && error.name === "TimeoutError") {
      return `Backend request to ${apiHost} timed out after 10s.`;
    }

    if (error instanceof Error && error.name === "AbortError") {
      return `Request to ${apiHost} was aborted.`;
    }

    if (error instanceof Error && error.message) {
      return error.message;
    }

    return String(error);
  }

  // Show loading while checking auth
  if (authLoading || !user) {
    return (
      <div className="min-h-screen bg-[#0b0f1a] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0b0f1a]">
      {/* Header */}
      <header className="bg-[#111827]/80 backdrop-blur-xl border-b border-white/5 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">Support Agent</h1>
              <p className="text-sm text-slate-500 mt-0.5">AI-Powered Technical Support</p>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 text-sm text-slate-400">
                <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse shadow-sm shadow-emerald-500/50"></div>
                <span className="font-medium">Live</span>
              </div>
              <select
                value={selectedTeam}
                onChange={(e) => setSelectedTeam(e.target.value)}
                className="px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-sm text-slate-200 outline-none cursor-pointer"
              >
                <option value="all" className="bg-[#111827]">All Teams</option>
                <option value="general" className="bg-[#111827]">General</option>
                <option value="engineering" className="bg-[#111827]">Engineering</option>
                <option value="api-platform" className="bg-[#111827]">API Platform</option>
                <option value="security" className="bg-[#111827]">Security</option>
                <option value="devops" className="bg-[#111827]">DevOps</option>
                <option value="product" className="bg-[#111827]">Product</option>
              </select>
              {user.role === "admin" && (
                <Link
                  href="/admin"
                  className="flex items-center gap-2 px-3 py-1.5 bg-amber-500/10 border border-amber-500/20 rounded-lg hover:border-amber-500/40 transition-colors"
                >
                  <Shield className="w-4 h-4 text-amber-400" />
                  <span className="text-sm font-medium text-amber-300">Admin</span>
                </Link>
              )}
              {user.role === "admin" && (
                <Link
                  href="/knowledge-base"
                  className="flex items-center gap-2 px-3 py-1.5 bg-indigo-500/10 border border-indigo-500/20 rounded-lg hover:border-indigo-500/40 transition-colors"
                >
                  <BookOpen className="w-4 h-4 text-indigo-400" />
                  <span className="text-sm font-medium text-indigo-300">Knowledge Base</span>
                </Link>
              )}
              <div className="flex items-center gap-2 px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg">
                <span className="text-sm text-slate-300">{user.name}</span>
                <span className="text-xs px-1.5 py-0.5 rounded bg-indigo-500/15 text-indigo-400">{user.role}</span>
              </div>
              <button
                onClick={() => { logout(); router.push("/login"); }}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-slate-400 hover:text-white hover:border-red-500/30 transition-colors"
              >
                <LogOut className="w-4 h-4" />
                <span className="text-sm">Logout</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-6">
        {apiError && (
          <div className="mb-6 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-300">
            Dashboard data could not be loaded from the backend at <span className="font-mono text-amber-400">{apiHost}</span>. {apiError}
          </div>
        )}

        {/* Priority Queue */}
        {priorityQueue.length > 0 && (
          <div className="mb-6 bg-red-500/5 border border-red-500/20 rounded-xl p-6">
            <div className="flex items-center gap-3 mb-4">
              <AlertCircle className="w-6 h-6 text-red-400" />
              <h2 className="text-xl font-bold text-red-300">Priority Queue</h2>
              <span className="text-sm text-red-400/60">Needs Attention</span>
            </div>
            <div className="grid gap-3">
              {priorityQueue.slice(0, 5).map((ticket) => (
                <div
                  key={ticket.ticket_id}
                  onClick={() => {
                    setSelectedCategory(ticket.category);
                    handleTicketSelect(ticket);
                  }}
                  className="bg-[#111827] rounded-lg p-4 border border-red-500/20 hover:border-red-500/40 cursor-pointer transition-all hover:bg-red-500/5"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="font-mono font-semibold text-slate-200 text-base">{ticket.ticket_id}</span>
                        {getSeverityBadge(ticket.severity)}
                        <span className={`px-2 py-0.5 rounded-full text-xs font-semibold border ${getCategoryColor(ticket.category)}`}>
                          {getCategoryLabel(ticket.category)}
                        </span>
                        <span className={`text-sm font-medium ${getSentimentColor(ticketSentiment(ticket))}`}>
                          {ticketSentiment(ticket)}
                        </span>
                      </div>
                      <p className="text-slate-300 text-base mb-2">{ticket.subject}</p>
                      <div className="flex flex-wrap gap-2">
                        {ticket.priority_reasons?.map((reason, idx) => (
                          <span key={idx} className="px-2 py-1 bg-red-500/15 text-red-400 text-xs rounded-full">
                            {reason}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-red-400">{ticket.priority_score}</div>
                      <div className="text-xs text-slate-500">Priority</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Main Content */}
        <div className="grid grid-cols-12 gap-6">
          {/* Left Sidebar - Triage Overview */}
          <div className="col-span-3">
            <div className="bg-[#111827] rounded-2xl border border-white/5 overflow-hidden">
              <div className="bg-gradient-to-r from-indigo-600/20 to-purple-600/20 border-b border-white/5 px-5 py-5">
                <h2 className="text-lg font-bold text-white">Triage Overview</h2>
                <p className="text-indigo-300/60 text-sm">Smart Category Analysis</p>
              </div>
              <div className="p-4 space-y-2">
                {triageStats.length === 0 ? (
                  <div className="text-center py-8 text-slate-500 text-sm">
                    <p>No tickets yet</p>
                    <p className="text-xs mt-2 text-slate-600">Tickets will appear here after ingestion</p>
                  </div>
                ) : (
                  triageStats.map((stat) => (
                  <button
                    key={stat.category}
                    onClick={() => {
                      setSelectedCategory(stat.category);
                      setStatusFilter("all");
                      setSelectedTicket(null);
                      setInsights(null);
                    }}
                    className={`w-full text-left p-4 rounded-xl border transition-all duration-200 ${
                      selectedCategory === stat.category
                        ? "border-indigo-500/50 bg-indigo-500/10"
                        : "border-white/5 hover:border-indigo-500/30 hover:bg-white/[0.02]"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <CategoryIcon category={stat.category} className="w-4 h-4 text-slate-400" />
                        <span className="font-semibold text-slate-200 text-sm">{getCategoryLabel(stat.category)}</span>
                      </div>
                      <span className="text-2xl font-bold text-indigo-400">{stat.count}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="flex items-center gap-1">
                        <div className="w-2 h-2 rounded-full bg-yellow-500/70"></div>
                        <span className="text-slate-500">New: {stat.new}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <div className="w-2 h-2 rounded-full bg-blue-500/70"></div>
                        <span className="text-slate-500">Progress: {stat.in_progress}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <div className="w-2 h-2 rounded-full bg-emerald-500/70"></div>
                        <span className="text-slate-500">Resolved: {stat.resolved}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <div className="w-2 h-2 rounded-full bg-red-500/70"></div>
                        <span className="text-slate-500">Escalated: {stat.escalated}</span>
                      </div>
                    </div>
                    {stat.forwarded > 0 && (
                      <div className="mt-2 px-2 py-1 bg-purple-500/15 text-purple-400 text-xs rounded-full inline-block mr-1">
                        {stat.forwarded} forwarded
                      </div>
                    )}
                    {stat.waiting_on_customer > 0 && (
                      <div className="mt-2 px-2 py-1 bg-orange-500/15 text-orange-400 text-xs rounded-full inline-block mr-1">
                        {stat.waiting_on_customer} waiting
                      </div>
                    )}
                    {stat.negative_sentiment > 0 && (
                      <div className="mt-2 px-2 py-1 bg-red-500/15 text-red-400 text-xs rounded-full inline-block">
                        {stat.negative_sentiment} negative
                      </div>
                    )}
                  </button>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Middle - Ticket List */}
          <div className="col-span-4">
            {selectedCategory ? (
              <div className="bg-[#111827] rounded-xl border border-white/5 overflow-hidden">
                <div className="bg-white/[0.03] border-b border-white/5 px-4 py-4">
                  <div className="flex items-center gap-2">
                    <CategoryIcon category={selectedCategory} className="w-5 h-5 text-slate-300" />
                    <h2 className="text-lg font-bold text-white">{getCategoryLabel(selectedCategory)} Tickets</h2>
                  </div>
                  <p className="text-slate-500 text-sm">{filteredTickets.length} tickets</p>
                </div>

                {/* Filters */}
                <div className="p-4 border-b border-white/5 space-y-3">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-500" />
                    <input
                      type="text"
                      placeholder="Search tickets..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg text-slate-200 placeholder-slate-500 focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/40 outline-none"
                    />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {["all", "new", "in_progress", "forwarded", "resolved", "escalated", "waiting_on_customer"].map((status) => (
                      <button
                        key={status}
                        onClick={() => setStatusFilter(status)}
                        className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                          statusFilter === status
                            ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
                            : "bg-white/5 text-slate-400 border border-white/5 hover:bg-white/10"
                        }`}
                      >
                        {status.replace(/_/g, " ")}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Ticket List */}
                <div className="max-h-[600px] overflow-y-auto">
                  {loading === "tickets" ? (
                    <div className="p-8 text-center text-slate-500">Loading tickets...</div>
                  ) : filteredTickets.length === 0 ? (
                    <div className="p-8 text-center text-slate-500">No tickets found</div>
                  ) : (
                    <div className="divide-y divide-white/5">
                      {filteredTickets.map((ticket) => (
                        <div
                          key={ticket.ticket_id}
                          onClick={() => handleTicketSelect(ticket)}
                          className={`p-4 cursor-pointer transition-all ${
                            selectedTicket?.ticket_id === ticket.ticket_id
                              ? "bg-indigo-500/10 border-l-4 border-indigo-500"
                              : "hover:bg-white/[0.02]"
                          }`}
                        >
                          <div className="flex items-start justify-between mb-1.5">
                            <span className="font-mono text-base font-semibold text-slate-200">{ticket.ticket_id}</span>
                            <div className="flex items-center gap-1.5">
                              {getSeverityBadge(ticket.severity)}
                              <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                                ticket.status === "new" ? "bg-yellow-500/15 text-yellow-400" :
                                ticket.status === "in_progress" ? "bg-blue-500/15 text-blue-400" :
                                ticket.status === "resolved" ? "bg-emerald-500/15 text-emerald-400" :
                                ticket.status === "waiting_on_customer" ? "bg-orange-500/15 text-orange-400" :
                                ticket.status === "forwarded" ? "bg-purple-500/15 text-purple-400" :
                                "bg-red-500/15 text-red-400"
                              }`}>
                                {ticket.status.replace(/_/g, " ")}
                              </span>
                            </div>
                          </div>
                          <p className="text-slate-300 text-base mb-2 leading-snug">{ticket.subject}</p>
                          <div className="flex items-center gap-2 text-sm">
                            <span className={getSentimentColor(ticketSentiment(ticket))}>
                              {ticketSentiment(ticket)}
                            </span>
                            {ticketConfidence(ticket) != null && (
                              <span className="text-slate-500">
                                {((ticketConfidence(ticket) ?? 0) * 100).toFixed(0)}% conf
                              </span>
                            )}
                            {ticket.priority && (
                              <span className="text-slate-500">{ticket.priority}</span>
                            )}
                            {ticket.assigned_team && (
                              <span className="px-1.5 py-0.5 rounded bg-indigo-500/15 text-indigo-400 text-xs">
                                {ticket.assigned_team}
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="bg-[#111827] rounded-xl border border-white/5 p-12 text-center">
                <Filter className="w-16 h-16 text-slate-600 mx-auto mb-4" />
                <p className="text-slate-500 text-lg">Select a category to view tickets</p>
              </div>
            )}
          </div>

          {/* Right - Ticket Detail */}
          <div className="col-span-5">
            {selectedTicket ? (
              <div className="bg-[#111827] rounded-xl border border-white/5 overflow-hidden flex flex-col" style={{ maxHeight: "calc(100vh - 180px)" }}>
                {/* Header */}
                <div className="bg-gradient-to-r from-indigo-600/20 to-purple-600/20 border-b border-white/5 px-4 py-3 flex-shrink-0">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-lg font-bold text-white">{selectedTicket.ticket_id}</h2>
                      <p className="text-slate-400 text-sm truncate">{selectedTicket.subject}</p>
                    </div>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                      selectedTicket.status === "new" ? "bg-yellow-500/15 text-yellow-400" :
                      selectedTicket.status === "in_progress" ? "bg-blue-500/15 text-blue-400" :
                      selectedTicket.status === "resolved" ? "bg-emerald-500/15 text-emerald-400" :
                      selectedTicket.status === "waiting_on_customer" ? "bg-orange-500/15 text-orange-400" :
                      selectedTicket.status === "forwarded" ? "bg-purple-500/15 text-purple-400" :
                      "bg-red-500/15 text-red-400"
                    }`}>
                      {selectedTicket.status.replace(/_/g, " ")}
                    </span>
                  </div>
                </div>

                {/* Tab bar */}
                <div className="flex border-b border-white/5 flex-shrink-0">
                  {([
                    { key: "details" as const, label: "Details", icon: <Sparkles className="w-3.5 h-3.5" /> },
                    { key: "chat" as const, label: "AI Chat", icon: <MessageSquare className="w-3.5 h-3.5" /> },
                    { key: "conversation" as const, label: "Conversation", icon: <Send className="w-3.5 h-3.5" />, count: conversations.length },
                  ]).map((tab) => (
                    <button
                      key={tab.key}
                      onClick={() => setDetailTab(tab.key)}
                      className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold transition-colors border-b-2 ${
                        detailTab === tab.key
                          ? "border-indigo-500 text-indigo-400"
                          : "border-transparent text-slate-500 hover:text-slate-300"
                      }`}
                    >
                      {tab.icon}
                      {tab.label}
                      {tab.count != null && tab.count > 0 && (
                        <span className="ml-1 px-1.5 py-0.5 rounded-full bg-white/10 text-[10px]">{tab.count}</span>
                      )}
                    </button>
                  ))}
                </div>

                {/* Tab content */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4">

                  {/* === DETAILS TAB === */}
                  {detailTab === "details" && (
                    <>
                      {/* Metadata */}
                      <div className="space-y-3">
                        {selectedTicket.description && (
                          <p className="text-slate-400 text-sm">{selectedTicket.description}</p>
                        )}
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold border ${getCategoryColor(selectedTicket.category)}`}>
                            {getCategoryLabel(selectedTicket.category)}
                          </span>
                          {getSeverityBadge(selectedTicket.severity)}
                          {selectedTicket.priority && (
                            <span className="px-2 py-0.5 rounded text-xs font-medium bg-white/5 text-slate-400">
                              {selectedTicket.priority}
                            </span>
                          )}
                          <select
                            value={selectedTicket.assigned_team || (typeof selectedTicket.ai_analysis?.decision?.assigned_team === "string" ? selectedTicket.ai_analysis.decision.assigned_team : "")}
                            onChange={(e) => assignTicketTeam(selectedTicket.ticket_id, e.target.value)}
                            className="px-2 py-0.5 rounded text-xs font-medium bg-indigo-500/15 text-indigo-400 border border-indigo-500/30 outline-none cursor-pointer appearance-none pr-5 bg-[length:12px] bg-[right_4px_center] bg-no-repeat"
                            style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='%236366f1' viewBox='0 0 16 16'%3E%3Cpath d='M8 11L3 6h10z'/%3E%3C/svg%3E")` }}
                          >
                            <option value="" disabled className="bg-[#111827]">Assign team...</option>
                            <option value="engineering" className="bg-[#111827]">Engineering</option>
                            <option value="api-platform" className="bg-[#111827]">API Platform</option>
                            <option value="security" className="bg-[#111827]">Security</option>
                            <option value="devops" className="bg-[#111827]">DevOps</option>
                            <option value="product" className="bg-[#111827]">Product</option>
                            <option value="general" className="bg-[#111827]">General</option>
                          </select>
                          {selectedTicket.customer?.name && (
                            <span className="text-xs text-slate-500">
                              Customer: {selectedTicket.customer.name}
                              {selectedTicket.customer.company ? ` (${selectedTicket.customer.company})` : ""}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* AI Insights */}
                      {loading === "insights" && (
                        <div className="flex items-center gap-2 text-sm text-slate-500 py-4">
                          <div className="w-4 h-4 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                          Analyzing ticket...
                        </div>
                      )}
                      {insights && (
                        <div className="space-y-3">
                          {insights.summary && (
                            <div className="bg-blue-500/10 rounded-lg p-3 border border-blue-500/20">
                              <h4 className="font-semibold text-blue-300 text-xs mb-1">Summary</h4>
                              <p className="text-blue-200/80 text-sm">{insights.summary}</p>
                            </div>
                          )}
                          {insights.route && (
                            <div className="bg-indigo-500/10 rounded-lg p-3 border border-indigo-500/20">
                              <h4 className="font-semibold text-indigo-300 text-xs mb-1">Routing</h4>
                              <div className="flex flex-wrap items-center gap-2 text-xs">
                                <span className={`px-2 py-0.5 rounded-full font-semibold border ${getCategoryColor(insights.route.category ?? "")}`}>
                                  {getCategoryLabel(insights.route.category ?? "")}
                                </span>
                                {getSeverityBadge(insights.route.severity)}
                                {insights.route.confidence != null && (
                                  <span className="text-slate-400">
                                    {(insights.route.confidence * 100).toFixed(0)}% conf
                                  </span>
                                )}
                              </div>
                            </div>
                          )}
                          {insights.sentiment && (
                            <div className="flex items-center gap-2 text-sm">
                              <span className="font-semibold text-slate-500 text-xs">Sentiment:</span>
                              <span className={`font-bold ${getSentimentColor(insights.sentiment.sentiment || insights.sentiment.label || "")}`}>
                                {insights.sentiment.sentiment || insights.sentiment.label}
                              </span>
                            </div>
                          )}
                          {insights.decision && (
                            <div className={`rounded-lg p-3 border ${
                              insights.decision.action === "auto_resolve" ? "bg-emerald-500/10 border-emerald-500/20" :
                              insights.decision.action === "escalate" ? "bg-red-500/10 border-red-500/20" :
                              "bg-yellow-500/10 border-yellow-500/20"
                            }`}>
                              <div className="flex items-center gap-2 text-xs">
                                <span className="font-semibold text-slate-300">Action:</span>
                                <span className="px-2 py-0.5 bg-white/10 rounded-full font-bold text-slate-200">
                                  {insights.decision.action?.replace(/_/g, " ").toUpperCase()}
                                </span>
                              </div>
                              {insights.decision.reason && (
                                <p className="text-xs text-slate-400 mt-1">{insights.decision.reason}</p>
                              )}
                            </div>
                          )}
                          {insights.solution?.resolution_steps && insights.solution.resolution_steps.length > 0 && (
                            <div className="bg-white/[0.03] rounded-lg p-3 border border-white/5">
                              <h4 className="text-xs font-semibold text-slate-300 mb-1">Resolution Steps:</h4>
                              <ol className="list-decimal list-inside space-y-0.5 text-xs text-slate-400">
                                {insights.solution.resolution_steps.map((step: string, idx: number) => (
                                  <li key={idx}>{step}</li>
                                ))}
                              </ol>
                            </div>
                          )}
                        </div>
                      )}
                    </>
                  )}

                  {/* === AI CHAT TAB === */}
                  {detailTab === "chat" && (
                    <div className="flex flex-col h-full -mt-4 -mx-4">
                      <div className="flex-1 overflow-y-auto p-4 space-y-2">
                        {!insights && (
                          <p className="text-xs text-slate-500 text-center py-8">
                            AI Chat will be available once insights are generated.
                          </p>
                        )}
                        {insights && chatMessages.length === 0 && (
                          <p className="text-xs text-slate-500 text-center py-8">
                            Ask a question about this ticket&hellip;
                          </p>
                        )}
                        {chatMessages.map((msg, idx) => (
                          <div
                            key={idx}
                            className={`text-sm rounded-lg p-2.5 ${
                              msg.role === "user"
                                ? "bg-blue-500/10 border border-blue-500/20 ml-8"
                                : "bg-indigo-500/10 border border-indigo-500/20 mr-8"
                            }`}
                          >
                            <span className="text-xs font-semibold block mb-0.5 text-slate-400">
                              {msg.role === "user" ? "You" : "AI"}
                            </span>
                            <p className="text-slate-300 whitespace-pre-wrap">{msg.content}</p>
                          </div>
                        ))}
                        {chatLoading && (
                          <div className="text-xs text-indigo-400 animate-pulse px-2">AI is thinking...</div>
                        )}
                        <div ref={chatEndRef} />
                      </div>

                      {insights && (
                        <div className="flex gap-2 p-4 border-t border-white/5 bg-[#0d1320] flex-shrink-0">
                          <input
                            type="text"
                            value={chatInput}
                            onChange={(e) => setChatInput(e.target.value)}
                            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendChatMessage()}
                            placeholder="e.g. What similar issues have been reported?"
                            className="flex-1 text-sm px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-slate-200 placeholder-slate-500 focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/40 outline-none"
                            disabled={chatLoading}
                          />
                          <button
                            onClick={sendChatMessage}
                            disabled={chatLoading || !chatInput.trim()}
                            className="px-3 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                          >
                            <Send className="w-4 h-4" />
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {/* === CONVERSATION TAB === */}
                  {detailTab === "conversation" && (
                    <div className="flex flex-col h-full -mt-4 -mx-4">
                      <div className="flex-1 overflow-y-auto p-4 space-y-3">
                        {conversations.length === 0 ? (
                          <p className="text-xs text-slate-500 text-center py-8">No messages yet. Send a reply below.</p>
                        ) : (
                          conversations.map((msg) => (
                            <div
                              key={msg.message_id}
                              className={`rounded-lg p-3 text-sm ${
                                msg.sender === "agent"
                                  ? "bg-blue-500/10 border border-blue-500/20 ml-4"
                                  : msg.sender === "system"
                                  ? "bg-white/[0.03] border border-white/5 mx-8 text-center"
                                  : "bg-white/[0.03] border border-white/5 mr-4"
                              }`}
                            >
                              <div className="flex items-center justify-between mb-1">
                                <span className={`text-xs font-semibold ${
                                  msg.sender === "agent" ? "text-blue-400" :
                                  msg.sender === "system" ? "text-slate-500" :
                                  "text-slate-400"
                                }`}>
                                  {msg.sender === "agent" ? "Agent" : msg.sender === "system" ? "System" : "Customer"}
                                </span>
                                <span className="text-xs text-slate-500">
                                  {new Date(msg.created_at).toLocaleTimeString()}
                                </span>
                              </div>
                              <p className={`whitespace-pre-wrap ${msg.sender === "system" ? "text-xs text-slate-500 italic" : "text-slate-300"}`}>
                                {msg.body}
                              </p>
                              {msg.email_status === "simulated" && (
                                <span className="text-xs text-slate-500 mt-1 inline-block">simulated</span>
                              )}
                            </div>
                          ))
                        )}
                        <div ref={conversationEndRef} />
                      </div>

                      {/* Reply composer inside conversation tab */}
                      {selectedTicket.status !== "resolved" && (
                        <div className="flex-shrink-0 border-t border-white/5 p-4 bg-[#0d1320] space-y-3">
                          <div>
                            <div className="flex items-center justify-between mb-1">
                              <label className="text-xs font-semibold text-slate-400">Reply to customer</label>
                              {insights?.solution?.draft_reply && !replyText && (
                                <button
                                  onClick={() => setReplyText(insights.solution?.draft_reply || "")}
                                  className="text-xs text-indigo-400 hover:text-indigo-300 font-medium"
                                >
                                  Use AI draft
                                </button>
                              )}
                            </div>
                            <textarea
                              value={replyText}
                              onChange={(e) => setReplyText(e.target.value)}
                              placeholder="Type your reply..."
                              rows={3}
                              className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/40 outline-none resize-none"
                            />
                          </div>
                          <button
                            onClick={sendReply}
                            disabled={sendingReply || !replyText.trim()}
                            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-semibold text-sm"
                          >
                            <Send className="w-4 h-4" />
                            {sendingReply ? "Sending..." : "Send Reply"}
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Actions — always pinned at bottom */}
                {selectedTicket.status !== "resolved" ? (
                  <div className="flex-shrink-0 border-t border-white/5 bg-[#0d1320]">
                    {/* Forward form (expandable) */}
                    {showForwardForm && (
                      <div className="p-3 border-b border-white/5 space-y-2">
                        <div className="flex items-center gap-2">
                          <select
                            value={forwardTeam}
                            onChange={(e) => setForwardTeam(e.target.value)}
                            className="flex-1 px-2 py-1.5 bg-white/5 border border-white/10 rounded-lg text-sm text-slate-200 outline-none"
                          >
                            <option value="" disabled className="bg-[#111827]">Select team...</option>
                            <option value="engineering" className="bg-[#111827]">Engineering</option>
                            <option value="api-platform" className="bg-[#111827]">API Platform</option>
                            <option value="security" className="bg-[#111827]">Security</option>
                            <option value="devops" className="bg-[#111827]">DevOps</option>
                            <option value="product" className="bg-[#111827]">Product</option>
                          </select>
                          <button
                            onClick={forwardTicket}
                            disabled={!forwardTeam || forwarding}
                            className="px-3 py-1.5 bg-amber-600 text-white rounded-lg text-sm font-semibold hover:bg-amber-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                          >
                            {forwarding ? "Forwarding..." : "Forward"}
                          </button>
                          <button
                            onClick={() => { setShowForwardForm(false); setForwardTeam(""); setForwardNote(""); }}
                            className="px-2 py-1.5 text-slate-400 hover:text-slate-200 text-sm"
                          >
                            Cancel
                          </button>
                        </div>
                        <textarea
                          value={forwardNote}
                          onChange={(e) => setForwardNote(e.target.value)}
                          placeholder="Internal note for the team (optional)..."
                          rows={2}
                          className="w-full px-2 py-1.5 bg-white/5 border border-white/10 rounded-lg text-sm text-slate-200 placeholder-slate-500 outline-none resize-none"
                        />
                      </div>
                    )}
                    {/* Action buttons */}
                    <div className="p-3 flex gap-2">
                      <button
                        onClick={handleCloseTicket}
                        disabled={closingTicket}
                        className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-semibold text-sm"
                      >
                        <CheckCircle className="w-4 h-4" />
                        {closingTicket ? "Closing..." : "Close Ticket"}
                      </button>
                      <button
                        onClick={() => setShowForwardForm(!showForwardForm)}
                        className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg transition-colors font-semibold text-sm ${
                          showForwardForm
                            ? "bg-amber-600 text-white"
                            : "bg-amber-600/80 text-white hover:bg-amber-500"
                        }`}
                      >
                        <Send className="w-4 h-4" />
                        Forward
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex-shrink-0 border-t border-emerald-500/20 bg-emerald-500/10 p-4 text-center">
                    <div className="flex items-center justify-center gap-2 text-emerald-400 font-semibold">
                      <CheckCircle className="w-5 h-5" />
                      Ticket Resolved
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="bg-[#111827] rounded-xl border border-white/5 p-12 text-center">
                <Clock className="w-16 h-16 text-slate-600 mx-auto mb-4" />
                <p className="text-slate-500 text-lg">Select a ticket to view details</p>
              </div>
            )}
          </div>
        </div>
      </div>
      <DebugPanel wsStatus={wsStatus} logs={logs} />
    </div>
  );
}
