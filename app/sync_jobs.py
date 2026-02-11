from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import platform
import subprocess
import threading
import time
from typing import Iterable
from urllib.parse import quote
from uuid import uuid4

import httpx

def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _is_registry_component(value: str) -> bool:
    return "." in value or ":" in value or value == "localhost"


def detect_arch_label(raw: str | None = None) -> str:
    machine = (raw or platform.machine() or "").strip().lower()
    if machine in {"x86_64", "amd64", "x64"}:
        return "x86"
    if machine in {"aarch64", "arm64"}:
        return "arm"
    if machine.startswith("arm"):
        return "arm"
    return machine or "unknown"


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


def _apply_prefix(repository: str, prefix_mode: str, prefix_value: str) -> str:
    base = repository.strip("/")
    prefix = prefix_value.strip("/")
    if not prefix or prefix_mode == "none":
        return base
    if prefix_mode == "add":
        if base.startswith(f"{prefix}/") or base == prefix:
            return base
        return f"{prefix}/{base}"
    if prefix_mode == "remove":
        if base.startswith(f"{prefix}/"):
            return base[len(prefix) + 1 :]
        if base == prefix:
            return ""
        return base
    raise ValueError(f"Unsupported prefix mode: {prefix_mode}")


@dataclass
class SyncJob:
    id: str
    source_image: str
    target_image: str
    job_type: str = "mirror"
    total_items: int = 1
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
            "job_type": self.job_type,
            "total_items": self.total_items,
            "status": self.status,
            "logs": self.logs,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class SyncJobManager:
    def __init__(
        self,
        registry_push_host: str,
        registry_api_url: str | None = None,
        retention: int = 120,
    ) -> None:
        self.registry_push_host = registry_push_host.rstrip("/")
        self.registry_api_url = (registry_api_url or "").rstrip("/")
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

        commands = [
            ["docker", "pull", source_image.strip()],
            ["docker", "tag", source_image.strip(), target_image],
            ["docker", "push", target_image],
        ]
        job = SyncJob(
            id=uuid4().hex[:12],
            source_image=source_image.strip(),
            target_image=target_image,
            job_type="mirror",
            total_items=1,
        )
        return self._create_and_start_job(job, commands)

    def create_local_push_job(
        self,
        image_refs: list[str],
        prefix_mode: str = "none",
        prefix_value: str = "",
        arch_mode: str = "auto",
        arch_value: str = "",
        target_registry_host: str | None = None,
        cleanup_local_tag: bool = False,
        cleanup_registry_source_tag: bool = False,
    ) -> SyncJob:
        cleaned_refs = [item.strip() for item in image_refs if item and item.strip()]
        if not cleaned_refs:
            raise ValueError("At least one local image is required.")

        normalized_arch_mode = arch_mode.strip().lower() or "auto"
        if normalized_arch_mode not in {"auto", "custom", "none"}:
            raise ValueError("arch_mode must be one of: auto, custom, none.")

        normalized_prefix_mode = prefix_mode.strip().lower() or "none"
        if normalized_prefix_mode not in {"add", "remove", "none"}:
            raise ValueError("prefix_mode must be one of: add, remove, none.")

        registry_host = (target_registry_host or self.registry_push_host).strip().rstrip("/")
        if not registry_host:
            raise ValueError("target_registry_host cannot be empty.")

        arch_label = ""
        if normalized_arch_mode == "auto":
            arch_label = detect_arch_label()
        elif normalized_arch_mode == "custom":
            arch_label = arch_value.strip().lower()
            if not arch_label:
                raise ValueError("arch_value is required when arch_mode=custom.")

        commands: list[list[str]] = []
        mappings: list[str] = []
        registry_cleanup_targets: list[tuple[str, str]] = []
        for source_ref in cleaned_refs:
            repository, tag = _split_source_image(source_ref)
            updated_repo = _apply_prefix(repository, normalized_prefix_mode, prefix_value)
            if not updated_repo:
                raise ValueError(
                    f"Prefix operation removed repository name entirely for {source_ref}."
                )

            target_tag = tag
            if arch_label:
                suffix = f"-{arch_label}"
                if not target_tag.endswith(suffix):
                    target_tag = f"{target_tag}{suffix}"

            target_ref = f"{registry_host}/{updated_repo}:{target_tag}"
            mappings.append(f"{source_ref} => {target_ref}")
            commands.append(["docker", "tag", source_ref, target_ref])
            commands.append(["docker", "push", target_ref])
            if cleanup_local_tag:
                commands.append(["docker", "image", "rm", source_ref])
            if cleanup_registry_source_tag:
                registry_cleanup_targets.append((repository, tag))

        summary = f"{len(cleaned_refs)} local images"
        job = SyncJob(
            id=uuid4().hex[:12],
            source_image=summary,
            target_image=registry_host,
            job_type="local-push",
            total_items=len(cleaned_refs),
        )
        created = self._create_and_start_job(job, commands)
        self._append_log(
            created.id,
            f"[plan] arch_mode={normalized_arch_mode} arch={arch_label or '-'} "
            f"prefix_mode={normalized_prefix_mode} prefix={prefix_value or '-'}",
        )
        for mapping in mappings[:120]:
            self._append_log(created.id, f"[map] {mapping}")
        if len(mappings) > 120:
            self._append_log(created.id, f"[map] ... ({len(mappings) - 120} more)")

        if cleanup_registry_source_tag:
            self._append_log(
                created.id,
                "[cleanup] registry source tag cleanup is enabled.",
            )
            thread = threading.Thread(
                target=self._wait_then_cleanup_registry_source_tags,
                args=(created.id, registry_cleanup_targets),
                daemon=True,
            )
            thread.start()
        return created

    def list_local_images(self, limit: int = 300) -> list[dict[str, object]]:
        ps = subprocess.run(
            [
                "docker",
                "image",
                "ls",
                "--format",
                "{{.Repository}}|{{.Tag}}|{{.ID}}|{{.Size}}",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if ps.returncode != 0:
            raise RuntimeError(ps.stderr.strip() or "docker image ls failed")

        rows: list[dict[str, object]] = []
        refs_for_inspect: list[str] = []
        for line in ps.stdout.splitlines():
            parts = line.strip().split("|")
            if len(parts) != 4:
                continue
            repository, tag, image_id, size_text = [p.strip() for p in parts]
            if repository in {"<none>", ""} or tag in {"<none>", ""}:
                continue
            ref = f"{repository}:{tag}"
            rows.append(
                {
                    "reference": ref,
                    "repository": repository,
                    "tag": tag,
                    "image_id": image_id,
                    "size": size_text,
                }
            )
            refs_for_inspect.append(ref)
            if len(rows) >= limit:
                break

        if not refs_for_inspect:
            return []

        inspect = subprocess.run(
            ["docker", "image", "inspect", *refs_for_inspect],
            check=False,
            capture_output=True,
            text=True,
        )
        arch_map: dict[str, tuple[str | None, str | None]] = {}
        if inspect.returncode == 0 and inspect.stdout.strip():
            try:
                payload = json.loads(inspect.stdout)
                if isinstance(payload, list):
                    for item in payload:
                        if not isinstance(item, dict):
                            continue
                        arch = item.get("Architecture")
                        os_name = item.get("Os")
                        tags = item.get("RepoTags")
                        if isinstance(tags, list):
                            for tag_ref in tags:
                                if isinstance(tag_ref, str):
                                    arch_map[tag_ref] = (
                                        str(arch) if arch is not None else None,
                                        str(os_name) if os_name is not None else None,
                                    )
            except json.JSONDecodeError:
                pass

        for row in rows:
            arch, os_name = arch_map.get(row["reference"], (None, None))
            row["architecture"] = arch
            row["os"] = os_name

        return rows

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

    def _create_and_start_job(self, job: SyncJob, commands: list[list[str]]) -> SyncJob:
        self._insert_job(job)
        self._append_log(
            job.id,
            f"[init] type={job.job_type} source={job.source_image} target={job.target_image}",
        )
        thread = threading.Thread(
            target=self._run_commands_job,
            args=(job.id, commands),
            daemon=True,
        )
        thread.start()
        return job

    def _wait_then_cleanup_registry_source_tags(
        self,
        job_id: str,
        targets: list[tuple[str, str]],
    ) -> None:
        while True:
            job = self.get_job(job_id)
            if job is None:
                return
            if job.status == "running":
                time.sleep(0.6)
                continue
            if job.status != "success":
                self._append_log(job_id, "[cleanup] skipped because job is not successful.")
                return
            break

        if not self.registry_api_url:
            self._append_log(job_id, "[cleanup] registry_api_url is empty, cannot cleanup.")
            return

        unique_targets = list(dict.fromkeys(targets))
        try:
            with httpx.Client(base_url=self.registry_api_url, timeout=20.0) as client:
                for repository, tag in unique_targets:
                    self._delete_registry_source_tag(client, job_id, repository, tag)
        except Exception as exc:
            self._append_log(job_id, f"[cleanup] registry cleanup failed: {exc}")
            self._update_job_status(job_id, "failed", f"Registry cleanup failed: {exc}")

    def _delete_registry_source_tag(
        self,
        client: httpx.Client,
        job_id: str,
        repository: str,
        tag: str,
    ) -> None:
        encoded_tag = quote(tag, safe="")
        path = f"/v2/{repository}/manifests/{encoded_tag}"
        headers = {
            "Accept": ", ".join(
                [
                    "application/vnd.docker.distribution.manifest.v2+json",
                    "application/vnd.oci.image.manifest.v1+json",
                    "application/vnd.docker.distribution.manifest.list.v2+json",
                    "application/vnd.oci.image.index.v1+json",
                ]
            )
        }
        head_resp = client.head(path, headers=headers)
        if head_resp.status_code == 404:
            self._append_log(job_id, f"[cleanup] skip missing tag {repository}:{tag}")
            return
        if head_resp.status_code >= 400:
            raise RuntimeError(
                f"cleanup HEAD failed {repository}:{tag} status={head_resp.status_code}"
            )
        digest = head_resp.headers.get("Docker-Content-Digest", "").strip()
        if not digest:
            get_resp = client.get(path, headers=headers)
            if get_resp.status_code >= 400:
                raise RuntimeError(
                    f"cleanup GET failed {repository}:{tag} status={get_resp.status_code}"
                )
            digest = get_resp.headers.get("Docker-Content-Digest", "").strip()
        if not digest:
            raise RuntimeError(f"cleanup digest missing for {repository}:{tag}")

        del_path = f"/v2/{repository}/manifests/{quote(digest, safe=':')}"
        del_resp = client.delete(del_path)
        if del_resp.status_code == 404:
            self._append_log(job_id, f"[cleanup] already removed {repository}:{tag}")
            return
        if del_resp.status_code >= 400:
            raise RuntimeError(
                f"cleanup DELETE failed {repository}:{tag} status={del_resp.status_code}"
            )
        self._append_log(job_id, f"[cleanup] deleted source tag {repository}:{tag}")

    def _run_commands_job(self, job_id: str, commands: list[list[str]]) -> None:
        try:
            for command in commands:
                self._run_command(job_id, command)
            self._update_job_status(job_id, "success")
            self._append_log(job_id, "[done] Job finished successfully.")
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
