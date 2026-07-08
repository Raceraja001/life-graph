import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";

const WEBHOOK_SECRET = process.env.WEBHOOK_SECRET || "dev-secret";

function verifyHMAC(payload: string, signature: string): boolean {
  const expected = crypto
    .createHmac("sha256", WEBHOOK_SECRET)
    .update(payload)
    .digest("hex");
  return crypto.timingSafeEqual(
    Buffer.from(signature, "hex"),
    Buffer.from(expected, "hex")
  );
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.text();
    const signature = req.headers.get("x-webhook-signature") || "";

    // In dev mode, skip HMAC verification
    if (process.env.NODE_ENV === "production" && signature) {
      if (!verifyHMAC(body, signature)) {
        return NextResponse.json({ error: "Invalid signature" }, { status: 401 });
      }
    }

    const event = JSON.parse(body);
    console.log(`[webhook] ${event.type}`, event.data);

    // Broadcast to connected clients via SSE or just log for now
    // In future: use a pub/sub mechanism
    return NextResponse.json({ received: true, type: event.type });
  } catch (err) {
    return NextResponse.json({ error: "Invalid payload" }, { status: 400 });
  }
}
