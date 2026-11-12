from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from ..adapters.postgres import PostgresRepository
from ..http.context import RequestContext
from ..http.dependencies import authenticated_context
from ..http.errors import ApiError
from .access import PlatformAccessRepository
from .service import PlatformService


class PlatformRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request):
            try:
                response = await original(request)
            except ApiError as error:
                return JSONResponse(
                    {
                        "error": {
                            "code": error.code,
                            "message": error.message,
                            "request_id": getattr(request.state, "correlation_id", ""),
                            "details": error.details,
                        }
                    },
                    status_code=error.status_code,
                    headers={"Cache-Control": "no-store"},
                )
            response.headers["Cache-Control"] = "no-store"
            return response

        return handler


def create_platform_router(
    access: PlatformAccessRepository | None = None, *, database_url: str | None = None
) -> APIRouter:
    service = PlatformService(
        access
        or PlatformAccessRepository(PostgresRepository(database_url) if database_url else None)
    )
    router = APIRouter(prefix="/v1/platform", tags=["platform"], route_class=PlatformRoute)

    @router.post("/brain/command")
    async def brain_command(
        command: dict, # Assuming command will be a JSON object with a 'prompt' field
        response: Response,
        identity: Annotated[RequestContext, Depends(authenticated_context)],
    ):
        response.headers["Cache-Control"] = "no-store"
        return await service.brain_command(identity, command.get("prompt", ""))

    @router.get("/context")
    async def context(
        response: Response, identity: Annotated[RequestContext, Depends(authenticated_context)]
    ):
        response.headers["Cache-Control"] = "no-store"
        return await service.context(identity)

    @router.get("/modules/{module_key}")
    async def module(
        module_key: str,
        response: Response,
        identity: Annotated[RequestContext, Depends(authenticated_context)],
    ):
        response.headers["Cache-Control"] = "no-store"
        return await service.module(identity, module_key)

    @router.get("/skills")
    async def skills(
        response: Response, identity: Annotated[RequestContext, Depends(authenticated_context)]
    ):
        response.headers["Cache-Control"] = "no-store"
        return await service.skills(identity)

    @router.get("/portfolio")
    async def portfolio(
        response: Response, identity: Annotated[RequestContext, Depends(authenticated_context)]
    ):
        response.headers["Cache-Control"] = "no-store"
        return await service.portfolio(identity)

    return router
