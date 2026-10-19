"""End-to-end: drive the running server over HTTP, as a client would."""

import json
import os
import urllib.error
import urllib.request

BASE = f"http://127.0.0.1:{os.environ.get('PORT', '8000')}"


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


assert post("/api/todos", {"title": "ship it"}) == 201
assert post("/api/todos", {"title": ""}) == 400
with urllib.request.urlopen(BASE + "/api/todos") as r:
    items = json.load(r)
assert [i["title"] for i in items] == ["ship it"], items
print("e2e ok")
