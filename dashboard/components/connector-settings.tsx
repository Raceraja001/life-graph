"use client";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Eye, GitPullRequest, Lock, Mail, Plus, RefreshCw, Trash2, Upload, Users } from "lucide-react";
import {
  api,
  type ConnectorAccount,
  type ConnectorAuth,
  type ConnectorExposure,
  type ConnectorsState,
} from "@/lib/api";

const METHOD_LABEL: Record<ConnectorAuth, string> = {
  none: "Calendar link (secret iCal address)",
  app_password: "App password",
  oauth: "Sign in with Google (read-only)",
  file: "Import a vCard file (.vcf)",
  token: "Access token (read-only, fine-grained)",
};

// The credential field each secret-based method stores.
const SECRET_KEY: Partial<Record<ConnectorAuth, string>> = { none: "url", app_password: "password", token: "token" };

type CloudFieldOption = { name: string; label: string; default: boolean };

const ICONS: Record<string, typeof Mail> = {
  email: Mail,
  calendar: CalendarDays,
  contacts: Users,
  github: GitPullRequest,
};

/** Read a picked file as text in the browser; the server never sees the file itself. */
function readText(file: File): Promise<string> {
  if (file.size > 5_000_000) return Promise.reject(new Error("That file is over 5 MB."));
  return file.text();
}

const STATUS: Record<ConnectorAccount["status"], { label: string; cls: string }> = {
  ok: { label: "Synced", cls: "bg-success-soft text-success" },
  never_synced: { label: "Waiting for first sync", cls: "bg-surface-3 text-ink-mid" },
  error: { label: "Sync failing", cls: "bg-warning-soft text-ink" },
  reauth_needed: { label: "Reconnect needed", cls: "bg-danger-soft text-danger" },
};

function ago(iso: string | null): string {
  if (!iso) return "never";
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const h = Math.round(mins / 60);
  return h < 48 ? `${h} h ago` : `${Math.round(h / 24)} d ago`;
}

/** Banner for ?connector=ok|error&message=… after the Google sign-in round trip. */
function useOAuthResult(): { status: string; message: string } | null {
  const [result, setResult] = useState<{ status: string; message: string } | null>(null);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const status = params.get("connector");
    if (!status) return;
    // One-shot read of the URL the OAuth callback redirected to.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setResult({ status, message: params.get("message") || "" });
    window.history.replaceState(null, "", window.location.pathname);
  }, []);
  return result;
}

export function ConnectorSettings() {
  const qc = useQueryClient();
  const state = useQuery({ queryKey: ["connectors"], queryFn: api.connectors.state, refetchInterval: 15000 });
  const [adding, setAdding] = useState(false);
  const oauth = useOAuthResult();
  const refresh = () => qc.invalidateQueries({ queryKey: ["connectors"] });

  return (
    <div className="bg-surface border border-line rounded-xl p-6 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-ink">Connected accounts</h3>
          <p className="text-xs text-ink-mid mt-0.5">
            Calendar, email, contacts and GitHub, read-only. Mail bodies never leave this machine; cloud chat sees
            only what each account allows.
          </p>
        </div>
        {!adding && (
          <button
            onClick={() => setAdding(true)}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-accent text-accent-fg hover:bg-accent-hover shrink-0"
          >
            <Plus className="w-3.5 h-3.5" /> Add account
          </button>
        )}
      </div>

      {oauth && (
        <p className={`text-sm rounded-lg px-3 py-2 ${oauth.status === "ok" ? "bg-success-soft text-success" : "bg-danger-soft text-danger"}`}>
          {oauth.message}
        </p>
      )}
      {state.isError && <p className="text-sm text-danger">Cannot load connectors — check API connection</p>}

      {adding && state.data && (
        <AddAccount state={state.data} onDone={() => { setAdding(false); refresh(); }} />
      )}

      <div className="divide-y divide-line border border-line rounded-lg">
        {(state.data?.accounts ?? []).length === 0 && !state.isLoading ? (
          <p className="px-4 py-4 text-sm text-ink-low">No accounts yet.</p>
        ) : (
          state.data?.accounts.map((a) => (
            <AccountRow
              key={a.id}
              account={a}
              options={state.data?.connectors.find((c) => c.name === a.connector)?.cloud_field_options ?? []}
              onChange={refresh}
            />
          ))
        )}
      </div>
    </div>
  );
}

function AccountRow({
  account: a,
  options,
  onChange,
}: {
  account: ConnectorAccount;
  options: CloudFieldOption[];
  onChange: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [newSecret, setNewSecret] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [editingFields, setEditingFields] = useState(false);
  const status = STATUS[a.status];
  const Icon = ICONS[a.connector] ?? CalendarDays;
  const isFile = a.auth_method === "file";
  const counts = Object.entries(a.items)
    .map(([k, n]) => (k === "code" ? `${n} ${n === 1 ? "PR/issue" : "PRs/issues"}` : `${n} ${k}${n === 1 ? "" : "s"}`))
    .join(", ");
  const shared = (a.settings.cloud_fields as string[] | undefined) ?? options.filter((o) => o.default).map((o) => o.name);

  const importFile = (file: File | undefined) =>
    file &&
    run(async () => {
      const result = await api.connectors.importFile(a.id, await readText(file));
      setNotice(`Imported ${result.fetched} contacts (${result.new} new, ${result.deleted} removed).`);
    });

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await fn();
      onChange();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const reconnect = () =>
    a.auth_method === "oauth"
      ? run(async () => { window.location.href = await api.connectors.oauthStart(a.id); })
      : setNewSecret("");

  return (
    <div className="px-4 py-3 space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <Icon className="w-4 h-4 text-ink-mid shrink-0" />
        <span className="text-sm font-medium text-ink">{a.display_name}</span>
        <span className="text-xs text-ink-low">{String(a.settings.username ?? "")}</span>
        <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${status.cls}`}>
          {a.enabled ? status.label : "Disabled"}
        </span>
        {a.exposure === "local_only" && (
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-accent-soft text-accent-text font-medium flex items-center gap-1">
            <Lock className="w-3 h-3" /> Local only
          </span>
        )}
      </div>
      <p className="text-xs text-ink-mid">
        {METHOD_LABEL[a.auth_method]} · {isFile ? "imported" : "synced"} {ago(a.last_sync_at)}
        {counts && ` · ${counts}`}
      </p>
      {options.length > 0 && a.exposure !== "local_only" && (
        <p className="text-xs text-ink-low">
          Cloud chat sees: {options.filter((o) => shared.includes(o.name)).map((o) => o.label.toLowerCase()).join(", ") || "nothing"}
        </p>
      )}
      {a.last_error && <p className="text-xs text-danger">{a.last_error}</p>}
      {error && <p className="text-xs text-danger">{error}</p>}
      {notice && <p className="text-xs text-success">{notice}</p>}

      {editingFields && (
        <CloudFields
          options={options}
          value={shared}
          busy={busy}
          onCancel={() => setEditingFields(false)}
          onSave={(fields) =>
            run(async () => {
              await api.connectors.update(a.id, { settings: { ...a.settings, cloud_fields: fields } });
              setEditingFields(false);
            })
          }
        />
      )}

      {newSecret !== null && (
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="password"
            autoComplete="off"
            value={newSecret}
            onChange={(e) => setNewSecret(e.target.value)}
            placeholder={
              a.auth_method === "none" ? "New calendar link" : a.auth_method === "token" ? "New access token" : "New app password"
            }
            className="bg-surface border border-line rounded-lg px-3 py-1.5 text-sm text-ink flex-1 min-w-[12rem]"
          />
          <button
            disabled={!newSecret || busy}
            onClick={() =>
              run(async () => {
                const key = SECRET_KEY[a.auth_method] ?? "password";
                await api.connectors.setCredential(a.id, a.auth_method, { [key]: newSecret || "" });
                setNewSecret(null);
                await api.connectors.sync(a.id);
              })
            }
            className="text-xs px-3 py-1.5 rounded-lg bg-accent text-accent-fg disabled:opacity-50"
          >
            Save
          </button>
          <button onClick={() => setNewSecret(null)} className="text-xs px-2 py-1.5 text-ink-mid">
            Cancel
          </button>
        </div>
      )}

      <div className="flex flex-wrap gap-1.5">
        {isFile ? (
          <label
            className={`flex items-center gap-1 text-xs px-2.5 py-1 rounded-md border border-line text-ink-mid ${busy ? "opacity-50" : "hover:bg-surface-3 cursor-pointer"}`}
          >
            <Upload className="w-3 h-3" /> Import vCard
            <input
              type="file"
              accept=".vcf,text/vcard,text/x-vcard"
              className="sr-only"
              disabled={busy}
              onChange={(e) => {
                importFile(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
          </label>
        ) : (
          <>
            <SmallButton disabled={busy || !a.enabled} onClick={() => run(() => api.connectors.sync(a.id))}>
              <RefreshCw className="w-3 h-3" /> Sync now
            </SmallButton>
            <SmallButton disabled={busy} onClick={reconnect}>
              {a.status === "reauth_needed" ? "Reconnect" : "Change credential"}
            </SmallButton>
          </>
        )}
        {options.length > 0 && a.exposure !== "local_only" && (
          <SmallButton disabled={busy} onClick={() => setEditingFields(true)}>
            <Eye className="w-3 h-3" /> Cloud visibility
          </SmallButton>
        )}
        {a.connector === "github" && a.exposure !== "local_only" && (
          <SmallButton
            disabled={busy}
            onClick={() =>
              run(() =>
                api.connectors.update(a.id, {
                  settings: { ...a.settings, share_private_titles: !a.settings.share_private_titles },
                })
              )
            }
          >
            {a.settings.share_private_titles ? "Private repos: counts only" : "Share private repo titles"}
          </SmallButton>
        )}
        <SmallButton
          disabled={busy}
          onClick={() =>
            run(() =>
              api.connectors.update(a.id, { exposure: a.exposure === "local_only" ? "standard" : "local_only" })
            )
          }
        >
          {a.exposure === "local_only" ? (options.length ? "Allow cloud access" : "Allow cloud summaries") : "Make local only"}
        </SmallButton>
        <SmallButton disabled={busy} onClick={() => run(() => api.connectors.update(a.id, { enabled: !a.enabled }))}>
          {a.enabled ? "Disable" : "Enable"}
        </SmallButton>
        <SmallButton
          disabled={busy}
          danger
          onClick={() => {
            if (confirm(`Remove ${a.display_name}? Its indexed items are deleted; the source account is not touched.`)) {
              run(() => api.connectors.remove(a.id));
            }
          }}
        >
          <Trash2 className="w-3 h-3" /> Remove
        </SmallButton>
      </div>
    </div>
  );
}

function SmallButton({
  children,
  onClick,
  disabled,
  danger,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  danger?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`flex items-center gap-1 text-xs px-2.5 py-1 rounded-md border border-line hover:bg-surface-3 disabled:opacity-50 ${danger ? "text-danger" : "text-ink-mid"}`}
    >
      {children}
    </button>
  );
}

/** Which contact fields cloud chat may see, for one account. */
function CloudFields({
  options,
  value,
  busy,
  onSave,
  onCancel,
  inline,
}: {
  options: CloudFieldOption[];
  value: string[];
  busy?: boolean;
  onSave: (fields: string[]) => void;
  onCancel?: () => void;
  inline?: boolean;
}) {
  const [chosen, setChosen] = useState<string[]>(value);
  const toggle = (name: string, on: boolean) => {
    const next = on ? [...chosen, name] : chosen.filter((n) => n !== name);
    setChosen(next);
    if (inline) onSave(next);
  };
  return (
    <div className="border border-line rounded-lg p-3 space-y-2 bg-surface-2">
      <p className="text-xs text-ink-mid">
        What cloud chat (jarvis, Telegram, push) may see of these contacts. Everything stays available to local
        models. Birth year and relations never leave this machine.
      </p>
      <div className="grid gap-1.5 sm:grid-cols-2">
        {options.map((o) => (
          <label key={o.name} className="flex items-center gap-2 text-xs text-ink">
            <input
              type="checkbox"
              checked={chosen.includes(o.name)}
              onChange={(e) => toggle(o.name, e.target.checked)}
            />
            {o.label}
            {!o.default && <span className="text-ink-low">(off by default)</span>}
          </label>
        ))}
      </div>
      {!chosen.includes("name") && (
        <p className="text-xs text-ink-low">Without names, cloud chat only sees how many contacts there are.</p>
      )}
      {!inline && (
        <div className="flex gap-2">
          <button
            disabled={busy}
            onClick={() => onSave(chosen)}
            className="text-xs px-3 py-1.5 rounded-lg bg-accent text-accent-fg disabled:opacity-50"
          >
            Save
          </button>
          <button onClick={onCancel} className="text-xs px-2 py-1.5 text-ink-mid">
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}

const field =
  "bg-surface border border-line rounded-lg px-3 py-2 text-sm text-ink placeholder-ink-low focus:outline-none focus:border-accent w-full";

function AddAccount({ state, onDone }: { state: ConnectorsState; onDone: () => void }) {
  const [connector, setConnector] = useState<string>("email");
  const [displayName, setDisplayName] = useState("");
  const [username, setUsername] = useState("");
  const [admin, setAdmin] = useState(false);
  const [method, setMethod] = useState<ConnectorAuth>("app_password");
  const [exposure, setExposure] = useState<ConnectorExposure>("standard");
  const [secret, setSecret] = useState("");
  const [host, setHost] = useState("");
  const [clientJson, setClientJson] = useState("");
  const [reason, setReason] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [cloudFields, setCloudFields] = useState<string[] | null>(null);
  const [sharePrivate, setSharePrivate] = useState(false);
  const info = state.connectors.find((c) => c.name === connector);
  const methods = info?.auth_methods ?? [];
  const options = info?.cloud_field_options ?? [];
  const fields = cloudFields ?? options.filter((o) => o.default).map((o) => o.name);
  const isContacts = connector === "contacts";

  // Keep the chosen method valid for the chosen connector.
  useEffect(() => {
    if (!methods.includes(method) && methods.length) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setMethod(methods[0]);
    }
  }, [connector, methods, method]);

  const suggest = async () => {
    if (!username.includes("@")) return;
    try {
      const rec = await api.connectors.recommend(username, admin);
      setReason(rec.reason);
      if (connector === "email" || rec.auth_method === "oauth") {
        setMethod(connector === "calendar" && rec.auth_method !== "oauth" ? "none" : rec.auth_method);
      }
      if (rec.exposure) setExposure(rec.exposure);
    } catch {
      /* a suggestion is optional */
    }
  };

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      if (method === "oauth" && !state.google_client_configured) {
        await api.connectors.setGoogleClient(JSON.parse(clientJson));
      }
      const settings: Record<string, unknown> = username ? { username } : {};
      if (options.length) settings.cloud_fields = fields;
      if (connector === "github") {
        settings.share_private_titles = sharePrivate;
        if (host) settings.api_url = host;
      }
      if (connector === "email" && method === "app_password" && host) settings.host = host;
      if (connector === "calendar") settings.my_addresses = username;
      const secretKey = SECRET_KEY[method];
      const secretBody: Record<string, string> | undefined = secretKey ? { [secretKey]: secret.trim() } : undefined;
      const account = await api.connectors.create({
        connector,
        display_name: displayName || username || info?.display_name || connector,
        auth_method: method,
        settings,
        exposure,
        secret: secretBody,
      });
      if (method === "oauth") {
        window.location.href = await api.connectors.oauthStart(account.id);
        return;
      }
      if (method === "file") {
        if (file) await api.connectors.importFile(account.id, await readText(file));
        onDone();
        return;
      }
      await api.connectors.sync(account.id);
      onDone();
    } catch (e) {
      setError(e instanceof SyntaxError ? "The Google client JSON is not valid JSON." : String(e));
    } finally {
      setBusy(false);
    }
  };

  const needsSecret = SECRET_KEY[method] !== undefined;
  const needsClient = method === "oauth" && !state.google_client_configured;
  const needsUsername = connector === "email";
  const ready =
    (!needsUsername || username.includes("@")) &&
    (!needsSecret || secret) &&
    (method !== "file" || file !== null) &&
    (!needsClient || clientJson.trim().startsWith("{"));

  return (
    <div className="border border-line rounded-lg p-4 space-y-3 bg-surface-2">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="space-y-1 text-xs text-ink-mid">
          Type
          <select value={connector} onChange={(e) => setConnector(e.target.value)} className={field}>
            {state.connectors.map((c) => (
              <option key={c.name} value={c.name}>{c.display_name}</option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-xs text-ink-mid">
          Name
          <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="e.g. Personal, Work" className={field} />
        </label>
        {method !== "file" && method !== "token" && (
          <>
            <label className="space-y-1 text-xs text-ink-mid">
              {isContacts ? "Google account (optional)" : "Email address"}
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                onBlur={suggest}
                placeholder="you@example.com"
                className={field}
              />
            </label>
            <label className="flex items-center gap-2 text-xs text-ink-mid pt-5">
              <input type="checkbox" checked={admin} onChange={(e) => { setAdmin(e.target.checked); }} onBlur={suggest} />
              I administer this Google Workspace
            </label>
          </>
        )}
      </div>

      {reason && <p className="text-xs text-ink bg-accent-soft rounded-lg px-3 py-2">Suggested: {reason}</p>}

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="space-y-1 text-xs text-ink-mid">
          How to connect
          <select value={method} onChange={(e) => setMethod(e.target.value as ConnectorAuth)} className={field}>
            {methods.map((m) => (
              <option key={m} value={m}>{METHOD_LABEL[m]}</option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-xs text-ink-mid">
          What cloud chat may see
          <select value={exposure} onChange={(e) => setExposure(e.target.value as ConnectorExposure)} className={field}>
            <option value="standard">
              {isContacts
                ? "The fields chosen below"
                : connector === "github"
                  ? "Titles (private repos as counts)"
                  : "Summaries (never bodies)"}
            </option>
            <option value="local_only">Counts only (local only)</option>
          </select>
        </label>
      </div>

      {method === "token" && (
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="space-y-1 text-xs text-ink-mid">
            Access token
            <input
              type="password"
              autoComplete="off"
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
              placeholder="github_pat_…"
              className={field}
            />
          </label>
          <label className="space-y-1 text-xs text-ink-mid">
            GitHub Enterprise API URL (blank = github.com)
            <input value={host} onChange={(e) => setHost(e.target.value)} placeholder="https://github.example.com/api/v3" className={field} />
          </label>
          <label className="flex items-center gap-2 text-xs text-ink sm:col-span-2">
            <input type="checkbox" checked={sharePrivate} onChange={(e) => setSharePrivate(e.target.checked)} />
            Let cloud chat see private repo names and titles (otherwise they are counts)
          </label>
          <p className="text-xs text-ink-low sm:col-span-2">
            github.com → Settings → Developer settings → Fine-grained tokens → Generate. Repository access: All
            repositories. Permissions, all <strong>read-only</strong>: Pull requests, Issues, Commit statuses,
            Checks. One token per GitHub account or organisation. A token that can write is refused.
          </p>
        </div>
      )}
      {method === "app_password" && connector === "email" && (
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="space-y-1 text-xs text-ink-mid">
            App password
            <input type="password" autoComplete="off" value={secret} onChange={(e) => setSecret(e.target.value)} className={field} />
          </label>
          <label className="space-y-1 text-xs text-ink-mid">
            IMAP server (blank = imap.gmail.com)
            <input value={host} onChange={(e) => setHost(e.target.value)} placeholder="imap.gmail.com" className={field} />
          </label>
          <p className="text-xs text-ink-low sm:col-span-2">
            Google Account → Security → 2-Step Verification → App passwords. If that page is missing, the
            account&apos;s admin has disabled app passwords.
          </p>
        </div>
      )}
      {method === "none" && (
        <label className="block space-y-1 text-xs text-ink-mid">
          Calendar link
          <input type="password" autoComplete="off" value={secret} onChange={(e) => setSecret(e.target.value)} placeholder="https://calendar.google.com/calendar/ical/…/basic.ics" className={field} />
          <span className="block text-ink-low">
            Google Calendar → Settings → your calendar → &quot;Secret address in iCal format&quot;. Treat it like a password.
          </span>
        </label>
      )}
      {method === "file" && (
        <label className="block space-y-1 text-xs text-ink-mid">
          Contacts file (.vcf)
          <input
            type="file"
            accept=".vcf,text/vcard,text/x-vcard"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className={field}
          />
          <span className="block text-ink-low">
            contacts.google.com → Export → vCard. Import a newer export any time; it replaces this account&apos;s
            contacts. The file itself is not kept.
          </span>
        </label>
      )}
      {options.length > 0 && exposure === "standard" && (
        <CloudFields options={options} value={fields} onSave={setCloudFields} inline />
      )}
      {needsClient && (
        <label className="block space-y-1 text-xs text-ink-mid">
          Google OAuth client (one-time setup)
          <textarea
            value={clientJson}
            onChange={(e) => setClientJson(e.target.value)}
            rows={4}
            placeholder='Paste the JSON downloaded for a "Desktop app" OAuth client'
            className={`${field} font-mono text-xs`}
          />
          <span className="block text-ink-low">
            Google Cloud Console → APIs &amp; Services: enable the Gmail API, Google Calendar API and People API
            (contacts), create an
            OAuth client of type &quot;Desktop app&quot;, download its JSON. Redirect used: {state.oauth_redirect_uri}
          </span>
        </label>
      )}

      {error && <p className="text-xs text-danger">{error}</p>}
      <div className="flex gap-2">
        <button
          onClick={submit}
          disabled={!ready || busy}
          className="text-sm px-4 py-2 rounded-lg bg-accent text-accent-fg hover:bg-accent-hover disabled:opacity-50"
        >
          {method === "oauth" ? "Continue to Google" : "Connect"}
        </button>
        <button onClick={onDone} className="text-sm px-3 py-2 text-ink-mid">Cancel</button>
      </div>
    </div>
  );
}
