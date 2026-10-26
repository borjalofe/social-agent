"""FastAPI app factory: Siren home entry behind JWT access tokens."""

from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from social_agent.auth.jwt_authn import AccessClaims, JwtAuthn, JwtAuthnError
from social_agent.auth.siren_authz import SirenActionAuthz
from social_agent.siren.home import SIREN_MEDIA_TYPE, build_home


def create_app(
    *,
    authn: JwtAuthn,
    authz: SirenActionAuthz | None = None,
) -> FastAPI:
    """Build the API. Inject `JwtAuthn` (tests) or wire from env at process start."""
    action_authz = authz if authz is not None else SirenActionAuthz()
    app = FastAPI(title="social-agent", docs_url=None, redoc_url=None)
    app.state.authn = authn
    app.state.authz = action_authz

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

    @app.get("/")
    def home(
        request: Request,
        claims: Annotated[AccessClaims, Depends(require_access)],
    ) -> JSONResponse:
        entity = build_home(claims.user_id, email=claims.email)
        # Home is the caller's own entry; still run authz so actions stay filtered.
        authz_layer: SirenActionAuthz = request.app.state.authz
        authorized = authz_layer.authorize_entity(
            entity,
            claims.user_id,
            resource_owner_id=claims.user_id,
        )
        return JSONResponse(content=authorized, media_type=SIREN_MEDIA_TYPE)

    return app
