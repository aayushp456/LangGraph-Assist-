'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { CheckCircle, AlertCircle, Loader2 } from 'lucide-react';

export default function SubmitTicket() {
  const router = useRouter();
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    subject: '',
    description: '',
    priority: 'medium',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState<{ ticketId: string; message: string } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);

    try {
      const response = await fetch('http://localhost:8000/api/public/tickets', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to submit ticket');
      }

      const data = await response.json();
      setSuccess({
        ticketId: data.ticket_id,
        message: data.message,
      });

      // Reset form
      setFormData({
        name: '',
        email: '',
        subject: '',
        description: '',
        priority: 'medium',
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred while submitting your ticket');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  if (success) {
    return (
      <div className="max-w-2xl mx-auto">
        <div className="bg-[#111827] rounded-xl border border-white/5 p-10">
          <div className="flex items-center justify-center w-20 h-20 bg-green-500/15 rounded-xl mx-auto mb-6">
            <CheckCircle className="h-10 w-10 text-green-400" />
          </div>
          <h2 className="text-3xl font-bold text-center text-white mb-4">
            Request Submitted Successfully
          </h2>
          <p className="text-center text-slate-400 mb-8 max-w-md mx-auto">
            Your support request has been received and assigned to our technical team.
          </p>
          <div className="bg-white/[0.03] border border-white/5 rounded-xl p-6 mb-8">
            <p className="text-sm font-semibold text-slate-300 mb-3 text-center">Ticket Reference Number</p>
            <p className="text-3xl font-mono font-bold text-white text-center tracking-tight">
              {success.ticketId}
            </p>
            <p className="text-xs text-slate-500 text-center mt-3">
              Please save this reference number for tracking purposes
            </p>
          </div>
          <div className="bg-indigo-500/15 border border-indigo-500/20 rounded-lg p-4 mb-8">
            <p className="text-sm text-indigo-300 text-center">
              <strong>Next Steps:</strong> Our team will review your request and respond within 4 business hours.
              You will receive email notifications for all updates.
            </p>
          </div>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <button
              onClick={() => router.push(`/portal/ticket/${success.ticketId}`)}
              className="px-8 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-500 transition-all font-semibold shadow-sm"
            >
              View Ticket Details
            </button>
            <button
              onClick={() => setSuccess(null)}
              className="px-8 py-3 bg-white/5 text-slate-300 border border-white/10 rounded-lg hover:bg-white/10 transition-all font-semibold"
            >
              Submit Another Request
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto">
      <div className="bg-[#111827] rounded-xl border border-white/5 p-10">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-3">Submit Support Request</h1>
          <p className="text-slate-400 leading-relaxed">
            Our technical support team will review your request and respond within our service level agreement timeframe.
          </p>
        </div>

        {error && (
          <div className="mb-8 bg-red-500/15 border border-red-500/20 rounded-lg p-4 flex items-start">
            <AlertCircle className="h-5 w-5 text-red-400 mr-3 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-300 font-medium">{error}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid md:grid-cols-2 gap-6">
            {/* Name */}
            <div>
              <label htmlFor="name" className="block text-sm font-semibold text-white mb-2">
                Full Name <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                id="name"
                name="name"
                required
                value={formData.name}
                onChange={handleChange}
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-slate-200 placeholder-slate-500 focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/40 outline-none transition-all"
                placeholder="John Doe"
              />
            </div>

            {/* Email */}
            <div>
              <label htmlFor="email" className="block text-sm font-semibold text-white mb-2">
                Email Address <span className="text-red-400">*</span>
              </label>
              <input
                type="email"
                id="email"
                name="email"
                required
                value={formData.email}
                onChange={handleChange}
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-slate-200 placeholder-slate-500 focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/40 outline-none transition-all"
                placeholder="john.doe@company.com"
              />
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            {/* Subject */}
            <div className="md:col-span-1">
              <label htmlFor="subject" className="block text-sm font-semibold text-white mb-2">
                Subject <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                id="subject"
                name="subject"
                required
                value={formData.subject}
                onChange={handleChange}
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-slate-200 placeholder-slate-500 focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/40 outline-none transition-all"
                placeholder="Brief summary of the issue"
              />
            </div>

            {/* Priority */}
            <div>
              <label htmlFor="priority" className="block text-sm font-semibold text-white mb-2">
                Priority Level
              </label>
              <select
                id="priority"
                name="priority"
                value={formData.priority}
                onChange={handleChange}
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-slate-200 focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/40 outline-none transition-all"
              >
                <option value="low" className="bg-[#111827]">Low - General inquiry</option>
                <option value="medium" className="bg-[#111827]">Medium - Standard issue</option>
                <option value="high" className="bg-[#111827]">High - Business impact</option>
                <option value="critical" className="bg-[#111827]">Critical - Service down</option>
              </select>
            </div>
          </div>

          {/* Description */}
          <div>
            <label htmlFor="description" className="block text-sm font-semibold text-white mb-2">
              Detailed Description <span className="text-red-400">*</span>
            </label>
            <textarea
              id="description"
              name="description"
              required
              value={formData.description}
              onChange={handleChange}
              rows={8}
              className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-slate-200 placeholder-slate-500 focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/40 outline-none resize-none transition-all"
              placeholder="Please provide detailed information about your issue including:
• Steps to reproduce
• Expected vs actual behavior
• Error messages (if any)
• Environment details"
            />
          </div>

          {/* Submit Button */}
          <div className="pt-4">
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full px-6 py-4 bg-indigo-600 text-white rounded-lg hover:bg-indigo-500 transition-all font-semibold disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center shadow-sm"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="animate-spin h-5 w-5 mr-2" />
                  Submitting Request...
                </>
              ) : (
                'Submit Support Request'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
