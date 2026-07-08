export default function SettingsPage() {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-zinc-900">Settings</h2>
        <p className="text-sm text-zinc-500">System configuration</p>
      </div>
      <div className="bg-white border border-zinc-200 rounded-xl p-6 space-y-5">
        <div>
          <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider">API Endpoint</label>
          <p className="text-sm text-zinc-800 mt-1 font-mono bg-zinc-50 px-3 py-2 rounded-lg border border-zinc-100">
            {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"}
          </p>
        </div>
        <div>
          <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Tenant ID</label>
          <p className="text-sm text-zinc-800 mt-1 font-mono bg-zinc-50 px-3 py-2 rounded-lg border border-zinc-100">
            {process.env.NEXT_PUBLIC_TENANT_ID || "default"}
          </p>
        </div>
        <div>
          <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Version</label>
          <p className="text-sm text-zinc-800 mt-1">Life Graph Dashboard v0.1.0</p>
        </div>
      </div>
    </div>
  );
}
