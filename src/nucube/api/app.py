from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from nucube.backends.docker import DockerBackend
from nucube.controller.scheduler import Scheduler
from nucube.controller.service import Service, owner_id
from nucube.errors import NucubeError
from nucube.models.schema import Config, Submission, load_config


class BodyLimit:
    def __init__(self, app, limit: int):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        # Buffer only a bounded request, including chunked requests without Content-Length.
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.limit:
                response = JSONResponse(
                    {
                        "error": {
                            "code": "REQUEST_TOO_LARGE",
                            "message": "Request exceeds byte limit",
                        }
                    },
                    413,
                )
                return await response(scope, receive, send)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


def create_app(
    config: Config | None = None, service: Service | None = None, start_scheduler: bool = True
) -> FastAPI:
    config = config or load_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        owned = service is None
        app.state.service = service or Service(config, DockerBackend(config, owner_id(config)))
        scheduler = Scheduler(app.state.service)
        if start_scheduler:
            scheduler.start()
        yield
        if start_scheduler:
            scheduler.stop()
        if owned:
            app.state.service.close()

    app = FastAPI(title="nucube", version="0.1.0", lifespan=lifespan)
    app.add_middleware(BodyLimit, limit=config.max_snapshot_bytes * 2 + 2 * 1024 * 1024)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"]
    )

    @app.middleware("http")
    async def local_client(request: Request, call_next):
        # Browser requests must not turn a loopback API into a cross-origin code runner.
        if "origin" in request.headers or request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse(
                {
                    "error": {
                        "code": "ORIGIN_DENIED",
                        "message": "Browser-origin requests are disabled",
                    }
                },
                403,
            )
        return await call_next(request)

    @app.exception_handler(NucubeError)
    async def domain_error(request: Request, exc: NucubeError):
        return JSONResponse(exc.response(), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            {"error": {"code": "VALIDATION_ERROR", "message": "Invalid request fields"}},
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception):
        return JSONResponse(
            {
                "error": {
                    "code": "CONTROLLER_ERROR",
                    "message": "Controller operation failed; retry inspection",
                }
            },
            status_code=500,
        )

    @app.get("/health")
    def health(request: Request):
        error = request.app.state.service.last_error
        return {
            "status": "degraded" if error else "ok",
            "scheduler_error": error,
            "backend": "docker",
            "provisions_machines": False,
        }

    @app.post("/jobs", status_code=202)
    def submit(body: Submission, request: Request):
        return request.app.state.service.submit(body)

    @app.get("/jobs")
    def jobs(request: Request, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        return {"jobs": request.app.state.service.list_jobs(limit, offset)}

    @app.get("/jobs/{jid}")
    def get_job(
        jid: str,
        request: Request,
        task_limit: int = Query(100, ge=1, le=100),
        task_offset: int = Query(0, ge=0),
    ):
        return request.app.state.service.public_job(jid, task_limit, task_offset)

    @app.post("/jobs/{jid}/cancel")
    def cancel(jid: str, request: Request):
        request.app.state.service.cancel(jid)
        return request.app.state.service.public_job(jid)

    @app.get("/jobs/{jid}/logs/{tid}")
    def logs(jid: str, tid: str, request: Request, attempt: int | None = Query(None, ge=1)):
        return request.app.state.service.logs(jid, tid, attempt)

    @app.get("/jobs/{jid}/artifacts")
    def artifacts(
        jid: str,
        request: Request,
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
    ):
        return request.app.state.service.artifacts(jid, limit, offset)

    @app.get("/jobs/{jid}/artifact")
    def read_artifact(
        jid: str,
        task_id: str,
        attempt: int,
        path: str,
        request: Request,
        offset: int = Query(0, ge=0),
        limit: int = Query(65536, ge=1, le=65536),
    ):
        return request.app.state.service.read_artifact(jid, task_id, attempt, path, offset, limit)

    return app
