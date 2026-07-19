"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { count, enqueue, getAll, remove } from "@/lib/offline-queue";

interface MobileStateValue {
  online: boolean;
  toggleOnline: () => void; // manual demo override; real events also drive `online`
  queued: number;
  enqueueCapture: (content: string) => Promise<void>;
}

const Ctx = createContext<MobileStateValue | null>(null);

export function MobileStateProvider({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient();
  const [online, setOnline] = useState(true);
  const [queued, setQueued] = useState(0);

  // Replay queued captures to the backend; stop at the first failure (still down).
  const flush = useCallback(async () => {
    const items = await getAll();
    for (const item of items) {
      try {
        await api.kernel.route(item.content);
        await remove(item.id);
      } catch {
        break;
      }
    }
    setQueued(await count());
    qc.invalidateQueries({ queryKey: ["memories"] });
    qc.invalidateQueries({ queryKey: ["tasks"] });
  }, [qc]);

  // Keep the latest flush in a ref so the mount-only listeners never go stale.
  const flushRef = useRef(flush);
  flushRef.current = flush;

  useEffect(() => {
    let active = true;
    count().then((c) => active && setQueued(c));
    if (typeof navigator !== "undefined") setOnline(navigator.onLine);

    const goOnline = () => {
      setOnline(true);
      void flushRef.current();
    };
    const goOffline = () => setOnline(false);
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      active = false;
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, []);

  const enqueueCapture = useCallback(async (content: string) => {
    await enqueue(content);
    setQueued(await count());
  }, []);

  const toggleOnline = useCallback(() => {
    setOnline((prev) => !prev);
    if (!online) void flushRef.current(); // currently offline → going online
  }, [online]);

  const value = useMemo<MobileStateValue>(
    () => ({ online, toggleOnline, queued, enqueueCapture }),
    [online, toggleOnline, queued, enqueueCapture],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useMobileState() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useMobileState must be used within MobileStateProvider");
  return v;
}
