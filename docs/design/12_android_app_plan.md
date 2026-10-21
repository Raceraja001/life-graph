# Jarvis on Android — Plan

> **Status: proposed** (2026-10-21), for the owner's approval before any build. Follows
> [Jarvis and its workers](11_persona_roster_plan.md): Jarvis is the one assistant; this puts
> it in the owner's pocket.

## Decisions (the owner's, 2026-10-21)

- **Native Android, Kotlin** (Jetpack Compose). Not a wrapped web UI: the later features (SMS,
  share target, background notifications) need native Android, and it keeps the commercial
  Luminaux template out of the app.
- **Tailscale** for reaching the PC from anywhere: a private network between the phone and the
  PC; nothing is exposed to the internet.
- **First version: chat and voice with Jarvis.** Notifications, share-to-capture and bank-SMS
  import come after it.
- **The app replaces Telegram.** Jobs 3, 4, 8 and 9 move into the app (after the first version)
  instead of waiting for a bot token, and Telegram leaves CHARTER invariant 7's list of
  exceptions.

## How it fits

```
Phone (app) ──Tailscale──> PC: tailscale serve (HTTPS, tailnet only) ──> API :8080 (WSL)
   chat  ─────────────────────────────────────────────> Jarvis (services/lead.py)
   voice ── audio ──> local speech-to-text ──> Jarvis ──> local text-to-speech ── audio ──>
```

- **Privacy is the same as everywhere else:** personal requests run on the local model
  (services/lead.py), voice is transcribed and spoken on the PC (faster-whisper; speaches
  for speech), and nothing passes through a third party. The voice path **forces** local
  transcription even if a cloud speech key is ever configured.
- **`tailscale serve`** on Windows gives the PC a private HTTPS address
  (`https://<pc>.<tailnet>.ts.net`) that proxies to the API, so the app gets real TLS and no
  WSL port-forwarding is needed.
- **Each phone gets its own token**, not the master service key: paired once with a short
  code shown in the dashboard, kept in the Android Keystore, revocable from the dashboard if
  the phone is lost. A device token can talk to Jarvis and nothing administrative.

## Work

### Phase 0 — set-up (once)

- Install the build tools: JDK 17 and the Android command-line SDK (about 1.5 GB), plus the
  Gradle wrapper in the project. No Android Studio needed; the owner may install it to browse
  the code.
- `tailscale serve` for the API; Tailscale on the phone, signed in to the same account.
- New repository **life-graph-android** next to the others: closed source, local git only
  until the owner says where it goes.

### Phase 1 — the API side (life-graph PR)

- **AC-1.1 Pairing:** the dashboard shows a one-time 6-digit code (10 minutes);
  `POST /api/v1/devices/pair {code, name}` returns a device token. Tokens are stored hashed,
  listed and revocable (`GET/DELETE /api/v1/devices`). *(integration test)*
- **AC-1.2 Scope:** a device token may use only the Jarvis endpoints below; anything else is
  403. *(integration test)*
- **AC-1.3 Chat:** `POST /api/v1/jarvis/chat {conversation_id?, message}` streams Jarvis's
  reply (the existing chat stream, target jarvis), with the route kind (personal or general)
  in the final event. `GET /api/v1/jarvis/conversations` and their messages. *(integration test)*
- **AC-1.4 Voice:** `POST /api/v1/jarvis/voice` (audio) → transcribed **locally**, answered by
  Jarvis, returns `{heard, reply, audio}` (spoken reply, mp3) in one call. A cloud speech key
  being set does not change this. *(integration test with a stubbed recogniser)*

### Phase 2 — the app, first version

- **AC-2.1 Pair:** first run asks for the PC's Tailscale address and the pairing code; the
  token goes into the Keystore. *(unit test)*
- **AC-2.2 Chat:** a conversation screen with streaming replies, past conversations, and a
  small label on each reply saying whether it ran locally. *(UI test)*
- **AC-2.3 Voice:** hold to talk; the reply is shown and spoken; a tap stops speaking.
  *(UI test with a fake recorder)*
- **AC-2.4 Failure is plain:** off the tailnet, PC asleep or API down → one clear message
  and a retry, never a spinner that never ends. *(unit test)*
- **AC-2.5 Install:** a signed debug APK the owner installs by USB or from a link on the
  tailnet; release signing comes later.

### Later phases (not in the first version)

1. **Notifications** — reminders, the morning brief, outages, study due (Jobs 3, 4, 7, 8). The
   push carries only "something new"; the app fetches the content over the tailnet. The
   choice between self-hosted (ntfy/UnifiedPush, nothing through Google) and Firebase is made
   then.
2. **Share-to-capture** — the app as a share target for photos, links, text and voice notes
   (Job 9).
3. **Bank SMS import** — read bank alerts, with the owner's permission, into the money
   check-in (Job 5).
4. Then Telegram is switched off and CHARTER invariant 7 updated.

## Limits to know now

- Spoken replies use Kokoro (English). Tamil questions are transcribed (whisper handles
  Tamil and code-switching), but a Tamil spoken reply needs a Tamil voice model; that is a
  separate piece of work.
- The PC must be on and reachable: the app does nothing while the PC sleeps (the failure
  message says so).
- Testing: unit and Compose UI tests run on the JVM here; the owner's phone is the real
  device test, since no emulator will run alongside the GPU work.

## Order

Phase 0 → Phase 1 (PR, merged after review) → Phase 2 (installed on the owner's phone and used
for a day) → the later phases in the order above.
