from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import load_settings
from app.registry_client import RegistryClient, RegistryError
from app.sync_jobs import SyncJobManager, detect_arch_label


settings = load_settings()
registry_client = RegistryClient(
    base_url=settings.registry_api_url,
    timeout=settings.request_timeout_sec,
)
sync_job_manager = SyncJobManager(
    registry_push_host=settings.registry_push_host,
    registry_api_url=settings.registry_api_url,
    retention=settings.sync_job_retention,
)
static_dir = Path(__file__).parent / "static"

app = FastAPI(title="Docker Registry Manager", version="1.0.0")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


class SyncJobRequest(BaseModel):
    source_image: str = Field(..., min_length=1, description="Image to pull, e.g. nginx:1.27")
    target_repository: str | None = Field(default=None, description="Target repository name")
    target_tag: str | None = Field(default=None, description="Target tag")


class LocalPushJobRequest(BaseModel):
    image_refs: list[str] = Field(..., min_length=1, description="Selected local image refs")
    prefix_mode: str = Field(default="none", description="none|add|remove")
    prefix_value: str = Field(default="", description="Prefix value for batch rename")
    arch_mode: str = Field(default="auto", description="auto|custom|none")
    arch_value: str = Field(default="", description="Custom arch label when arch_mode=custom")
    target_registry_host: str | None = Field(
        default=None,
        description="Override registry host, default from REGISTRY_PUSH_HOST",
    )
    cleanup_local_tag: bool = Field(
        default=False,
        description="Delete local source tag after successful push",
    )
    cleanup_registry_source_tag: bool = Field(
        default=False,
        description="Delete source tag from registry after successful push",
    )


class RemotePrefixJobRequest(BaseModel):
    repositories: list[str] = Field(..., min_length=1, description="Selected remote repositories")
    prefix_mode: str = Field(default="add", description="add|remove")
    prefix_value: str = Field(default="", description="Prefix value")
    cleanup_source_tag: bool = Field(
        default=False,
        description="Delete source tags from registry after successful rename",
    )
    target_registry_host: str | None = Field(
        default=None,
        description="Override registry host, default from REGISTRY_PUSH_HOST",
    )


class RepositoryDeleteJobRequest(BaseModel):
    repositories: list[str] = Field(..., min_length=1, description="Selected repositories")


def _raise_registry_error(exc: RegistryError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@app.on_event("shutdown")
def on_shutdown() -> None:
    registry_client.close()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "registry_api_url": settings.registry_api_url,
        "registry_push_host": settings.registry_push_host,
        "registry_healthy": registry_client.ping(),
        "detected_arch": detect_arch_label(),
    }


@app.get("/api/repositories")
def list_repositories(
    n: int = Query(default=100, ge=1, le=settings.max_catalog_results),
    last: str | None = Query(default=None),
    non_empty_only: bool = Query(default=False),
) -> dict[str, object]:
    try:
        result = registry_client.list_repositories(n=n, last=last)
        if not non_empty_only:
            return result

        repositories = result.get("repositories") or []
        if not isinstance(repositories, list):
            repositories = []

        filtered_repositories: list[str] = []
        for repository in repositories:
            if not isinstance(repository, str) or not repository:
                continue
            try:
                if registry_client.list_tags(repository):
                    filtered_repositories.append(repository)
            except RegistryError:
                # Treat inaccessible repositories as empty for this view.
                continue

        return {
            "repositories": filtered_repositories,
            "next": result.get("next"),
        }
    except RegistryError as exc:
        _raise_registry_error(exc)


@app.get("/api/repositories/{repository:path}/tags")
def list_tags(
    repository: str,
    details: bool = Query(default=True),
) -> dict[str, object]:
    try:
        tags = registry_client.list_tags(repository)
        if not details:
            return {"repository": repository, "tags": [{"tag": tag} for tag in tags]}

        tag_details = []
        for tag in tags:
            try:
                tag_details.append(registry_client.get_tag_details(repository, tag))
            except RegistryError as exc:
                tag_details.append(
                    {
                        "tag": tag,
                        "error": exc.message,
                    }
                )

        return {"repository": repository, "tags": tag_details}
    except RegistryError as exc:
        _raise_registry_error(exc)


@app.delete("/api/repositories/{repository:path}/tags/{tag}")
def delete_tag(repository: str, tag: str) -> dict[str, object]:
    try:
        digest = registry_client.delete_tag(repository, tag)
        return {"deleted": True, "repository": repository, "tag": tag, "digest": digest}
    except RegistryError as exc:
        _raise_registry_error(exc)


@app.post("/api/sync-jobs")
def create_sync_job(request: SyncJobRequest) -> dict[str, object]:
    try:
        job = sync_job_manager.create_job(
            source_image=request.source_image,
            target_repository=request.target_repository,
            target_tag=request.target_tag,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return job.to_dict()


@app.get("/api/local-images")
def list_local_images(limit: int = Query(default=300, ge=1, le=1000)) -> dict[str, object]:
    try:
        images = sync_job_manager.list_local_images(limit=limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"images": images, "detected_arch": detect_arch_label()}


@app.post("/api/local-push-jobs")
def create_local_push_job(request: LocalPushJobRequest) -> dict[str, object]:
    try:
        job = sync_job_manager.create_local_push_job(
            image_refs=request.image_refs,
            prefix_mode=request.prefix_mode,
            prefix_value=request.prefix_value,
            arch_mode=request.arch_mode,
            arch_value=request.arch_value,
            target_registry_host=request.target_registry_host,
            cleanup_local_tag=request.cleanup_local_tag,
            cleanup_registry_source_tag=request.cleanup_registry_source_tag,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return job.to_dict()


@app.post("/api/remote-prefix-jobs")
def create_remote_prefix_job(request: RemotePrefixJobRequest) -> dict[str, object]:
    try:
        job = sync_job_manager.create_remote_prefix_job(
            repositories=request.repositories,
            prefix_mode=request.prefix_mode,
            prefix_value=request.prefix_value,
            cleanup_source_tag=request.cleanup_source_tag,
            target_registry_host=request.target_registry_host,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return job.to_dict()


@app.post("/api/repository-delete-jobs")
def create_repository_delete_job(request: RepositoryDeleteJobRequest) -> dict[str, object]:
    try:
        job = sync_job_manager.create_repository_delete_job(
            repositories=request.repositories,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return job.to_dict()


@app.get("/api/sync-jobs")
def list_sync_jobs(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, object]:
    jobs = [job.to_dict() for job in sync_job_manager.list_jobs(limit=limit)]
    return {"jobs": jobs}


@app.get("/api/sync-jobs/{job_id}")
def get_sync_job(job_id: str) -> dict[str, object]:
    job = sync_job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return job.to_dict()
