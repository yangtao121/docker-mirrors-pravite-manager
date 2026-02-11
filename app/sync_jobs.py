from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
import subprocess
import threading
from typing import Iterable
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _is_registry_component(value: str) -> bool:
    return "." in value or ":" in value or value == "localhost"


def _split_source_image(image: str) -> tuple[str, str]:
    value = image.strip()
    if not value:
        raise ValueError("source_image cannot be empty.")

    if "@" in value:
        base_name, digest = value.rsplit("@", 1)
        default_tag = digest.replace(":", "-")
    else:
        slash_index = value.rfind("/")
        colon_index = value.rfind(":")
        if colon_index > slash_index:
            base_name = value[:colon_index]
            default_tag = value[colon_index + 1 :]
        else:
            base_name = value
            default_tag = "latest"

    components = base_name.split("/")
    if len(components) > 1 and _is_registry_component(components[0]):
        target_repo = "/".join(components[1:])
    else:
        target_repo = base_name

    if not target_repo:
        raise ValueError(f"Cannot derive target repository from {image!r}.")
    return target_repo, default_tag


@dataclass
class SyncJob:
    id: str
    source_image: str
    target_image: str
    status: str = "running"
    logs: list[str] = field(default_factory=list)
    error: str | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "source_image": self.source_image,
            "target_image": self.target_image,
            "status": self.status,
            "logs": self.logs,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class SyncJobManager:
    def __init__(self, registry_push_host: str, retention: int = 120) -> None:
        self.registry_push_host = registry_push_host.rstrip("/")
        self.retention = max(retention, 20)
        self._jobs: OrderedDict[str, SyncJob] = OrderedDict()
        self._lock = threading.Lock()

    def create_job(
        self,
        source_image: str,
        target_repository: str | None = None,
        target_tag: str | None = None,
    ) -> SyncJob:
        default_repo, default_tag = _split_source_image(source_image)
        repository = (target_repository or "").strip() or default_repo
        tag = (target_tag or "").strip() or default_tag
        target_image = f"{self.registry_push_host}/{repository}:{tag}"

        job = SyncJob(
            id=uuid4().hex[:12],
            source_image=source_image.strip(),
            target_image=target_image,
        )
        self._insert_job(job)
        self._append_log(job.id, f"[init] source={job.source_image} target={job.target_image}")

        thread = threading.Thread(
            target=self._run_job,
            args=(job.id,),
            daemon=True,
        )
        thread.start()
        return job

    def get_job(self, job_id: str) -> SyncJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self, limit: int = 20) -> list[SyncJob]:
        with self._lock:
            jobs = list(self._jobs.values())
        jobs.reverse()
        return jobs[:limit]

    def _insert_job(self, job: SyncJob) -> None:
        with self._lock:
            self._jobs[job.id] = job
            while len(self._jobs) > self.retention:
                self._jobs.popitem(last=False)

    def _update_job_status(self, job_id: str, status: str, error: str | None = None) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.status = status
            job.error = error
            job.updated_at = utc_now_iso()

    def _append_log(self, job_id: str, message: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            timestamp = datetime.now(tz=timezone.utc).strftime("%H:%M:%S")
            job.logs.append(f"{timestamp} {message}")
            if len(job.logs) > 300:
                del job.logs[:-300]
            job.updated_at = utc_now_iso()

    def _run_job(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            source_image = job.source_image
            target_image = job.target_image

        steps: list[list[str]] = [
            ["docker", "pull", source_image],
            ["docker", "tag", source_image, target_image],
            ["docker", "push", target_image],
        ]

        try:
            for step in steps:
                self._run_command(job_id, step)
            self._update_job_status(job_id, "success")
            self._append_log(job_id, "[done] Image sync finished successfully.")
        except Exception as exc:
            self._append_log(job_id, f"[error] {exc}")
            self._update_job_status(job_id, "failed", str(exc))

    def _run_command(self, job_id: str, command: Iterable[str]) -> None:
        cmd_list = list(command)
        printable = " ".join(cmd_list)
        self._append_log(job_id, f"[run] {printable}")

        process = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        if process.stdout is not None:
            for line in process.stdout:
                cleaned = line.rstrip()
                if cleaned:
                    self._append_log(job_id, cleaned)
        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError(f"Command failed ({return_code}): {printable}")
