import Link from 'next/link';
import { FileText, Search, Zap, Shield } from 'lucide-react';

export default function PortalHome() {
  return (
    <div className="max-w-6xl mx-auto">
      {/* Hero Section */}
      <div className="text-center mb-16">
        <h1 className="text-5xl font-bold text-white mb-6 tracking-tight">
          Humanitarians AI Support Portal
        </h1>
        <p className="text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed">
          AI-powered support to help you resolve issues quickly and efficiently.
        </p>
      </div>

      {/* Action Cards */}
      <div className="grid md:grid-cols-2 gap-8 mb-16">
        {/* Submit Ticket Card */}
        <Link href="/portal/submit">
          <div className="bg-[#111827] rounded-xl border border-white/5 p-10 hover:border-white/10 transition-all duration-300 cursor-pointer group">
            <div className="flex items-center justify-center w-16 h-16 bg-indigo-600 rounded-xl mb-6 group-hover:scale-110 transition-transform">
              <FileText className="h-8 w-8 text-white" />
            </div>
            <h2 className="text-2xl font-semibold text-white mb-3">
              Submit New Ticket
            </h2>
            <p className="text-slate-400 leading-relaxed">
              Create a support request and receive expert assistance from our technical team
            </p>
            <div className="mt-6 flex items-center text-sm font-medium text-indigo-400 group-hover:text-indigo-300">
              Get Started
              <svg className="ml-2 h-4 w-4 group-hover:translate-x-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </div>
          </div>
        </Link>

        {/* Track Ticket Card */}
        <Link href="/portal/track">
          <div className="bg-[#111827] rounded-xl border border-white/5 p-10 hover:border-white/10 transition-all duration-300 cursor-pointer group">
            <div className="flex items-center justify-center w-16 h-16 bg-indigo-600 rounded-xl mb-6 group-hover:scale-110 transition-transform">
              <Search className="h-8 w-8 text-white" />
            </div>
            <h2 className="text-2xl font-semibold text-white mb-3">
              Track Ticket Status
            </h2>
            <p className="text-slate-400 leading-relaxed">
              Monitor the progress of your support requests and view resolution updates
            </p>
            <div className="mt-6 flex items-center text-sm font-medium text-indigo-400 group-hover:text-indigo-300">
              Track Now
              <svg className="ml-2 h-4 w-4 group-hover:translate-x-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </div>
          </div>
        </Link>
      </div>

      {/* Features Grid */}
      <div className="grid md:grid-cols-3 gap-6">
        <div className="bg-[#111827] rounded-lg border border-white/5 p-6">
          <div className="flex items-center justify-center w-12 h-12 bg-white/[0.03] rounded-lg mb-4">
            <Zap className="h-6 w-6 text-slate-300" />
          </div>
          <h4 className="font-semibold text-white mb-2">Real-time Updates</h4>
          <p className="text-sm text-slate-400">
            Receive instant notifications on ticket progress and resolution
          </p>
        </div>
        <div className="bg-[#111827] rounded-lg border border-white/5 p-6">
          <div className="flex items-center justify-center w-12 h-12 bg-white/[0.03] rounded-lg mb-4">
            <FileText className="h-6 w-6 text-slate-300" />
          </div>
          <h4 className="font-semibold text-white mb-2">Detailed Tracking</h4>
          <p className="text-sm text-slate-400">
            Complete audit trail and history of all support interactions
          </p>
        </div>
        <div className="bg-[#111827] rounded-lg border border-white/5 p-6">
          <div className="flex items-center justify-center w-12 h-12 bg-white/[0.03] rounded-lg mb-4">
            <Shield className="h-6 w-6 text-slate-300" />
          </div>
          <h4 className="font-semibold text-white mb-2">Priority Support</h4>
          <p className="text-sm text-slate-400">
            Critical issues escalated immediately to senior engineers
          </p>
        </div>
      </div>
    </div>
  );
}
