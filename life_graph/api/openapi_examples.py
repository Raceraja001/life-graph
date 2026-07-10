"""OpenAPI response examples for key API endpoints.

Provides reusable response schema definitions with examples
so that ``/docs`` (Swagger UI) shows meaningful response shapes
even though ``response_model`` was removed from endpoints.

Usage in route decorators::

    from life_graph.api.openapi_examples import PAGINATED_MEMORIES, MEMORY_DETAIL

    @router.get("/", responses=PAGINATED_MEMORIES)
    async def list_memories(...):
        ...
"""

from __future__ import annotations

# ── Memory Responses ────────────────────────────────────────────

MEMORY_EXAMPLE = {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "content": "User prefers dark mode interfaces",
    "tags": ["preference", "ui"],
    "importance": 0.75,
    "status": "active",
    "source_type": "conversation",
    "created_at": "2026-07-05T12:00:00Z",
    "updated_at": "2026-07-05T12:00:00Z",
    "access_count": 3,
}

PAGINATED_MEMORIES = {
    200: {
        "description": "Paginated list of memories",
        "content": {
            "application/json": {
                "example": {
                    "data": [MEMORY_EXAMPLE],
                    "meta": {
                        "total": 42,
                        "page_size": 20,
                        "has_more": True,
                        "next_cursor": "eyJrIjoiMjAyNi0wNy0wNVQxMjowMDowMFoiLCJpZCI6ImExYjJjM2Q0In0=",
                    },
                }
            }
        },
    }
}

MEMORY_DETAIL = {
    200: {
        "description": "Memory detail",
        "content": {
            "application/json": {
                "example": {"data": MEMORY_EXAMPLE}
            }
        },
    },
    404: {
        "description": "Memory not found",
        "content": {
            "application/json": {
                "example": {"detail": "Memory a1b2c3d4-... not found"}
            }
        },
    },
}

MEMORY_CREATED = {
    201: {
        "description": "Memories created from input",
        "content": {
            "application/json": {
                "example": {"data": [MEMORY_EXAMPLE]}
            }
        },
    }
}

# ── Search Responses ────────────────────────────────────────────

SEARCH_RESULT = {
    200: {
        "description": "Semantic search results",
        "content": {
            "application/json": {
                "example": {
                    "data": {
                        "memories": [
                            {
                                **MEMORY_EXAMPLE,
                                "similarity": 0.94,
                            }
                        ],
                        "total_count": 1,
                        "query_time_ms": 12.5,
                    }
                }
            }
        },
    }
}

# ── Webhook Responses ───────────────────────────────────────────

WEBHOOK_EXAMPLE = {
    "id": "f1e2d3c4-b5a6-7890-fedc-ba0987654321",
    "url": "https://example.com/webhook",
    "events": "*",
    "active": True,
    "created_at": "2026-07-05T12:00:00Z",
    "last_delivered_at": None,
    "failure_count": 0,
}

WEBHOOK_CREATED = {
    201: {
        "description": "Webhook registered",
        "content": {
            "application/json": {
                "example": {"data": WEBHOOK_EXAMPLE}
            }
        },
    },
    422: {
        "description": "Validation error (missing url, short secret, etc.)",
    },
}

WEBHOOK_LIST = {
    200: {
        "description": "List of registered webhooks",
        "content": {
            "application/json": {
                "example": {
                    "data": [WEBHOOK_EXAMPLE],
                    "meta": {"page_size": 1, "has_more": False},
                }
            }
        },
    }
}

# ── Tenant Responses ────────────────────────────────────────────

TENANT_PROVISIONED = {
    201: {
        "description": "Tenant provisioned",
        "content": {
            "application/json": {
                "example": {
                    "data": {
                        "tenant_id": "acme-corp",
                        "plan": "pro",
                        "status": "active",
                        "provisioned_at": "2026-07-05T12:00:00Z",
                    }
                }
            }
        },
    },
    409: {"description": "Tenant already exists"},
    422: {"description": "Invalid tenant_id or plan"},
}

TENANT_SUMMARY = {
    200: {
        "description": "Tenant summary",
        "content": {
            "application/json": {
                "example": {
                    "data": {
                        "tenant_id": "acme-corp",
                        "plan": "pro",
                        "status": "active",
                        "provisioned_at": "2026-07-05T12:00:00Z",
                        "deactivated_at": None,
                        "memory_count": 1234,
                        "session_count": 56,
                        "usage": {
                            "total_api_calls": 5678,
                            "total_memories_created": 1234,
                            "total_llm_tokens_used": 890000,
                        },
                    }
                }
            }
        },
    },
    404: {"description": "Tenant not found"},
}

# ── Bulk Operation Responses ────────────────────────────────────

BULK_DELETE = {
    200: {
        "description": "Bulk delete result",
        "content": {
            "application/json": {
                "examples": {
                    "dry_run": {
                        "summary": "Dry run (preview)",
                        "value": {
                            "data": {
                                "dry_run": True,
                                "match_count": 42,
                                "filters": {"status": "archived"},
                            }
                        },
                    },
                    "executed": {
                        "summary": "Executed",
                        "value": {
                            "data": {
                                "dry_run": False,
                                "deleted": 42,
                                "filters": {"status": "archived"},
                            }
                        },
                    },
                }
            }
        },
    },
    400: {"description": "No filters provided"},
}

BULK_IMPORT = {
    201: {
        "description": "Bulk import result",
        "content": {
            "application/json": {
                "example": {
                    "data": {
                        "imported": 100,
                        "embedding_job_id": "abc123",
                        "searchable": False,
                    }
                }
            }
        },
    },
    422: {"description": "Validation error (>500 items, empty content, etc.)"},
}

# ── Health Responses ────────────────────────────────────────────

HEALTH_CHECK = {
    200: {
        "description": "System healthy or degraded",
        "content": {
            "application/json": {
                "example": {
                    "status": "healthy",
                    "version": "1.0.0",
                    "environment": "production",
                    "checks": {
                        "postgres": {"status": "healthy", "latency_ms": 1.5},
                        "redis": {"status": "healthy", "latency_ms": 0.8},
                    },
                }
            }
        },
    },
    503: {
        "description": "Critical dependency down",
        "content": {
            "application/json": {
                "example": {
                    "status": "unhealthy",
                    "checks": {
                        "postgres": {
                            "status": "unhealthy",
                            "error": "connection refused",
                            "latency_ms": 5000.0,
                        },
                    },
                }
            }
        },
    },
}
