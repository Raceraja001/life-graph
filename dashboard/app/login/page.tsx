"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Brain, Loader2, ArrowRight } from "lucide-react";

export default function LoginPage() {
  const [apiKey, setApiKey] = useState("");
  const [tenantId, setTenantId] = useState("default");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      // Verify credentials by hitting a simple endpoint
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"}/health`,
        { headers: { "X-Tenant-ID": tenantId, "Authorization": `Bearer ${apiKey}` } }
      );
      if (!res.ok && res.status === 401) {
        setError("Invalid API key");
        setLoading(false);
        return;
      }
      // Store credentials
      localStorage.setItem("lg_api_key", apiKey);
      localStorage.setItem("lg_tenant_id", tenantId);
      router.push("/");
    } catch {
      setError("Cannot reach API server");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#fafafa] flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-emerald-100 flex items-center justify-center mb-4 shadow-sm">
            <Brain className="w-7 h-7 text-emerald-600" />
          </div>
          <h1 className="text-xl font-bold text-zinc-900 tracking-tight">Life Graph</h1>
          <p className="text-sm text-zinc-500 mt-1">Personal AI Operating System</p>
        </div>

        {/* Form */}
        <form onSubmit={handleLogin} className="bg-white border border-zinc-200 rounded-2xl p-6 shadow-sm space-y-4">
          <div>
            <label className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Tenant ID</label>
            <input
              type="text"
              value={tenantId}
              onChange={e => setTenantId(e.target.value)}
              className="w-full mt-1.5 bg-zinc-50 border border-zinc-200 rounded-xl px-4 py-2.5 text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100 transition-all"
              placeholder="default"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-zinc-500 uppercase tracking-wider">API Key</label>
            <input
              type="password"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              className="w-full mt-1.5 bg-zinc-50 border border-zinc-200 rounded-xl px-4 py-2.5 text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100 transition-all"
              placeholder="Enter your API key"
            />
          </div>

          {error && (
            <p className="text-xs text-red-500 bg-red-50 border border-red-100 rounded-lg px-3 py-2">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 bg-emerald-600 text-white rounded-xl px-4 py-2.5 text-sm font-medium hover:bg-emerald-700 shadow-sm hover:shadow transition-all disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <><span>Connect</span><ArrowRight className="w-4 h-4" /></>}
          </button>
        </form>

        <p className="text-center text-xs text-zinc-400 mt-6">
          v0.1.0 · Self-hosted · Your data stays yours
        </p>
      </div>
    </div>
  );
}
