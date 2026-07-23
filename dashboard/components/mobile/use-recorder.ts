"use client";
// MediaRecorder wrapper: start() asks for the mic, stop() resolves the
// recorded Blob. Chrome/Android records audio/webm; Safari records
// audio/mp4 — mimeExt tracks the right file extension for the backend.
import { useCallback, useEffect, useRef, useState } from "react";

const MIME = typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported?.("audio/webm")
  ? { type: "audio/webm", ext: "webm" }
  : { type: "audio/mp4", ext: "m4a" };

export function useRecorder() {
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const start = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream, { mimeType: MIME.type });
      chunksRef.current = [];
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.start();
      mediaRef.current = rec;
      setRecording(true);
      setSeconds(0);
      timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
    } catch {
      setError("Microphone unavailable — allow mic access in your browser's site settings.");
    }
  }, []);

  const stop = useCallback((): Promise<Blob | null> => {
    return new Promise((resolve) => {
      const rec = mediaRef.current;
      clearInterval(timerRef.current);
      setRecording(false);
      setSeconds(0);
      if (!rec || rec.state === "inactive") {
        resolve(null);
        return;
      }
      rec.onstop = () => {
        rec.stream.getTracks().forEach((t) => t.stop());
        resolve(new Blob(chunksRef.current, { type: MIME.type }));
      };
      rec.stop();
    });
  }, []);

  useEffect(() => {
    return () => {
      clearInterval(timerRef.current);
      try {
        const rec = mediaRef.current;
        if (rec && rec.state !== "inactive") {
          rec.stop();
          rec.stream.getTracks().forEach((t) => t.stop());
        }
      } catch {
        // best-effort — component is unmounting either way
      }
    };
  }, []);

  return { recording, seconds, error, start, stop, mimeExt: MIME.ext };
}
