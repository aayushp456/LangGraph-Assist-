"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import type { WSStatus } from "../hooks/useWebSocket";

export interface DebugLog {
  id: number;
  time: string;
  level: "info" | "success" | "warn" | "error";
  source: string;
  message: string;
}

interface DebugPanelProps {
  wsStatus: WSStatus;
  logs: DebugLog[];
}

const LEVEL_COLORS: Record<string, string> = {
  info: "text-blue-400",
  success: "text-green-400",
  warn: "text-yellow-400",
  error: "text-red-400",
};

const WS_STATUS_COLORS: Record<WSStatus, string> = {
  connected: "bg-green-500",
  connecting: "bg-yellow-500 animate-pulse",
  disconnected: "bg-red-500",
};

export function useDebugLog() {
  const [logs, setLogs] = useState<DebugLog[]>([]);
  const idRef = useRef(0);

  const addLog = useCallback(
    (level: DebugLog["level"], source: string, message: string) => {
      const entry: DebugLog = {
        id: ++idRef.current,
        time: new Date().toLocaleTimeString(),
        level,
        source,
        message,
      };
      setLogs((prev) => [...prev.slice(-49), entry]);

      // Also emit to browser console with prefix
      const prefix = `[${source}]`;
      if (level === "error") console.error(prefix, message);
      else if (level === "warn") console.warn(prefix, message);
      else console.log(prefix, message);
    },
    []
  );

  return { logs, addLog };
}

export default function DebugPanel({ wsStatus, logs }: DebugPanelProps) {
  const [open, setOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, open]);

  return (
    <div className="fixed bottom-4 right-4 z-50 font-mono text-xs">
      {/* Toggle button */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 text-white rounded-lg shadow-lg hover:bg-slate-700 transition-colors"
      >
        <span className={`w-2 h-2 rounded-full ${WS_STATUS_COLORS[wsStatus]}`} />
        <span>Debug</span>
        <span className="text-slate-400">({logs.length})</span>
      </button>

      {/* Panel */}
      {open && (
        <div className="absolute bottom-10 right-0 w-[480px] max-h-[360px] bg-slate-900 border border-slate-700 rounded-lg shadow-2xl flex flex-col overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-3 py-2 bg-slate-800 border-b border-slate-700">
            <div className="flex items-center gap-2 text-white">
              <span className={`w-2 h-2 rounded-full ${WS_STATUS_COLORS[wsStatus]}`} />
              <span>WS: {wsStatus}</span>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="text-slate-400 hover:text-white"
            >
              ✕
            </button>
          </div>

          {/* Log entries */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-2 space-y-0.5">
            {logs.length === 0 ? (
              <p className="text-slate-500 text-center py-4">No logs yet</p>
            ) : (
              logs.map((log) => (
                <div key={log.id} className="flex gap-2 leading-tight">
                  <span className="text-slate-500 flex-shrink-0">{log.time}</span>
                  <span className="text-slate-400 flex-shrink-0 w-20 text-right">[{log.source}]</span>
                  <span className={LEVEL_COLORS[log.level]}>{log.message}</span>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
