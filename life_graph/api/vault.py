"""The vault's endpoints: put a secret in, see what is in there, take one out.

``services/vault.py`` holds the reasoning; this router is deliberately thin
and, more importantly, **write-and-metadata only**. There is no endpoint that
returns a secret's value: resolution happens in-process, in the code that
fills a form, through ``vault.resolve_for_origin``, which checks the target
origin first. An HTTP route back to plaintext would turn every one of those
checks into a formality.

``POST /vault/secrets`` stores a value and answers with its ``vault://``
handle (the only time the caller learns the handle is irrelevant — the handle
is not a secret, which is the point). ``GET /vault/secrets`` lists metadata,
``DELETE /vault/secrets/{id}`` revokes a secret and destroys its ciphertext.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from life_graph.api.responses import success_response
from life_graph.core.tenant import get_current_tenant_id
from life_graph.storage.database import async_session

router = APIRouter(prefix="/vault", tags=["vault"])


class SecretCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=120, description="What the owner calls it")
    value: str = Field(
        ..., min_length=1, max_length=8192, description="Stored encrypted, never returned"
    )
    allowed_origins: list[str] = Field(
        ..., min_length=1, description="Sites this secret may be filled into ('*.bank.com' allowed)"
    )
    secret_type: str = Field(
        "generic", description="generic | password | otp | card | token | note"
    )
    one_use: bool = Field(False, description="Spend it on first use (an OTP)")


@router.post(
    "/secrets", status_code=status.HTTP_201_CREATED, summary="Store a secret, get a handle"
)
async def create_secret(body: SecretCreate):
    from life_graph.services import vault

    async with async_session() as session:
        try:
            row = await vault.store(
                session,
                get_current_tenant_id(),
                label=body.label,
                value=body.value,
                allowed_origins=body.allowed_origins,
                secret_type=body.secret_type,
                one_use=body.one_use,
            )
        except vault.VaultError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None
        data = vault.to_dict(row)
        await session.commit()
        return success_response(data=data)


@router.get("/secrets", summary="What is in the vault (metadata only — never values)")
async def list_secrets(include_revoked: bool = False):
    from life_graph.services import vault

    async with async_session() as session:
        rows = await vault.list_secrets(session, get_current_tenant_id(), include_revoked)
        return success_response(data=[vault.to_dict(r) for r in rows])


@router.get("/secrets/{secret_id}", summary="One secret's metadata")
async def get_secret(secret_id: str):
    from life_graph.services import vault

    async with async_session() as session:
        try:
            row = await vault.get(session, get_current_tenant_id(), _as_uuid(secret_id))
        except vault.SecretNotFoundError:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "secret not found") from None
        return success_response(data=vault.to_dict(row))


@router.delete("/secrets/{secret_id}", summary="Revoke a secret and destroy its ciphertext")
async def revoke_secret(secret_id: str):
    from life_graph.services import vault

    async with async_session() as session:
        try:
            row = await vault.revoke(session, get_current_tenant_id(), _as_uuid(secret_id))
        except vault.SecretNotFoundError:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "secret not found") from None
        data = vault.to_dict(row)
        await session.commit()
        return success_response(data=data)


def _as_uuid(secret_id: str) -> uuid.UUID:
    """A path id as a UUID; a malformed one is simply not found.

    404 rather than 422: whether a string is a well-formed id is not something
    a caller of this router should learn anything from.
    """
    try:
        return uuid.UUID(secret_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "secret not found") from None
