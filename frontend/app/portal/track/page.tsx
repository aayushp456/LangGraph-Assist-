'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Search, Mail, Loader2, AlertCircle, Ticket } from 'lucide-react';

interface TicketSummary {
  ticket_id: string;
  subject: string;
  status: string;
  priority: string;
  created_at: string;
  updated_at: string;
}

export default function TrackTicket() {
  const router = useRouter();
  const [searchType, setSearchType] = useState<'id' | 'email'>('id');
  const [searchValue, setSearchValue] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState('');
  const [tickets, setTickets] = useState<TicketSummary[]>([]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSearching(true);
    setTickets([]);

    try {
      let url = '';
      if (searchType === 'id') {
        url = `http://localhost:8000/api/public/tickets/${encodeURIComponent(searchValue)}`;
      } else {
        url = `http://localhost:8000/api/public/tickets/by-email/${encodeURIComponent(searchValue)}`;
      }

      const response = await fetch(url);

      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('No tickets found');
        }
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to fetch tickets');
      }

      const data = await response.json();

      if (searchType === 'id') {
        // Single ticket response
        setTickets([data]);
      } else {
        // Multiple tickets response
        if (data.tickets.length === 0) {
          throw new Error('No tickets found for this email address');
        }
        setTickets(data.tickets);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred while searching');
    } finally {
      setIsSearching(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'new':
        return 'bg-blue-500/15 text-blue-400';
      case 'open':
        return 'bg-amber-500/15 text-amber-400';
      case 'in_progress':
        return 'bg-purple-500/15 text-purple-400';
      case 'waiting_on_customer':
        return 'bg-orange-500/15 text-orange-400';
      case 'resolved':
        return 'bg-green-500/15 text-green-400';
      case 'closed':
        return 'bg-slate-500/15 text-slate-400';
      default:
        return 'bg-slate-500/15 text-slate-400';
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority.toLowerCase()) {
      case 'critical':
        return 'bg-red-500/15 text-red-400';
      case 'high':
        return 'bg-orange-500/15 text-orange-400';
      case 'medium':
        return 'bg-yellow-500/15 text-yellow-400';
      case 'low':
        return 'bg-emerald-500/15 text-emerald-400';
      default:
        return 'bg-slate-500/15 text-slate-400';
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="max-w-5xl mx-auto">
      <div className="bg-[#111827] rounded-xl border border-white/5 p-10">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-3">Track Support Request</h1>
          <p className="text-slate-400 leading-relaxed">
            Retrieve your support request status using your ticket reference number or registered email address.
          </p>
        </div>

        {/* Search Type Toggle */}
        <div className="grid grid-cols-2 gap-3 mb-8">
          <button
            onClick={() => {
              setSearchType('id');
              setSearchValue('');
              setError('');
              setTickets([]);
            }}
            className={`px-6 py-4 rounded-lg font-semibold transition-all ${
              searchType === 'id'
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'bg-white/5 text-slate-300 hover:bg-white/10'
            }`}
          >
            <Ticket className="h-5 w-5 inline mr-2" />
            By Ticket ID
          </button>
          <button
            onClick={() => {
              setSearchType('email');
              setSearchValue('');
              setError('');
              setTickets([]);
            }}
            className={`px-6 py-4 rounded-lg font-semibold transition-all ${
              searchType === 'email'
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'bg-white/5 text-slate-300 hover:bg-white/10'
            }`}
          >
            <Mail className="h-5 w-5 inline mr-2" />
            By Email Address
          </button>
        </div>

        {/* Search Form */}
        <form onSubmit={handleSearch} className="mb-8">
          <div className="flex gap-3">
            <input
              type={searchType === 'email' ? 'email' : 'text'}
              value={searchValue}
              onChange={(e) => setSearchValue(e.target.value)}
              placeholder={
                searchType === 'id'
                  ? 'Enter ticket reference (e.g., TKT-20260322-abc123)'
                  : 'Enter your registered email address'
              }
              required
              className="flex-1 px-5 py-4 bg-white/5 border border-white/10 rounded-lg text-slate-200 placeholder-slate-500 focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/40 outline-none text-lg transition-all"
            />
            <button
              type="submit"
              disabled={isSearching}
              className="px-8 py-4 bg-indigo-600 text-white rounded-lg hover:bg-indigo-500 transition-all font-semibold disabled:opacity-50 disabled:cursor-not-allowed flex items-center shadow-sm"
            >
              {isSearching ? (
                <>
                  <Loader2 className="animate-spin h-5 w-5 mr-2" />
                  Searching...
                </>
              ) : (
                <>
                  <Search className="h-5 w-5 mr-2" />
                  Search
                </>
              )}
            </button>
          </div>
        </form>

        {/* Error Message */}
        {error && (
          <div className="mb-8 bg-red-500/15 border border-red-500/20 rounded-lg p-4 flex items-start">
            <AlertCircle className="h-5 w-5 text-red-400 mr-3 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-300 font-medium">{error}</p>
          </div>
        )}

        {/* Results */}
        {tickets.length > 0 && (
          <div className="space-y-4">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold text-white">
                {tickets.length === 1 ? 'Request Found' : `${tickets.length} Requests Found`}
              </h2>
              <span className="text-sm text-slate-500">
                {tickets.length} {tickets.length === 1 ? 'result' : 'results'}
              </span>
            </div>
            {tickets.map((ticket) => (
              <div
                key={ticket.ticket_id}
                onClick={() => router.push(`/portal/ticket/${ticket.ticket_id}`)}
                className="border border-white/5 rounded-xl p-6 hover:border-white/10 transition-all cursor-pointer bg-white/[0.03]"
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold text-white mb-2">
                      {ticket.subject}
                    </h3>
                    <p className="text-sm text-slate-500 font-mono bg-white/5 inline-block px-3 py-1 rounded">{ticket.ticket_id}</p>
                  </div>
                  <div className="flex flex-col items-end gap-2 ml-4">
                    <span
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wide ${getStatusColor(
                        ticket.status
                      )}`}
                    >
                      {ticket.status.replace('_', ' ')}
                    </span>
                    <span
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wide ${getPriorityColor(
                        ticket.priority
                      )}`}
                    >
                      {ticket.priority}
                    </span>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4 text-sm text-slate-400 pt-4 border-t border-white/5">
                  <div>
                    <span className="font-medium text-slate-300">Created:</span> {formatDate(ticket.created_at)}
                  </div>
                  <div className="text-right">
                    <span className="font-medium text-slate-300">Last Updated:</span> {formatDate(ticket.updated_at)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
