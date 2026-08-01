"use client";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Mic, Square, Camera, Paperclip, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { useCreateMemory } from "@/lib/hooks";
import { useMobileState } from "./mobile-state";
import { useRecorder } from "./use-recorder";
import { onCaptureComplete, type CaptureSource } from "@/lib/capture-events";

const KINDS: Array<[string, string]> = [
  ["auto", "Auto"],
  ["memory", "Memory"],
  ["task", "Task"],
  ["intention", "Intention"],
];

const chipBase: CSSProperties = {
  height: "30px",
  paddingInline: "11px",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-pill)",
  background: "var(--surface-2)",
  color: "var(--text-muted)",
  fontFamily: "inherit",
  fontSize: "var(--text-xs)",
  fontWeight: "var(--fw-semibold)",
  cursor: "pointer",
};
const chipOn: CSSProperties = {
  ...chipBase,
  background: "var(--accent-soft)",
  borderColor: "var(--accent)",
  color: "var(--accent-soft-fg)",
};

type Result =
  | { kind: "captured"; routedTo: string }
  | { kind: "queued" }
  | { kind: "processing"; source: CaptureSource }
  | { kind: "done-async"; source: CaptureSource; count: number }
  | { kind: "error"; message?: string }
  | null;

const SOURCE_LABEL: Record<CaptureSource, string> = {
  voice: "Voice note",
  image: "Photo",
  document: "Document",
};

function routedTarget(res: any, fallback: string): string {
  return res?.route?.target || res?.target || res?.kind || res?.classification || fallback;
}

export function MobileCapture() {
  const { online, enqueueCapture } = useMobileState();
  const route = useCreateMemory();
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [kind, setKind] = useState("auto");
  const [result, setResult] = useState<Result>(null);

  useEffect(() => {
    return onCaptureComplete(({ source, memoriesCreated }) => {
      setResult({ kind: "done-async", source, count: memoriesCreated });
    });
  }, []);

  const recorder = useRecorder();
  const [busy, setBusy] = useState<null | "voice" | "file">(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const MAX_FILE_BYTES = 20 * 1024 * 1024; // stay far below Cloudflare's 100MB

  const afterIngest = (source: CaptureSource) => {
    setResult({ kind: "processing", source });
    // The memories list refreshes live on the completion WS event; still
    // nudge tasks in case the capture routed to one.
    qc.invalidateQueries({ queryKey: ["tasks"] });
  };

  const onMicTap = async () => {
    if (recorder.recording) {
      const blob = await recorder.stop();
      if (!blob || blob.size === 0) return;
      if (blob.size > MAX_FILE_BYTES) {
        setResult({ kind: "error", message: "File is too large (max 20 MB)" });
        return;
      }
      setBusy("voice");
      try {
        await api.ingest.voice(blob, `note.${recorder.mimeExt}`);
        afterIngest("voice");
      } catch {
        setResult({ kind: "error", message: "Couldn't transcribe — try again" });
      } finally {
        setBusy(null);
      }
    } else {
      void recorder.start();
    }
  };

  const onFilePicked = async (f: File | undefined) => {
    if (!f) return;
    if (f.size > MAX_FILE_BYTES) {
      setResult({ kind: "error", message: "File is too large (max 20 MB)" });
      return;
    }
    setBusy("file");
    try {
      if (f.type === "application/pdf") {
        await api.ingest.document(f);
        afterIngest("document");
      } else {
        await api.ingest.image(f);
        afterIngest("image");
      }
    } catch {
      setResult({ kind: "error", message: "Upload failed — try again" });
    } finally {
      setBusy(null);
    }
  };

  const submit = async () => {
    const content = text.trim();
    if (!content || route.isPending) return;
    const fallbackKind = kind === "auto" ? "memory" : kind;
    setText("");

    // Offline: persist to the IndexedDB queue; the provider flushes on reconnect.
    if (!online) {
      await enqueueCapture(content);
      setResult({ kind: "queued" });
      return;
    }

    try {
      const res = await route.mutateAsync(content);
      setResult({ kind: "captured", routedTo: routedTarget(res, fallbackKind) });
    } catch {
      setResult({ kind: "error" });
      setText(content); // let the user retry without retyping
    }
  };

  return (
    <section
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-sm)",
        padding: "14px",
      }}
    >
      <textarea
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setResult(null);
        }}
        rows={3}
        placeholder="Capture a thought… it becomes a memory, task or intention."
        style={{
          width: "100%",
          border: 0,
          outline: "none",
          resize: "none",
          background: "transparent",
          color: "var(--text)",
          fontFamily: "inherit",
          fontSize: "var(--ui-text)",
          lineHeight: 1.55,
          boxSizing: "border-box",
        }}
      />
      <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: "6px", rowGap: "8px", marginTop: "8px" }}>
        {KINDS.map(([id, label]) => (
          <button key={id} onClick={() => setKind(id)} style={kind === id ? chipOn : chipBase}>
            {label}
          </button>
        ))}
        <button
          onClick={submit}
          disabled={!text.trim() || route.isPending}
          style={{
            marginInlineStart: "auto",
            height: "34px",
            paddingInline: "16px",
            border: 0,
            borderRadius: "var(--radius-pill)",
            background: "var(--accent)",
            color: "var(--accent-fg)",
            fontFamily: "inherit",
            fontSize: "var(--text-sm)",
            fontWeight: "var(--fw-bold)",
            cursor: text.trim() && !route.isPending ? "pointer" : "not-allowed",
            opacity: text.trim() && !route.isPending ? 1 : 0.5,
          }}
        >
          {route.isPending ? "Routing…" : "Capture"}
        </button>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "10px" }}>
        <button
          type="button"
          onClick={onMicTap}
          disabled={!online || busy !== null}
          aria-label={recorder.recording ? "Stop recording" : "Record a voice note"}
          style={{
            ...chipBase,
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            ...(recorder.recording
              ? { background: "var(--danger-soft, #fee)", borderColor: "var(--danger, #d33)", color: "var(--danger, #d33)" }
              : {}),
            opacity: !online || busy !== null ? 0.5 : 1,
          }}
        >
          {recorder.recording ? <Square width={14} height={14} /> : <Mic width={14} height={14} />}
          {recorder.recording ? `Stop · ${recorder.seconds}s` : "Voice"}
        </button>

        <button
          type="button"
          onClick={() => cameraInputRef.current?.click()}
          disabled={!online || busy !== null || recorder.recording}
          aria-label="Capture a photo"
          style={{ ...chipBase, display: "inline-flex", alignItems: "center", gap: "6px", opacity: !online || busy !== null ? 0.5 : 1 }}
        >
          <Camera width={14} height={14} /> Camera
        </button>

        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={!online || busy !== null || recorder.recording}
          aria-label="Attach a photo or PDF"
          style={{ ...chipBase, display: "inline-flex", alignItems: "center", gap: "6px", opacity: !online || busy !== null ? 0.5 : 1 }}
        >
          <Paperclip width={14} height={14} /> Attach
        </button>

        {busy !== null && (
          <span style={{ display: "inline-flex", alignItems: "center", gap: "5px", fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
            <Loader2 width={13} height={13} className="animate-spin" />
            {busy === "voice" ? "Transcribing…" : "Uploading…"}
          </span>
        )}
      </div>

      {!online && (
        <p style={{ fontSize: "var(--text-2xs)", color: "var(--text-subtle)", marginTop: "6px" }}>
          Voice, camera, and attachments need a connection — text capture still queues offline.
        </p>
      )}
      {recorder.error && (
        <p style={{ fontSize: "var(--text-2xs)", color: "var(--danger, #d33)", marginTop: "6px" }}>{recorder.error}</p>
      )}

      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        onChange={(e) => { void onFilePicked(e.target.files?.[0]); e.target.value = ""; }}
      />
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*,application/pdf"
        hidden
        onChange={(e) => { void onFilePicked(e.target.files?.[0]); e.target.value = ""; }}
      />

      {result?.kind === "captured" && (
        <Toast bg="var(--success-soft)" fg="var(--success)">
          Captured — routed to {result.routedTo} · pending your approval
        </Toast>
      )}
      {result?.kind === "queued" && (
        <Toast bg="var(--warning-soft)" fg="var(--warning)">
          Saved offline — will sync when you reconnect
        </Toast>
      )}
      {result?.kind === "processing" && (
        <Toast bg="var(--surface-2)" fg="var(--text-muted)">
          {SOURCE_LABEL[result.source]} uploaded — processing…
        </Toast>
      )}
      {result?.kind === "done-async" && (
        <Toast bg="var(--success-soft)" fg="var(--success)">
          {SOURCE_LABEL[result.source]} → {result.count} {result.count === 1 ? "memory" : "memories"}
        </Toast>
      )}
      {result?.kind === "error" && (
        <Toast bg="var(--danger-soft)" fg="var(--danger)">
          {result.message ?? "Couldn’t reach the server — your text is kept, try again"}
        </Toast>
      )}
    </section>
  );
}

function Toast({ bg, fg, children }: { bg: string; fg: string; children: React.ReactNode }) {
  return (
    <div
      role="status"
      style={{
        marginTop: "10px",
        padding: "9px 12px",
        borderRadius: "var(--radius-md)",
        background: bg,
        color: fg,
        fontSize: "var(--text-xs)",
        fontWeight: "var(--fw-semibold)",
      }}
    >
      {children}
    </div>
  );
}
