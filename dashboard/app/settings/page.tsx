"use client";
import { useState, useSyncExternalStore } from "react";
import { usePersonas, useUpdatePersona, type PersonaVM } from "@/lib/mobile-api";
import { ModelCombobox } from "@/components/model-combobox";
import { API_BASE, getTenantId } from "@/lib/api";

export default function SettingsPage() {
  // The tenant lives in localStorage, which the server cannot read, so it is
  // read as external state: null on the server (and on the hydrating render),
  // the real value on the client. This panel previously printed build-time env
  // defaults instead, reporting a stale endpoint (:8000) and "default" no
  // matter who was logged in. It only changes at login/logout, both of which
  // navigate, so there is nothing to subscribe to.
  const tenantId = useSyncExternalStore(
    () => () => {},
    () => getTenantId(),
    () => null,
  );

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-ink">Settings</h2>
        <p className="text-sm text-ink-mid">System configuration</p>
      </div>
      <div className="bg-surface border border-line rounded-xl p-6 space-y-5">
        <div>
          <label className="text-xs font-medium text-ink-low uppercase tracking-wider">API Endpoint</label>
          <p className="text-sm text-ink mt-1 font-mono bg-surface-2 px-3 py-2 rounded-lg border border-line">
            {API_BASE}
          </p>
        </div>
        <div>
          <label className="text-xs font-medium text-ink-low uppercase tracking-wider">Tenant ID</label>
          <p className="text-sm text-ink mt-1 font-mono bg-surface-2 px-3 py-2 rounded-lg border border-line">
            {tenantId ?? "—"}
          </p>
        </div>
        <div>
          <label className="text-xs font-medium text-ink-low uppercase tracking-wider">Version</label>
          <p className="text-sm text-ink mt-1">Life Graph Dashboard v0.1.0</p>
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
    <div className="bg-surface border border-line rounded-xl p-6 space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-ink">Personas</h3>
        <p className="text-xs text-ink-mid">Model, temperature &amp; max tokens per persona</p>
      </div>
      {personas.isLoading && <p className="text-sm text-ink-mid">Loading personas…</p>}
      {personas.isError && (
        <p className="text-sm text-danger">Can&rsquo;t reach personas — is the backend running?</p>
      )}
      {!personas.isLoading && !personas.isError && rows.length === 0 && (
        <p className="text-sm text-ink-mid">No personas configured yet.</p>
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
      className="border border-line rounded-lg p-4 space-y-3"
      style={{ opacity: busy ? 0.7 : 1 }}
    >
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-ink">{persona.displayName ?? persona.name}</span>
        {persona.isBuiltin && (
          <span className="text-xs text-ink-mid border border-line rounded-full px-2 py-0.5">
            Built-in
          </span>
        )}
      </div>

      <div>
        <label className="text-xs font-medium text-ink-low uppercase tracking-wider">Model</label>
        <div className="mt-1">
          <ModelCombobox value={model} onChange={setModel} disabled={busy} variant="desktop" />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-ink-low uppercase tracking-wider">Temperature</label>
          <input
            type="number"
            min={0}
            max={2}
            step={0.1}
            value={temperature}
            disabled={busy}
            onChange={(e) => setTemperature(Number(e.target.value))}
            className="w-full mt-1 text-sm text-ink bg-surface-2 px-3 py-2 rounded-lg border border-line"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-ink-low uppercase tracking-wider">Max tokens</label>
          <input
            type="number"
            min={1}
            max={128000}
            value={maxTokens}
            disabled={busy}
            onChange={(e) => setMaxTokens(Number(e.target.value))}
            className="w-full mt-1 text-sm text-ink bg-surface-2 px-3 py-2 rounded-lg border border-line"
          />
        </div>
      </div>

      {update.isError && <p className="text-xs text-danger">Couldn&rsquo;t save — try again</p>}

      <button
        type="button"
        disabled={!dirty || busy}
        onClick={save}
        className={
          dirty && !busy
            ? "w-full py-2 text-sm font-semibold rounded-lg bg-info text-info-fg cursor-pointer"
            : "w-full py-2 text-sm font-semibold rounded-lg bg-surface-3 text-ink-low cursor-default"
        }
      >
        Save
      </button>
    </div>
  );
}
