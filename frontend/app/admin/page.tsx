"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Users, Plus, Trash2, Edit2, Shield, BookOpen, LogOut, X, Check } from "lucide-react";
import { useAuth, getAuthToken } from "@/hooks/useAuth";
import { fetchWithTimeout, getApiUrl } from "@/lib/runtime-config";

interface UserRecord {
  user_id: string;
  email: string;
  name: string;
  role: string;
  team: string | null;
  created_at: string;
}

const TEAMS = ["general", "engineering", "api-platform", "security", "devops", "product"];
const ROLES = ["agent", "admin"];

function authHeaders(): Record<string, string> {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}`, "Content-Type": "application/json" } : { "Content-Type": "application/json" };
}

export default function AdminPage() {
  const router = useRouter();
  const { user, loading: authLoading, logout } = useAuth();

  const [users, setUsers] = useState<UserRecord[]>([]);
  const [filterRole, setFilterRole] = useState<string>("all");
  const [loadingUsers, setLoadingUsers] = useState(false);

  // Create agent form
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newName, setNewName] = useState("");
  const [newRole, setNewRole] = useState("agent");
  const [newTeam, setNewTeam] = useState("general");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  // Edit state
  const [editingUser, setEditingUser] = useState<string | null>(null);
  const [editTeam, setEditTeam] = useState("");
  const [editRole, setEditRole] = useState("");

  // Auth guard
  useEffect(() => {
    if (authLoading) return;
    if (!user || user.role !== "admin") {
      router.push("/login");
    }
  }, [user, authLoading, router]);

  const fetchUsers = useCallback(async () => {
    setLoadingUsers(true);
    try {
      const params = filterRole !== "all" ? `?role=${filterRole}` : "";
      const res = await fetchWithTimeout(
        `${getApiUrl()}/api/admin/users${params}`,
        { headers: authHeaders() },
        10000,
      );
      const data = await res.json();
      setUsers(data.users || []);
    } catch {
      console.error("Failed to fetch users");
    } finally {
      setLoadingUsers(false);
    }
  }, [filterRole]);

  useEffect(() => {
    if (user?.role === "admin") fetchUsers();
  }, [user, fetchUsers]);

  const handleCreateAgent = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setCreating(true);
    try {
      const res = await fetchWithTimeout(
        `${getApiUrl()}/api/admin/users`,
        {
          method: "POST",
          headers: authHeaders(),
          body: JSON.stringify({ email: newEmail, password: newPassword, name: newName, role: newRole, team: newTeam }),
        },
        10000,
      );
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Failed to create user");
      }
      setShowCreateForm(false);
      setNewEmail(""); setNewPassword(""); setNewName(""); setNewRole("agent"); setNewTeam("general");
      fetchUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setCreating(false);
    }
  };

  const handleUpdateUser = async (userId: string) => {
    try {
      const body: Record<string, string> = {};
      if (editRole) body.role = editRole;
      if (editTeam) body.team = editTeam;
      await fetchWithTimeout(
        `${getApiUrl()}/api/admin/users/${userId}`,
        { method: "PATCH", headers: authHeaders(), body: JSON.stringify(body) },
        10000,
      );
      setEditingUser(null);
      fetchUsers();
    } catch {
      console.error("Update failed");
    }
  };

  const handleDeleteUser = async (userId: string, email: string) => {
    if (!confirm(`Delete user ${email}? This cannot be undone.`)) return;
    try {
      await fetchWithTimeout(
        `${getApiUrl()}/api/admin/users/${userId}`,
        { method: "DELETE", headers: authHeaders() },
        10000,
      );
      fetchUsers();
    } catch {
      console.error("Delete failed");
    }
  };

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
        <div className="max-w-6xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">Admin Panel</h1>
              <p className="text-sm text-slate-500 mt-0.5">Manage agents, teams & access</p>
            </div>
            <div className="flex items-center gap-3">
              <Link
                href="/dashboard"
                className="px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-sm text-slate-300 hover:text-white transition-colors"
              >
                Dashboard
              </Link>
              <Link
                href="/knowledge-base"
                className="flex items-center gap-2 px-3 py-1.5 bg-indigo-500/10 border border-indigo-500/20 rounded-lg hover:border-indigo-500/40 transition-colors"
              >
                <BookOpen className="w-4 h-4 text-indigo-400" />
                <span className="text-sm font-medium text-indigo-300">Knowledge Base</span>
              </Link>
              <div className="flex items-center gap-2 px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg">
                <Shield className="w-4 h-4 text-amber-400" />
                <span className="text-sm text-slate-300">{user.name}</span>
              </div>
              <button
                onClick={() => { logout(); router.push("/login"); }}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-slate-400 hover:text-white hover:border-red-500/30 transition-colors"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Stats */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          {[
            { label: "Total Users", count: users.length, color: "text-white" },
            { label: "Agents", count: users.filter(u => u.role === "agent").length, color: "text-indigo-400" },
            { label: "Admins", count: users.filter(u => u.role === "admin").length, color: "text-amber-400" },
            { label: "Customers", count: users.filter(u => u.role === "customer").length, color: "text-emerald-400" },
          ].map((stat) => (
            <div key={stat.label} className="bg-[#111827] rounded-xl border border-white/5 p-5">
              <p className="text-xs text-slate-500 uppercase tracking-wider">{stat.label}</p>
              <p className={`text-3xl font-bold mt-1 ${stat.color}`}>{stat.count}</p>
            </div>
          ))}
        </div>

        {/* Actions bar */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5 text-slate-400" />
            <h2 className="text-lg font-semibold text-white">User Management</h2>
          </div>
          <div className="flex items-center gap-3">
            {/* Role filter */}
            <select
              value={filterRole}
              onChange={(e) => setFilterRole(e.target.value)}
              className="px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-sm text-slate-200 outline-none"
            >
              <option value="all" className="bg-[#111827]">All Roles</option>
              <option value="agent" className="bg-[#111827]">Agents</option>
              <option value="admin" className="bg-[#111827]">Admins</option>
              <option value="customer" className="bg-[#111827]">Customers</option>
            </select>
            <button
              onClick={() => setShowCreateForm(true)}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-500 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Add Agent
            </button>
          </div>
        </div>

        {/* Create form */}
        {showCreateForm && (
          <div className="bg-[#111827] rounded-xl border border-indigo-500/20 p-6 mb-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-white">Create New Agent</h3>
              <button onClick={() => setShowCreateForm(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            {error && (
              <div className="px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm mb-4">
                {error}
              </div>
            )}
            <form onSubmit={handleCreateAgent} className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1">Name</label>
                <input
                  type="text" value={newName} onChange={(e) => setNewName(e.target.value)} required
                  className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-slate-200 placeholder-slate-500 outline-none focus:ring-2 focus:ring-indigo-500/40"
                  placeholder="Agent name"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1">Email</label>
                <input
                  type="email" value={newEmail} onChange={(e) => setNewEmail(e.target.value)} required
                  className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-slate-200 placeholder-slate-500 outline-none focus:ring-2 focus:ring-indigo-500/40"
                  placeholder="agent@company.com"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1">Password</label>
                <input
                  type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required minLength={6}
                  className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-slate-200 placeholder-slate-500 outline-none focus:ring-2 focus:ring-indigo-500/40"
                  placeholder="Min 6 characters"
                />
              </div>
              <div className="flex gap-4">
                <div className="flex-1">
                  <label className="block text-xs font-semibold text-slate-400 mb-1">Role</label>
                  <select value={newRole} onChange={(e) => setNewRole(e.target.value)}
                    className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-slate-200 outline-none">
                    {ROLES.map(r => <option key={r} value={r} className="bg-[#111827]">{r}</option>)}
                  </select>
                </div>
                <div className="flex-1">
                  <label className="block text-xs font-semibold text-slate-400 mb-1">Team</label>
                  <select value={newTeam} onChange={(e) => setNewTeam(e.target.value)}
                    className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-slate-200 outline-none">
                    {TEAMS.map(t => <option key={t} value={t} className="bg-[#111827]">{t}</option>)}
                  </select>
                </div>
              </div>
              <div className="col-span-2">
                <button type="submit" disabled={creating}
                  className="px-6 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-500 disabled:opacity-50 transition-colors">
                  {creating ? "Creating..." : "Create Agent"}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Users table */}
        <div className="bg-[#111827] rounded-xl border border-white/5 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/5">
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">User</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Role</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Team</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Created</th>
                <th className="px-6 py-3 text-right text-xs font-semibold text-slate-400 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {loadingUsers ? (
                <tr><td colSpan={5} className="px-6 py-8 text-center text-slate-500">Loading...</td></tr>
              ) : users.length === 0 ? (
                <tr><td colSpan={5} className="px-6 py-8 text-center text-slate-500">No users found</td></tr>
              ) : (
                users.map((u) => (
                  <tr key={u.user_id} className="hover:bg-white/[0.02]">
                    <td className="px-6 py-4">
                      <div className="text-sm font-medium text-slate-200">{u.name}</div>
                      <div className="text-xs text-slate-500">{u.email}</div>
                    </td>
                    <td className="px-6 py-4">
                      {editingUser === u.user_id ? (
                        <select value={editRole} onChange={(e) => setEditRole(e.target.value)}
                          className="px-2 py-1 bg-white/5 border border-white/10 rounded text-xs text-slate-200 outline-none">
                          {["agent", "admin", "customer"].map(r => <option key={r} value={r} className="bg-[#111827]">{r}</option>)}
                        </select>
                      ) : (
                        <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                          u.role === "admin" ? "bg-amber-500/15 text-amber-400" :
                          u.role === "agent" ? "bg-indigo-500/15 text-indigo-400" :
                          "bg-emerald-500/15 text-emerald-400"
                        }`}>
                          {u.role}
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      {editingUser === u.user_id ? (
                        <select value={editTeam} onChange={(e) => setEditTeam(e.target.value)}
                          className="px-2 py-1 bg-white/5 border border-white/10 rounded text-xs text-slate-200 outline-none">
                          <option value="" className="bg-[#111827]">None</option>
                          {TEAMS.map(t => <option key={t} value={t} className="bg-[#111827]">{t}</option>)}
                        </select>
                      ) : (
                        <span className="text-sm text-slate-400">{u.team || "—"}</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-500">
                      {u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"}
                    </td>
                    <td className="px-6 py-4 text-right">
                      {editingUser === u.user_id ? (
                        <div className="flex items-center justify-end gap-2">
                          <button onClick={() => handleUpdateUser(u.user_id)}
                            className="p-1.5 rounded bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25 transition-colors">
                            <Check className="w-4 h-4" />
                          </button>
                          <button onClick={() => setEditingUser(null)}
                            className="p-1.5 rounded bg-white/5 text-slate-400 hover:text-white transition-colors">
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => { setEditingUser(u.user_id); setEditRole(u.role); setEditTeam(u.team || ""); }}
                            className="p-1.5 rounded bg-white/5 text-slate-400 hover:text-indigo-400 transition-colors"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDeleteUser(u.user_id, u.email)}
                            className="p-1.5 rounded bg-white/5 text-slate-400 hover:text-red-400 transition-colors"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
