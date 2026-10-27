"""FastAPI app factory: Siren resources behind JWT access tokens."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from social_agent.auth.jwt_authn import AccessClaims, JwtAuthn, JwtAuthnError
from social_agent.auth.siren_authz import ForbiddenError, SirenActionAuthz
from social_agent.crypto import FernetBoxError, seal
from social_agent.siren.canal_rules import (
    CanalRuleStore,
    InMemoryCanalRuleStore,
    build_canal_rule_item,
    build_canal_rules_collection,
)
from social_agent.siren.context import (
    ContextStore,
    InMemoryContextStore,
    build_context_collection,
    build_context_item,
)
from social_agent.siren.home import SIREN_MEDIA_TYPE, build_home
from social_agent.siren.social_accounts import (
    InMemorySocialAccountStore,
    SocialAccountStore,
    build_social_account_item,
    build_social_accounts_collection,
)
from social_agent.siren.user import build_user
from social_agent.siren.voice import InMemoryVoiceStore, VoiceStore, build_voice


class VoiceUpdate(BaseModel):
    body: str = Field(min_length=0)


class ContextWrite(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=0)


class CanalRuleCreate(BaseModel):
    channel: str = Field(min_length=1, max_length=64)
    body: str = Field(min_length=0)


class CanalRuleUpdate(BaseModel):
    body: str = Field(min_length=0)


class SocialAccountCreate(BaseModel):
    channel: str = Field(min_length=1, max_length=64)
    handle: str = Field(min_length=1, max_length=255)
    credentials: str = Field(min_length=1)


class SocialAccountUpdate(BaseModel):
    handle: str = Field(min_length=1, max_length=255)
    credentials: str = Field(min_length=1)


def create_app(
    *,
    authn: JwtAuthn,
    authz: SirenActionAuthz | None = None,
    voice_store: VoiceStore | None = None,
    context_store: ContextStore | None = None,
    canal_rule_store: CanalRuleStore | None = None,
    social_account_store: SocialAccountStore | None = None,
    fernet_key: str | bytes | None = None,
) -> FastAPI:
    """Build the API. Inject `JwtAuthn` (tests) or wire from env at process start."""
    action_authz = authz if authz is not None else SirenActionAuthz()
    voices: VoiceStore = voice_store if voice_store is not None else InMemoryVoiceStore()
    contexts: ContextStore = context_store if context_store is not None else InMemoryContextStore()
    canal_rules: CanalRuleStore = (
        canal_rule_store if canal_rule_store is not None else InMemoryCanalRuleStore()
    )
    social_accounts: SocialAccountStore = (
        social_account_store if social_account_store is not None else InMemorySocialAccountStore()
    )
    app = FastAPI(title="social-agent", docs_url=None, redoc_url=None)
    app.state.authn = authn
    app.state.authz = action_authz
    app.state.voice_store = voices
    app.state.context_store = contexts
    app.state.canal_rule_store = canal_rules
    app.state.social_account_store = social_accounts
    app.state.fernet_key = fernet_key

    def require_access(
        authorization: Annotated[str | None, Header()] = None,
    ) -> AccessClaims:
        if authorization is None:
            raise HTTPException(status_code=401, detail="missing_authorization")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=401, detail="invalid_authorization")
        try:
            return authn.verify_access(token)
        except JwtAuthnError as exc:
            raise HTTPException(status_code=401, detail="invalid_token") from exc

    def siren_response(
        request: Request,
        claims: AccessClaims,
        entity: dict[str, Any],
    ) -> JSONResponse:
        authz_layer: SirenActionAuthz = request.app.state.authz
        authorized = authz_layer.authorize_entity(
            entity,
            claims.user_id,
            resource_owner_id=claims.user_id,
        )
        return JSONResponse(content=authorized, media_type=SIREN_MEDIA_TYPE)

    @app.get("/")
    def home(
        request: Request,
        claims: Annotated[AccessClaims, Depends(require_access)],
    ) -> JSONResponse:
        entity = build_home(claims.user_id, email=claims.email)
        return siren_response(request, claims, entity)

    @app.get("/user")
    def user(
        request: Request,
        claims: Annotated[AccessClaims, Depends(require_access)],
    ) -> JSONResponse:
        entity = build_user(claims.user_id, email=claims.email)
        return siren_response(request, claims, entity)

    @app.get("/voice")
    def voice_get(
        request: Request,
        claims: Annotated[AccessClaims, Depends(require_access)],
    ) -> JSONResponse:
        store: VoiceStore = request.app.state.voice_store
        record = store.get(claims.user_id)
        body = record.body if record is not None else ""
        entity = build_voice(claims.user_id, body=body)
        return siren_response(request, claims, entity)

    @app.put("/voice")
    def voice_put(
        request: Request,
        payload: VoiceUpdate,
        claims: Annotated[AccessClaims, Depends(require_access)],
    ) -> JSONResponse:
        authz_layer: SirenActionAuthz = request.app.state.authz
        try:
            authz_layer.enforce(
                claims.user_id,
                resource_owner_id=claims.user_id,
                action="update-voice",
            )
        except ForbiddenError as exc:
            raise HTTPException(status_code=exc.status_code, detail="forbidden") from exc
        store: VoiceStore = request.app.state.voice_store
        record = store.put(claims.user_id, payload.body)
        entity = build_voice(claims.user_id, body=record.body)
        return siren_response(request, claims, entity)

    def enforce_action(request: Request, claims: AccessClaims, action: str) -> None:
        authz_layer: SirenActionAuthz = request.app.state.authz
        try:
            authz_layer.enforce(
                claims.user_id,
                resource_owner_id=claims.user_id,
                action=action,
            )
        except ForbiddenError as exc:
            raise HTTPException(status_code=exc.status_code, detail="forbidden") from exc

    @app.get("/context")
    def context_list(
        request: Request,
        claims: Annotated[AccessClaims, Depends(require_access)],
    ) -> JSONResponse:
        store: ContextStore = request.app.state.context_store
        entity = build_context_collection(claims.user_id, store.list(claims.user_id))
        return siren_response(request, claims, entity)

    @app.post("/context")
    def context_create(
        request: Request,
        payload: ContextWrite,
        claims: Annotated[AccessClaims, Depends(require_access)],
    ) -> JSONResponse:
        enforce_action(request, claims, "add-context")
        store: ContextStore = request.app.state.context_store
        record = store.create(claims.user_id, title=payload.title, body=payload.body)
        return siren_response(request, claims, build_context_item(record))

    @app.get("/context/{doc_id}")
    def context_get(
        request: Request,
        doc_id: UUID,
        claims: Annotated[AccessClaims, Depends(require_access)],
    ) -> JSONResponse:
        store: ContextStore = request.app.state.context_store
        record = store.get(claims.user_id, doc_id)
        if record is None:
            raise HTTPException(status_code=404, detail="not_found")
        return siren_response(request, claims, build_context_item(record))

    @app.put("/context/{doc_id}")
    def context_put(
        request: Request,
        doc_id: UUID,
        payload: ContextWrite,
        claims: Annotated[AccessClaims, Depends(require_access)],
    ) -> JSONResponse:
        enforce_action(request, claims, "update-context")
        store: ContextStore = request.app.state.context_store
        record = store.update(
            claims.user_id,
            doc_id,
            title=payload.title,
            body=payload.body,
        )
        if record is None:
            raise HTTPException(status_code=404, detail="not_found")
        return siren_response(request, claims, build_context_item(record))

    @app.get("/canal-rules")
    def canal_rules_list(
        request: Request,
        claims: Annotated[AccessClaims, Depends(require_access)],
    ) -> JSONResponse:
        store: CanalRuleStore = request.app.state.canal_rule_store
        entity = build_canal_rules_collection(claims.user_id, store.list(claims.user_id))
        return siren_response(request, claims, entity)

    @app.post("/canal-rules")
    def canal_rules_create(
        request: Request,
        payload: CanalRuleCreate,
        claims: Annotated[AccessClaims, Depends(require_access)],
    ) -> JSONResponse:
        enforce_action(request, claims, "add-canal-rule")
        store: CanalRuleStore = request.app.state.canal_rule_store
        record = store.create(
            claims.user_id,
            channel=payload.channel,
            body=payload.body,
        )
        if record is None:
            raise HTTPException(status_code=409, detail="channel_exists")
        return siren_response(request, claims, build_canal_rule_item(record))

    @app.get("/canal-rules/{channel}")
    def canal_rules_get(
        request: Request,
        channel: str,
        claims: Annotated[AccessClaims, Depends(require_access)],
    ) -> JSONResponse:
        store: CanalRuleStore = request.app.state.canal_rule_store
        record = store.get(claims.user_id, channel)
        if record is None:
            raise HTTPException(status_code=404, detail="not_found")
        return siren_response(request, claims, build_canal_rule_item(record))

    @app.put("/canal-rules/{channel}")
    def canal_rules_put(
        request: Request,
        channel: str,
        payload: CanalRuleUpdate,
        claims: Annotated[AccessClaims, Depends(require_access)],
    ) -> JSONResponse:
        enforce_action(request, claims, "update-canal-rule")
        store: CanalRuleStore = request.app.state.canal_rule_store
        record = store.update(claims.user_id, channel, body=payload.body)
        if record is None:
            raise HTTPException(status_code=404, detail="not_found")
        return siren_response(request, claims, build_canal_rule_item(record))

    def seal_credentials(request: Request, plaintext: str) -> str:
        try:
            return seal(plaintext, key=request.app.state.fernet_key)
        except FernetBoxError as exc:
            raise HTTPException(status_code=500, detail="fernet_unavailable") from exc

    @app.get("/social-accounts")
    def social_accounts_list(
        request: Request,
        claims: Annotated[AccessClaims, Depends(require_access)],
    ) -> JSONResponse:
        store: SocialAccountStore = request.app.state.social_account_store
        entity = build_social_accounts_collection(
            claims.user_id,
            store.list(claims.user_id),
        )
        return siren_response(request, claims, entity)

    @app.post("/social-accounts")
    def social_accounts_create(
        request: Request,
        payload: SocialAccountCreate,
        claims: Annotated[AccessClaims, Depends(require_access)],
    ) -> JSONResponse:
        enforce_action(request, claims, "add-social-account")
        store: SocialAccountStore = request.app.state.social_account_store
        record = store.create(
            claims.user_id,
            channel=payload.channel,
            handle=payload.handle,
            credentials_encrypted=seal_credentials(request, payload.credentials),
        )
        if record is None:
            raise HTTPException(status_code=409, detail="channel_exists")
        return siren_response(request, claims, build_social_account_item(record))

    @app.get("/social-accounts/{channel}")
    def social_accounts_get(
        request: Request,
        channel: str,
        claims: Annotated[AccessClaims, Depends(require_access)],
    ) -> JSONResponse:
        store: SocialAccountStore = request.app.state.social_account_store
        record = store.get(claims.user_id, channel)
        if record is None:
            raise HTTPException(status_code=404, detail="not_found")
        return siren_response(request, claims, build_social_account_item(record))

    @app.put("/social-accounts/{channel}")
    def social_accounts_put(
        request: Request,
        channel: str,
        payload: SocialAccountUpdate,
        claims: Annotated[AccessClaims, Depends(require_access)],
    ) -> JSONResponse:
        enforce_action(request, claims, "update-social-account")
        store: SocialAccountStore = request.app.state.social_account_store
        record = store.update(
            claims.user_id,
            channel,
            handle=payload.handle,
            credentials_encrypted=seal_credentials(request, payload.credentials),
        )
        if record is None:
            raise HTTPException(status_code=404, detail="not_found")
        return siren_response(request, claims, build_social_account_item(record))

    return app
