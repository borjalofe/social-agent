"""FastAPI app factory: Siren resources behind JWT access tokens."""

from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from social_agent.auth.jwt_authn import AccessClaims, JwtAuthn, JwtAuthnError
from social_agent.auth.siren_authz import ForbiddenError, SirenActionAuthz
from social_agent.siren.home import SIREN_MEDIA_TYPE, build_home
from social_agent.siren.user import build_user
from social_agent.siren.voice import InMemoryVoiceStore, VoiceStore, build_voice


class VoiceUpdate(BaseModel):
    body: str = Field(min_length=0)


def create_app(
    *,
    authn: JwtAuthn,
    authz: SirenActionAuthz | None = None,
    voice_store: VoiceStore | None = None,
) -> FastAPI:
    """Build the API. Inject `JwtAuthn` (tests) or wire from env at process start."""
    action_authz = authz if authz is not None else SirenActionAuthz()
    voices: VoiceStore = voice_store if voice_store is not None else InMemoryVoiceStore()
    app = FastAPI(title="social-agent", docs_url=None, redoc_url=None)
    app.state.authn = authn
    app.state.authz = action_authz
    app.state.voice_store = voices

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

    return app
