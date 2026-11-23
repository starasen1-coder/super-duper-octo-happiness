"""Read-only API for stored public research records."""
from __future__ import annotations

import hmac
import ipaddress
import os

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from agent_reach.storage.repository import ResearchRepository
from agent_reach.api.routes import health, sources, items, jobs

_bearer = HTTPBearer(auto_error=False)


def _is_loopback(host: str | None) -> bool:
    if not host:
        return False
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host == "localhost"


def create_app(
    *,
    repository: ResearchRepository | None = None,
    api_token: str | None = None,
    database_path: str | None = None,
) -> FastAPI:
    repo = repository or ResearchRepository(
        database_path or os.getenv("AGENT_REACH_DB", "/data/research.sqlite3"),
        readonly=True,
    )
    token = api_token if api_token is not None else os.getenv("AGENT_REACH_API_TOKEN", "")
    app = FastAPI(title="Agent Reach Research API", version="1.0.0", docs_url=None, redoc_url=None)
    app.state.repository = repo

    def require_auth(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    ) -> None:
        if _is_loopback(request.client.host if request.client else None):
            return
        if not token or credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="authentication required")
        if not hmac.compare_digest(credentials.credentials, token):
            raise HTTPException(status_code=401, detail="invalid credentials")

    @app.get("/health")
    def health_check():
        return health.health(repo)

    @app.get("/v1/sources", dependencies=[Depends(require_auth)])
    def get_sources():
        return sources.list_sources(repository=repo)

    @app.get("/v1/items", dependencies=[Depends(require_auth)])
    def get_items(
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        source: str | None = None,
        status: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
    ):
        return items.list_items(
            limit=limit, offset=offset, source=source, status=status,
            from_date=from_date, to_date=to_date, repository=repo
        )

    @app.get("/v1/items/{item_id}", dependencies=[Depends(require_auth)])
    def get_item(item_id: str):
        return items.get_item(item_id, repository=repo)

    @app.get("/v1/jobs", dependencies=[Depends(require_auth)])
    def get_jobs(limit: int = 50):
        return jobs.list_jobs(limit=limit, repository=repo)

    return app
