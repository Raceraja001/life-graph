"use client";
import { useState } from "react";
import { usePersonas, useUpdatePersona, type PersonaVM } from "@/lib/mobile-api";
import { ModelCombobox } from "@/components/model-combobox";

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
      <PersonaSettings />
    </div>
  );
}

function PersonaSettings() {
  const personas = usePersonas();
  const rows = personas.data ?? [];

  return (
    <div className="bg-white border border-zinc-200 rounded-xl p-6 space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-zinc-900">Personas</h3>
        <p className="text-xs text-zinc-500">Model, temperature &amp; max tokens per persona</p>
      </div>
      {personas.isLoading && <p className="text-sm text-zinc-500">Loading personas…</p>}
      {personas.isError && (
        <p className="text-sm text-red-600">Can&rsquo;t reach personas — is the backend running?</p>
      )}
      {!personas.isLoading && !personas.isError && rows.length === 0 && (
        <p className="text-sm text-zinc-500">No personas configured yet.</p>
      )}
      <div className="space-y-3">
        {rows.map((p) => (
          <PersonaCard key={p.id} persona={p} />
        ))}
      </div>
    </div>
  );
}

function PersonaCard({ persona }: { persona: PersonaVM }) {
  const update = useUpdatePersona();
  const busy = update.isPending;

  const [model, setModel] = useState(persona.model);
  const [temperature, setTemperature] = useState(persona.temperature);
  const [maxTokens, setMaxTokens] = useState(persona.maxTokens);

  const dirty =
    model !== persona.model || temperature !== persona.temperature || maxTokens !== persona.maxTokens;

  function revert() {
    setModel(persona.model);
    setTemperature(persona.temperature);
    setMaxTokens(persona.maxTokens);
  }

  function save() {
    const body: Record<string, unknown> = {};
    if (model !== persona.model) body.model = model;
    if (temperature !== persona.temperature) body.temperature = temperature;
    if (maxTokens !== persona.maxTokens) body.max_tokens = maxTokens;
    update.mutate({ id: persona.id, body }, { onError: () => revert() });
  }

  return (
    <div
      className="border border-zinc-100 rounded-lg p-4 space-y-3"
      style={{ opacity: busy ? 0.7 : 1 }}
    >
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-zinc-900">{persona.displayName ?? persona.name}</span>
        {persona.isBuiltin && (
          <span className="text-xs text-zinc-500 border border-zinc-200 rounded-full px-2 py-0.5">
            Built-in
          </span>
        )}
      </div>

      <div>
        <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Model</label>
        <div className="mt-1">
          <ModelCombobox value={model} onChange={setModel} disabled={busy} variant="desktop" />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Temperature</label>
          <input
            type="number"
            min={0}
            max={2}
            step={0.1}
            value={temperature}
            disabled={busy}
            onChange={(e) => setTemperature(Number(e.target.value))}
            className="w-full mt-1 text-sm text-zinc-800 bg-zinc-50 px-3 py-2 rounded-lg border border-zinc-100"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Max tokens</label>
          <input
            type="number"
            min={1}
            max={128000}
            value={maxTokens}
            disabled={busy}
            onChange={(e) => setMaxTokens(Number(e.target.value))}
            className="w-full mt-1 text-sm text-zinc-800 bg-zinc-50 px-3 py-2 rounded-lg border border-zinc-100"
          />
        </div>
      </div>

      {update.isError && <p className="text-xs text-red-600">Couldn&rsquo;t save — try again</p>}

      <button
        type="button"
        disabled={!dirty || busy}
        onClick={save}
        className={
          dirty && !busy
            ? "w-full py-2 text-sm font-semibold rounded-lg bg-blue-600 text-white cursor-pointer"
            : "w-full py-2 text-sm font-semibold rounded-lg bg-zinc-100 text-zinc-400 cursor-default"
        }
      >
        Save
      </button>
    </div>
  );
}
