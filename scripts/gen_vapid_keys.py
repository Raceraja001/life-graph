"""Generate a VAPID keypair for Web Push. Run once; store the private key in the
VM's .env.production (LIFE_GRAPH_VAPID_PRIVATE_KEY) and the public key in both the
backend env and the dashboard build env (NEXT_PUBLIC_VAPID_PUBLIC_KEY).

Verified against py_vapid 1.9.4 (bundled by pywebpush 2.3.0): that version's
Vapid02 has no `private_key_to_base64url` / `public_key_to_base64url` helpers,
so the raw EC key material is exported and base64url-encoded by hand, matching
how `py_vapid.Vapid02.sign()` encodes the public key internally.
"""

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid02
from py_vapid.utils import b64urlencode


def main() -> None:
    v = Vapid02()
    v.generate_keys()

    # Private key: raw 32-byte big-endian scalar, base64url-encoded.
    private_value = v.private_key.private_numbers().private_value
    private_raw = private_value.to_bytes(32, "big")
    private_b64url = b64urlencode(private_raw)

    # Public key: raw 65-byte uncompressed EC point, base64url-encoded.
    public_raw = v.public_key.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    public_b64url = b64urlencode(public_raw)

    print("VAPID_PRIVATE_KEY:", private_b64url)
    print("VAPID_PUBLIC_KEY:", public_b64url)


if __name__ == "__main__":
    main()
