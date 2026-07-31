"use client";
import { useEffect, useRef, useState } from "react";

interface Options {
  onRefresh: () => void | Promise<unknown>;
  threshold?: number;
}

/**
 * Pull-to-refresh for the mobile scroll container ([data-scroll-root]).
 * Engages only when that container is scrolled to the top and the drag is
 * downward. No dependency; guards for SSR / non-touch. Returns indicator state.
 */
export function usePullToRefresh({ onRefresh, threshold = 64 }: Options) {
  const [distance, setDistance] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const startY = useRef<number | null>(null);
  const refreshingRef = useRef(false);
  // Keep a ref of the live distance for the touchend closure.
  const distanceRef = useRef(0);
  // Keep a ref of the live onRefresh so the touchend closure never goes stale
  // (the caller's onRefresh identity/behavior can change render to render —
  // e.g. it depends on search state — but the listener effect below only
  // re-attaches on [threshold]).
  const onRefreshRef = useRef(onRefresh);

  useEffect(() => {
    onRefreshRef.current = onRefresh;
  }, [onRefresh]);

  useEffect(() => {
    if (typeof window === "undefined" || !("ontouchstart" in window)) return;
    const el = document.querySelector<HTMLElement>("[data-scroll-root]");
    if (!el) return;

    const onStart = (e: TouchEvent) => {
      if (el.scrollTop <= 0 && !refreshingRef.current) {
        startY.current = e.touches[0].clientY;
      } else {
        startY.current = null;
      }
    };
    const onMove = (e: TouchEvent) => {
      if (startY.current === null) return;
      const dy = e.touches[0].clientY - startY.current;
      if (dy <= 0) {
        distanceRef.current = 0;
        setDistance(0);
        return;
      }
      // Rubber-band: dampen the pull so it feels physical.
      const next = Math.min(dy * 0.5, threshold * 1.5);
      distanceRef.current = next;
      setDistance(next);
    };
    const onEnd = async () => {
      if (startY.current === null) return;
      const pulled = distanceRef.current;
      startY.current = null;
      setDistance(0);
      if (pulled >= threshold && !refreshingRef.current) {
        refreshingRef.current = true;
        setRefreshing(true);
        try {
          await onRefreshRef.current();
        } finally {
          refreshingRef.current = false;
          setRefreshing(false);
        }
      }
    };

    el.addEventListener("touchstart", onStart, { passive: true });
    el.addEventListener("touchmove", onMove, { passive: true });
    el.addEventListener("touchend", onEnd);
    el.addEventListener("touchcancel", onEnd);
    return () => {
      el.removeEventListener("touchstart", onStart);
      el.removeEventListener("touchmove", onMove);
      el.removeEventListener("touchend", onEnd);
      el.removeEventListener("touchcancel", onEnd);
    };
    // onRefresh is read via onRefreshRef (always live); threshold is stable.
  }, [threshold]);

  return { refreshing, distance };
}
