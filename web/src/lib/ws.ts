"use client";

import { useEffect, useRef } from "react";

// One shared WebSocket for the whole app. Components subscribe to topics
// ("submission:42", "group:7"); the server pushes {topic, event, data} messages.

export type LiveMessage = { topic: string; event: string; data: Record<string, unknown> };
type Handler = (msg: LiveMessage) => void;

let socket: WebSocket | null = null;
let attempts = 0;
const handlers = new Map<string, Set<Handler>>();

function send(msg: { op: "subscribe" | "unsubscribe"; topic: string }) {
  if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(msg));
}

function connect() {
  if (socket && socket.readyState <= WebSocket.OPEN) return; // connecting or open
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${proto}://${window.location.host}/ws`);
  socket.onopen = () => {
    attempts = 0;
    for (const topic of handlers.keys()) send({ op: "subscribe", topic });
  };
  socket.onmessage = (e) => {
    const msg = JSON.parse(e.data) as LiveMessage;
    handlers.get(msg.topic)?.forEach((h) => h(msg));
  };
  socket.onclose = () => {
    socket = null;
    if (handlers.size) setTimeout(connect, Math.min(1000 * 2 ** attempts++, 10_000));
  };
}

function subscribe(topic: string, handler: Handler): () => void {
  let set = handlers.get(topic);
  if (!set) {
    set = new Set();
    handlers.set(topic, set);
    send({ op: "subscribe", topic }); // no-op until open; onopen resubscribes everything
  }
  set.add(handler);
  connect();
  return () => {
    set.delete(handler);
    if (set.size === 0) {
      handlers.delete(topic);
      send({ op: "unsubscribe", topic });
    }
  };
}

/** Call `handler` for every live message on `topic` while mounted. Pass null to skip. */
export function useTopic(topic: string | null, handler: Handler) {
  const latest = useRef(handler);
  useEffect(() => {
    latest.current = handler;
  });
  useEffect(() => {
    if (!topic) return;
    return subscribe(topic, (msg) => latest.current(msg));
  }, [topic]);
}
