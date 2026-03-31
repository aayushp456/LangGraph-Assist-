"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { getWebSocketUrl } from "@/lib/runtime-config";

export type WSStatus = "connecting" | "connected" | "disconnected";

export interface WSEvent {
  type: string;
  payload: Record<string, unknown>;
  timestamp: string;
}

type EventHandler = (event: WSEvent) => void;

interface UseWebSocketOptions {
  subscriptions?: string[];
  onEvent?: EventHandler;
  enabled?: boolean;
}

export function useWebSocket({ subscriptions = [], onEvent, enabled = true }: UseWebSocketOptions = {}) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttempt = useRef(0);
  const mountedRef = useRef(true);
  const [status, setStatus] = useState<WSStatus>("disconnected");
  const handlersRef = useRef<Map<string, EventHandler[]>>(new Map());
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  // Store subscriptions in a ref so they don't trigger reconnects
  const subscriptionsRef = useRef(subscriptions);
  subscriptionsRef.current = subscriptions;

  const subscribe = useCallback((eventType: string, handler: EventHandler) => {
    const handlers = handlersRef.current.get(eventType) || [];
    handlers.push(handler);
    handlersRef.current.set(eventType, handlers);

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "subscribe", event: eventType }));
      console.log(`[WS] Subscribed to ${eventType}`);
    }

    return () => {
      const h = handlersRef.current.get(eventType) || [];
      handlersRef.current.set(eventType, h.filter((fn) => fn !== handler));
    };
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (!mountedRef.current) return;
    if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    const delay = Math.min(1000 * 2 ** reconnectAttempt.current, 30000);
    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${reconnectAttempt.current + 1})`);
    reconnectTimer.current = setTimeout(() => {
      if (!mountedRef.current) return;
      reconnectAttempt.current += 1;
      doConnect();
    }, delay);
  }, []);

  function doConnect() {
    if (!enabled || !mountedRef.current) return;
    // Prevent duplicate connections
    if (wsRef.current) {
      const state = wsRef.current.readyState;
      if (state === WebSocket.OPEN || state === WebSocket.CONNECTING) return;
    }

    try {
      const wsUrl = getWebSocketUrl();
      console.log(`[WS] Connecting to ${wsUrl}...`);
      setStatus("connecting");
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        if (!mountedRef.current) { ws.close(); return; }
        console.log("[WS] Connected");
        setStatus("connected");
        reconnectAttempt.current = 0;

        const allEvents = new Set([
          ...subscriptionsRef.current,
          ...Array.from(handlersRef.current.keys()),
        ]);
        allEvents.forEach((eventType) => {
          ws.send(JSON.stringify({ type: "subscribe", event: eventType }));
          console.log(`[WS] Subscribed to ${eventType}`);
        });
      };

      ws.onmessage = (event) => {
        try {
          const data: WSEvent = JSON.parse(event.data);
          console.log(`[WS] Event received: ${data.type}`, data.payload);
          onEventRef.current?.(data);
          const handlers = handlersRef.current.get(data.type) || [];
          handlers.forEach((h) => h(data));
        } catch (err) {
          console.warn("[WS] Failed to parse message:", err);
        }
      };

      ws.onclose = () => {
        console.log("[WS] Disconnected");
        if (mountedRef.current) {
          setStatus("disconnected");
          wsRef.current = null;
          scheduleReconnect();
        }
      };

      ws.onerror = (err) => {
        console.error("[WS] Error:", err);
        ws.close();
      };

      wsRef.current = ws;
    } catch (err) {
      console.error("[WS] Connection failed:", err);
      if (mountedRef.current) {
        setStatus("disconnected");
        scheduleReconnect();
      }
    }
  }

  // Connect once on mount, clean up on unmount
  useEffect(() => {
    mountedRef.current = true;
    doConnect();
    return () => {
      mountedRef.current = false;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // prevent reconnect on intentional close
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [enabled]); // only reconnect if enabled changes

  return { status, subscribe };
}
