"""Opaque keyset-pagination cursors.

A cursor is base64(JSON ``{"k": sort_key, "id": item_id}``). The API encodes
them into list responses and the storage layer decodes them into a
``(sort_key, id) <`` predicate, so the helpers live here, below both: they
were in ``api/responses.py``, and ``storage/postgres.py`` imported the API
package just to read a cursor (audit M12). ``api.responses`` re-exports these
same objects, so ``main.py``'s ``InvalidCursorError`` handler still matches.
"""

from __future__ import annotations

import base64
import json


def encode_cursor(sort_key: str, item_id: str) -> str:
    """Encode a cursor from sort key and item ID."""
    payload = json.dumps({"k": sort_key, "id": item_id})
    return base64.urlsafe_b64encode(payload.encode()).decode()


class InvalidCursorError(ValueError):
    """A pagination cursor could not be decoded.

    A malformed cursor is bad client input, not a server fault, so main.py
    maps this to 422. It previously escaped as a bare ValueError and became
    an unhandled 500.
    """


def decode_cursor(cursor: str) -> dict[str, str]:
    """Decode a cursor back to sort key and item ID.

    Returns:
        Dict with 'k' (sort key) and 'id' fields.

    Raises:
        InvalidCursorError: If the cursor is not valid base64 JSON.
    """
    try:
        payload = base64.urlsafe_b64decode(cursor.encode()).decode()
        return json.loads(payload)
    except Exception as exc:
        raise InvalidCursorError("Invalid cursor format") from exc
