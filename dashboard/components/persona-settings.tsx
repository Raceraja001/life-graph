"use client";
// Persona model/temperature/max_tokens editor — fixes a persona stuck on a
// dead/deprecated model id without SSH or direct database access. Mirrors
// ambient-roles.tsx's card/CSS-variable conventions, but gives each card its
// own useUpdatePersona() mutation instance (rather than one shared mutation
// at the list level) so busy/error state is naturally scoped per card, with
// no need to compare a shared mutation's `variables.id` against each row.
import { useState, type CSSProperties } from "react";
import { LoadingCard, EmptyCard, ErrorCard } from "@/components/mobile/parts";
import { usePersonas, useUpdatePersona, type PersonaVM } from "@/lib/mobile-api";
import { ModelCombobox } from "@/components/model-combobox";

const cardStyle: CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-card)",
  padding: "var(--o-lg)",
};

const inputStyle: CSSProperties = {
  width: "100%",
  padding: "8px 10px",
  borderRadius: "var(--radius-field)",
  border: "1px solid var(--border)",
  background: "var(--surface)",
  color: "var(--text)",
  fontSize: "var(--size-meta)",
};

const labelStyle: CSSProperties = {
  display: "block",
  fontSize: "var(--size-meta)",
  color: "var(--text-muted)",
  marginBottom: "4px",
};

export default function PersonaSettings() {
  const personas = usePersonas();
  const rows = personas.data ?? [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {personas.isLoading && <LoadingCard label="Loading personas…" />}
      {personas.isError && <ErrorCard>Can&rsquo;t reach personas — is the backend running?</ErrorCard>}
      {!personas.isLoading && !personas.isError && rows.length === 0 && (
        <EmptyCard hint="Personas are seeded on first boot — if this stays empty, the backend never finished startup.">
          No personas configured yet.
        </EmptyCard>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
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
    <section style={{ ...cardStyle, opacity: busy ? 0.7 : 1 }}>
      <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "10px" }}>
        <span style={{ fontSize: "var(--size-body)", fontWeight: 600 }}>
          {persona.displayName ?? persona.name}
        </span>
        {persona.isBuiltin && (
          <span
            style={{
              fontSize: "var(--size-meta)",
              color: "var(--text-subtle)",
              border: "1px solid var(--border)",
              borderRadius: "999px",
              padding: "1px 7px",
            }}
          >
            Built-in
          </span>
        )}
      </div>

      <label style={labelStyle}>Model</label>
      <div style={{ marginBottom: "10px" }}>
        <ModelCombobox value={model} onChange={setModel} disabled={busy} variant="mobile" />
      </div>

      <div style={{ display: "flex", gap: "10px", marginBottom: "10px" }}>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Temperature</label>
          <input
            type="number"
            min={0}
            max={2}
            step={0.1}
            value={temperature}
            disabled={busy}
            onChange={(e) => setTemperature(Number(e.target.value))}
            style={inputStyle}
          />
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Max tokens</label>
          <input
            type="number"
            min={1}
            max={128000}
            value={maxTokens}
            disabled={busy}
            onChange={(e) => setMaxTokens(Number(e.target.value))}
            style={inputStyle}
          />
        </div>
      </div>

      {update.isError && (
        <p style={{ fontSize: "var(--size-meta)", color: "var(--danger)", marginBottom: "8px" }}>
          Couldn&rsquo;t save — try again
        </p>
      )}

      <button
        type="button"
        disabled={!dirty || busy}
        onClick={save}
        style={{
          width: "100%",
          padding: "8px",
          borderRadius: "var(--radius-control)",
          border: "none",
          background: dirty && !busy ? "var(--accent)" : "var(--border)",
          color: dirty && !busy ? "var(--accent-fg)" : "var(--text-subtle)",
          fontSize: "var(--size-meta)",
          fontWeight: 600,
          cursor: dirty && !busy ? "pointer" : "default",
        }}
      >
        Save
      </button>
    </section>
  );
}
