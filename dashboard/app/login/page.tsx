"use client";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Brain, Loader2, ArrowRight } from "lucide-react";
import { saveCredentials } from "@/lib/auth";

function LoginForm() {
  const [apiKey, setApiKey] = useState("");
  const [tenantId, setTenantId] = useState("default");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();
  const searchParams = useSearchParams();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      // Verify credentials by hitting a simple endpoint
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080/api/v1"}/health`,
        { headers: { "X-Tenant-ID": tenantId, "Authorization": `Bearer ${apiKey}` } }
      );
      if (!res.ok && res.status === 401) {
        setError("Invalid API key");
        setLoading(false);
        return;
      }
      // Store credentials + set auth cookie for middleware
      saveCredentials(apiKey, tenantId);
      const from = searchParams.get("from") || "/";
      router.push(from);
    } catch {
      setError("Cannot reach API server");
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleLogin} className="bg-surface border border-line rounded-2xl p-6 shadow-sm space-y-4">
      <div>
        <label className="text-xs font-medium text-ink-mid uppercase tracking-wider">Tenant ID</label>
        <input
          type="text"
          value={tenantId}
          onChange={e => setTenantId(e.target.value)}
          className="w-full mt-1.5 bg-surface-2 border border-line rounded-xl px-4 py-2.5 text-sm text-ink placeholder-ink-low focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft transition-all"
          placeholder="default"
        />
      </div>
      <div>
        <label className="text-xs font-medium text-ink-mid uppercase tracking-wider">API Key</label>
        <input
          type="password"
          value={apiKey}
          onChange={e => setApiKey(e.target.value)}
          className="w-full mt-1.5 bg-surface-2 border border-line rounded-xl px-4 py-2.5 text-sm text-ink placeholder-ink-low focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft transition-all"
          placeholder="Enter your API key"
        />
      </div>

      {error && (
        <p className="text-xs text-danger bg-danger-soft border border-danger/30 rounded-lg px-3 py-2">{error}</p>
      )}

      <button
        type="submit"
        disabled={loading}
        className="w-full flex items-center justify-center gap-2 bg-accent text-accent-fg rounded-xl px-4 py-2.5 text-sm font-medium hover:bg-accent-hover shadow-sm hover:shadow transition-all disabled:opacity-50"
      >
        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <><span>Connect</span><ArrowRight className="w-4 h-4" /></>}
      </button>
    </form>
  );
}

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-canvas flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-accent-soft flex items-center justify-center mb-4 shadow-sm">
            <Brain className="w-7 h-7 text-accent" />
          </div>
          <h1 className="text-xl font-bold text-ink tracking-tight">Life Graph</h1>
          <p className="text-sm text-ink-mid mt-1">Personal AI Operating System</p>
        </div>

        {/* Form — Suspense required because LoginForm uses useSearchParams */}
        <Suspense fallback={
          <div className="bg-surface border border-line rounded-2xl p-6 shadow-sm flex items-center justify-center h-48">
            <Loader2 className="w-5 h-5 animate-spin text-accent" />
          </div>
        }>
          <LoginForm />
        </Suspense>

        <p className="text-center text-xs text-ink-low mt-6">
          v0.1.0 · Self-hosted · Your data stays yours
        </p>
      </div>
    </div>
  );
}
