// Web Push subscribe/unsubscribe helpers for the mobile "Enable notifications"
// control. All browser API access is guarded so this module is safe to import
// from server components / during SSR (Notification, ServiceWorkerContainer,
// and PushManager only exist in a real browser).
import { api } from "./api";

export type PushState = "unsupported" | "default" | "subscribed" | "denied";

export function isPushSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    "Notification" in window &&
    "serviceWorker" in navigator &&
    "PushManager" in window
  );
}

// Standard Web Push VAPID-key decoder: the server hands back a URL-safe
// base64 public key; PushManager.subscribe() wants it as a Uint8Array.
export function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  // Explicit ArrayBuffer (not the wider ArrayBufferLike the bare constructor
  // infers under the esnext lib) — PushManager.subscribe() wants BufferSource.
  const outputArray: Uint8Array<ArrayBuffer> = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i++) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

// Current permission/subscription state, for populating the control on mount.
export async function getPushState(): Promise<PushState> {
  if (!isPushSupported()) return "unsupported";
  if (Notification.permission === "denied") return "denied";
  const reg = await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.getSubscription();
  return sub ? "subscribed" : "default";
}

export async function enablePush(): Promise<PushState> {
  if (!isPushSupported()) return "unsupported";
  const permission = await Notification.requestPermission();
  if (permission !== "granted") return permission === "denied" ? "denied" : "default";

  const reg = await navigator.serviceWorker.ready;
  let sub = await reg.pushManager.getSubscription();
  if (!sub) {
    const key = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY || (await api.push.vapidKey()).data.key;
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(key),
    });
  }
  await api.push.subscribe(sub.toJSON());
  return "subscribed";
}

export async function disablePush(): Promise<PushState> {
  if (!isPushSupported()) return "unsupported";
  const reg = await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.getSubscription();
  if (sub) {
    await sub.unsubscribe();
    await api.push.unsubscribe(sub.endpoint);
  }
  return "default";
}
