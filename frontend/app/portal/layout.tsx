"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FileText, Search, LogOut } from "lucide-react";
import Image from "next/image";
import { useAuth } from "@/hooks/useAuth";

const PUBLIC_PATHS = ["/portal/login", "/portal/register"];

export default function PortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading, logout } = useAuth();

  const isPublicPage = PUBLIC_PATHS.includes(pathname);

  // Redirect to login if not authenticated and not on a public page
  useEffect(() => {
    if (loading) return;
    if (!isPublicPage && !user) {
      router.push("/portal/login");
    }
    // If logged in but not a customer, redirect away
    if (user && user.role !== "customer") {
      router.push("/dashboard");
    }
  }, [user, loading, isPublicPage, router]);

  // Public pages (login/register) — render without chrome
  if (isPublicPage) {
    return <>{children}</>;
  }

  // Loading state
  if (loading || !user) {
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
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-20">
            <div className="flex items-center space-x-3">
              <Link href="/portal" className="flex items-center space-x-3 group">
                <Image src="/logo.png" alt="Humanitarians AI" width={40} height={40} className="rounded-lg" />
                <div>
                  <span className="text-xl font-semibold text-white tracking-tight">Humanitarians AI</span>
                  <p className="text-xs text-slate-500 font-medium">AI Support Portal</p>
                </div>
              </Link>
            </div>
            <nav className="flex items-center space-x-2">
              <Link
                href="/portal/submit"
                className="px-5 py-2.5 text-sm font-medium text-slate-300 hover:text-white hover:bg-white/5 rounded-lg transition-all duration-200 flex items-center space-x-2"
              >
                <FileText className="h-4 w-4" />
                <span>New Ticket</span>
              </Link>
              <Link
                href="/portal/track"
                className="px-5 py-2.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg transition-all duration-200 flex items-center space-x-2 shadow-sm"
              >
                <Search className="h-4 w-4" />
                <span>My Tickets</span>
              </Link>
              <div className="flex items-center gap-2 px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg ml-2">
                <span className="text-sm text-slate-300">{user.name}</span>
              </div>
              <button
                onClick={() => { logout(); router.push("/portal/login"); }}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-slate-400 hover:text-white hover:border-red-500/30 transition-colors"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {children}
      </main>

      {/* Footer */}
      <footer className="bg-[#111827]/50 border-t border-white/5 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div>
            <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">Resources</h3>
            <div className="flex space-x-6">
              <a href="#" className="text-sm text-slate-500 hover:text-slate-300 transition-colors">Knowledge Base</a>
              <a href="#" className="text-sm text-slate-500 hover:text-slate-300 transition-colors">API Documentation</a>
              <a href="#" className="text-sm text-slate-500 hover:text-slate-300 transition-colors">Service Status</a>
            </div>
          </div>
          <div className="mt-8 pt-8 border-t border-white/5">
            <p className="text-center text-xs text-slate-600">
              &copy; 2024 Humanitarians AI. All rights reserved. | <a href="#" className="hover:text-slate-400">Privacy Policy</a> | <a href="#" className="hover:text-slate-400">Terms of Service</a>
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
