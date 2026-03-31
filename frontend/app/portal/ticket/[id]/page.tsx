'use client';

import { useState, useEffect, useRef } from 'react';
import { useParams } from 'next/navigation';
import { Send, Loader2, AlertCircle, ArrowLeft, User, Headset } from 'lucide-react';
import Link from 'next/link';

interface Message {
  message_id: string;
  sender: string;
  body: string;
  created_at: string;
}

interface TicketDetail {
  ticket_id: string;
  subject: string;
  description: string;
  status: string;
  priority: string;
  customer_name: string;
  customer_email: string;
  created_at: string;
  updated_at: string;
  conversation: Message[];
}

export default function TicketDetailPage() {
  const params = useParams();
  const ticketId = params.id as string;

  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [messageText, setMessageText] = useState('');
  const [isSending, setIsSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Fetch ticket details
  useEffect(() => {
    const fetchTicket = async () => {
      try {
        const response = await fetch(`http://localhost:8000/api/public/tickets/${ticketId}`);

        if (!response.ok) {
          if (response.status === 404) {
            throw new Error('Ticket not found');
          }
          throw new Error('Failed to load ticket');
        }

        const data = await response.json();
        setTicket(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load ticket');
      } finally {
        setIsLoading(false);
      }
    };

    fetchTicket();
  }, [ticketId]);

  // WebSocket connection for real-time updates
  useEffect(() => {
    const websocket = new WebSocket(`ws://localhost:8000/ws/${ticketId}`);

    websocket.onopen = () => {
      console.log('WebSocket connected');
      // Subscribe to ticket events
      websocket.send(JSON.stringify({
        action: 'subscribe',
        event_type: 'agent:message'
      }));
    };

    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data);

      // Handle agent messages
      if (data.type === 'agent:message' && data.payload.ticket_id === ticketId) {
        const newMessage = data.payload.message;
        setTicket((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            conversation: [...prev.conversation, {
              message_id: newMessage.message_id,
              sender: 'Support Team',
              body: newMessage.body,
              created_at: newMessage.created_at,
            }],
          };
        });
      }

      // Handle ticket updates
      if (data.type === 'ticket:updated' && data.payload.ticket_id === ticketId) {
        if (data.payload.updates.status) {
          setTicket((prev) => {
            if (!prev) return prev;
            return {
              ...prev,
              status: data.payload.updates.status,
            };
          });
        }
      }
    };

    websocket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    websocket.onclose = () => {
      console.log('WebSocket disconnected');
    };

    return () => {
      websocket.close();
    };
  }, [ticketId]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [ticket?.conversation]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!messageText.trim() || isSending) return;

    setIsSending(true);

    try {
      const response = await fetch(`http://localhost:8000/api/public/tickets/${ticketId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          body: messageText,
          sender_name: ticket?.customer_name,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to send message');
      }

      const data = await response.json();

      // Add message to conversation
      setTicket((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          conversation: [...prev.conversation, {
            message_id: data.message_id,
            sender: 'You',
            body: messageText,
            created_at: data.created_at,
          }],
        };
      });

      setMessageText('');
    } catch (err) {
      console.error('Failed to send message:', err);
      alert('Failed to send message. Please try again.');
    } finally {
      setIsSending(false);
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

  if (isLoading) {
    return (
      <div className="max-w-6xl mx-auto">
        <div className="bg-[#111827] rounded-xl border border-white/5 p-12 flex items-center justify-center">
          <Loader2 className="animate-spin h-8 w-8 text-indigo-400 mr-3" />
          <span className="text-slate-400 font-medium">Loading ticket details...</span>
        </div>
      </div>
    );
  }

  if (error || !ticket) {
    return (
      <div className="max-w-6xl mx-auto">
        <div className="bg-[#111827] rounded-xl border border-white/5 p-10">
          <div className="flex items-start mb-8">
            <AlertCircle className="h-6 w-6 text-red-400 mr-3 flex-shrink-0 mt-0.5" />
            <div>
              <h2 className="text-2xl font-semibold text-white mb-2">Request Not Found</h2>
              <p className="text-slate-400">{error || 'The requested ticket could not be found in our system.'}</p>
            </div>
          </div>
          <Link
            href="/portal/track"
            className="inline-flex items-center text-indigo-400 hover:text-indigo-300 font-medium"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Return to Search
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Back Button */}
      <Link
        href="/portal/track"
        className="inline-flex items-center text-slate-400 hover:text-white mb-6 font-medium"
      >
        <ArrowLeft className="h-4 w-4 mr-2" />
        Back to Search
      </Link>

      {/* Ticket Header */}
      <div className="bg-[#111827] rounded-xl border border-white/5 p-8 mb-6">
        <div className="flex items-start justify-between mb-6">
          <div className="flex-1">
            <h1 className="text-3xl font-bold text-white mb-3">{ticket.subject}</h1>
            <p className="text-sm text-slate-500 font-mono bg-white/5 inline-block px-3 py-1.5 rounded">{ticket.ticket_id}</p>
          </div>
          <div className="flex flex-col items-end gap-2 ml-6">
            <span className={`px-4 py-2 rounded-lg text-xs font-semibold uppercase tracking-wide ${getStatusColor(ticket.status)}`}>
              {ticket.status.replace('_', ' ')}
            </span>
            <span className={`px-4 py-2 rounded-lg text-xs font-semibold uppercase tracking-wide ${getPriorityColor(ticket.priority)}`}>
              {ticket.priority}
            </span>
          </div>
        </div>

        <div className="border-t border-white/5 pt-6">
          <div className="grid grid-cols-2 gap-6 text-sm mb-6">
            <div>
              <span className="text-slate-500 font-medium">Created:</span>
              <span className="ml-2 text-white">{formatDate(ticket.created_at)}</span>
            </div>
            <div>
              <span className="text-slate-500 font-medium">Last Updated:</span>
              <span className="ml-2 text-white">{formatDate(ticket.updated_at)}</span>
            </div>
          </div>
        </div>

        <div className="bg-white/[0.03] border border-white/5 rounded-lg p-6">
          <p className="text-sm font-semibold text-white mb-3 uppercase tracking-wide">Original Request</p>
          <p className="text-slate-300 whitespace-pre-wrap leading-relaxed">{ticket.description}</p>
        </div>
      </div>

      {/* Conversation */}
      <div className="bg-[#111827] rounded-xl border border-white/5 overflow-hidden">
        <div className="bg-gradient-to-r from-indigo-600/20 to-purple-600/20 px-8 py-5 border-b border-white/5">
          <h2 className="text-lg font-semibold text-white">Support Conversation</h2>
          <p className="text-sm text-slate-400 mt-1">Real-time communication with our technical team</p>
        </div>

        {/* Messages */}
        <div className="h-[500px] overflow-y-auto p-8 space-y-6 bg-white/[0.03]">
          {ticket.conversation.map((message) => {
            const isCustomer = message.sender === 'You';
            return (
              <div
                key={message.message_id}
                className={`flex ${isCustomer ? 'justify-end' : 'justify-start'}`}
              >
                <div className={`flex max-w-[70%] ${isCustomer ? 'flex-row-reverse' : 'flex-row'}`}>
                  <div className={`flex-shrink-0 ${isCustomer ? 'ml-4' : 'mr-4'}`}>
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center shadow-sm ${
                      isCustomer ? 'bg-indigo-600' : 'bg-white/10 border border-white/10'
                    }`}>
                      {isCustomer ? (
                        <User className="h-5 w-5 text-white" />
                      ) : (
                        <Headset className="h-5 w-5 text-slate-300" />
                      )}
                    </div>
                  </div>
                  <div className="flex-1">
                    <div className={`rounded-xl px-5 py-3 shadow-sm ${
                      isCustomer
                        ? 'bg-indigo-600 text-white'
                        : 'bg-[#111827] text-slate-200 border border-white/10'
                    }`}>
                      <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.body}</p>
                    </div>
                    <p className={`text-xs text-slate-500 mt-2 font-medium ${isCustomer ? 'text-right' : 'text-left'}`}>
                      {formatDate(message.created_at)}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
          <div ref={messagesEndRef} />
        </div>

        {/* Message Input */}
        <div className="border-t border-white/5 p-6 bg-[#111827]">
          <form onSubmit={handleSendMessage} className="flex gap-3">
            <input
              type="text"
              value={messageText}
              onChange={(e) => setMessageText(e.target.value)}
              placeholder="Type your message to our support team..."
              disabled={isSending}
              className="flex-1 px-5 py-3 bg-white/5 border border-white/10 rounded-lg text-slate-200 placeholder-slate-500 focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/40 outline-none disabled:opacity-50 transition-all"
            />
            <button
              type="submit"
              disabled={isSending || !messageText.trim()}
              className="px-8 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-500 transition-all font-semibold disabled:opacity-50 disabled:cursor-not-allowed flex items-center shadow-sm"
            >
              {isSending ? (
                <Loader2 className="animate-spin h-5 w-5" />
              ) : (
                <>
                  <Send className="h-5 w-5 mr-2" />
                  Send Message
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
