from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import httpx


MANIFEST_ACCEPT_HEADER = ", ".join(
    [
        "application/vnd.docker.distribution.manifest.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.index.v1+json",
    ]
)


@dataclass
class RegistryError(Exception):
    message: str
    status_code: int = 500

    def __str__(self) -> str:
        return self.message


class RegistryClient:
    def __init__(self, base_url: str, timeout: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def close(self) -> None:
        self.client.close()

    def ping(self) -> bool:
        try:
            response = self.client.get("/v2/")
        except httpx.RequestError:
            return False
        return response.status_code in (200, 401)

    def list_repositories(self, n: int = 100, last: str | None = None) -> dict[str, object]:
        params: dict[str, str | int] = {"n": n}
        if last:
            params["last"] = last
        response = self._request("GET", "/v2/_catalog", params=params)
        payload = response.json()
        repositories = payload.get("repositories") or []
        if not isinstance(repositories, list):
            raise RegistryError("Invalid catalog response from registry.", status_code=502)
        return {
            "repositories": repositories,
            "next": self._parse_next_from_link(response.headers.get("Link")),
        }

    def list_tags(self, repository: str) -> list[str]:
        response = self._request("GET", f"/v2/{repository}/tags/list")
        payload = response.json()
        tags = payload.get("tags") or []
        if not isinstance(tags, list):
            return []
        return tags

    def get_tag_details(self, repository: str, tag: str) -> dict[str, object]:
        digest = self.resolve_manifest_digest(repository, tag)
        manifest, media_type = self.get_manifest(repository, digest)
        size_bytes = self._estimate_manifest_size(manifest, media_type)
        created_at = self._extract_created_at(repository, manifest, media_type)
        return {
            "tag": tag,
            "digest": digest,
            "media_type": media_type,
            "size_bytes": size_bytes,
            "created_at": created_at,
        }

    def resolve_manifest_digest(self, repository: str, reference: str) -> str:
        headers = {"Accept": MANIFEST_ACCEPT_HEADER}
        response = self._request(
            "HEAD",
            f"/v2/{repository}/manifests/{reference}",
            headers=headers,
        )
        digest = response.headers.get("Docker-Content-Digest")
        if digest:
            return digest

        fallback = self._request(
            "GET",
            f"/v2/{repository}/manifests/{reference}",
            headers=headers,
        )
        digest = fallback.headers.get("Docker-Content-Digest")
        if not digest:
            raise RegistryError(
                f"Digest not found for {repository}:{reference}.",
                status_code=502,
            )
        return digest

    def get_manifest(self, repository: str, reference: str) -> tuple[dict[str, object], str]:
        headers = {"Accept": MANIFEST_ACCEPT_HEADER}
        response = self._request(
            "GET",
            f"/v2/{repository}/manifests/{reference}",
            headers=headers,
        )
        media_type = (
            response.headers.get("Content-Type")
            or response.json().get("mediaType")
            or "application/vnd.docker.distribution.manifest.v2+json"
        )
        return response.json(), media_type

    def delete_tag(self, repository: str, tag: str) -> str:
        digest = self.resolve_manifest_digest(repository, tag)
        self.delete_manifest(repository, digest)
        return digest

    def delete_manifest(self, repository: str, digest: str) -> None:
        self._request("DELETE", f"/v2/{repository}/manifests/{digest}")

    def _request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        try:
            response = self.client.request(method=method, url=path, **kwargs)
        except httpx.RequestError as exc:
            raise RegistryError(f"Registry request failed: {exc}", status_code=502) from exc

        if response.status_code >= 400:
            body_preview = response.text[:300] if response.text else ""
            if method.upper() == "DELETE" and response.status_code == 405:
                raise RegistryError(
                    "Registry denied manifest delete (405). "
                    "Enable REGISTRY_STORAGE_DELETE_ENABLED=true on registry and restart it.",
                    status_code=405,
                )
            raise RegistryError(
                f"Registry API error {response.status_code}: {body_preview}",
                status_code=response.status_code,
            )
        return response

    @staticmethod
    def _parse_next_from_link(link_header: str | None) -> str | None:
        if not link_header:
            return None
        for raw_part in link_header.split(","):
            part = raw_part.strip()
            if 'rel="next"' not in part:
                continue
            if not part.startswith("<") or ">" not in part:
                continue
            url = part[1 : part.index(">")]
            parsed = urlparse(url)
            query = parse_qs(parsed.query)
            candidate = query.get("last")
            if candidate:
                return candidate[0]
        return None

    def _extract_created_at(
        self,
        repository: str,
        manifest: dict[str, object],
        media_type: str,
    ) -> str | None:
        normalized = media_type.split(";")[0].strip().lower()
        is_single_manifest = normalized in {
            "application/vnd.docker.distribution.manifest.v2+json",
            "application/vnd.oci.image.manifest.v1+json",
        }
        if not is_single_manifest:
            return None

        config = manifest.get("config")
        if not isinstance(config, dict):
            return None
        config_digest = config.get("digest")
        if not isinstance(config_digest, str) or not config_digest:
            return None

        try:
            blob = self._request("GET", f"/v2/{repository}/blobs/{config_digest}").json()
        except RegistryError:
            return None
        created = blob.get("created")
        if not isinstance(created, str):
            return None
        try:
            parsed = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except ValueError:
            return created
        return parsed.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _estimate_manifest_size(manifest: dict[str, object], media_type: str) -> int | None:
        normalized = media_type.split(";")[0].strip().lower()
        if normalized in {
            "application/vnd.docker.distribution.manifest.v2+json",
            "application/vnd.oci.image.manifest.v1+json",
        }:
            total_size = 0
            config = manifest.get("config")
            if isinstance(config, dict):
                config_size = config.get("size")
                if isinstance(config_size, int):
                    total_size += config_size
            layers = manifest.get("layers")
            if isinstance(layers, list):
                for layer in layers:
                    if isinstance(layer, dict):
                        layer_size = layer.get("size")
                        if isinstance(layer_size, int):
                            total_size += layer_size
            return total_size

        if normalized in {
            "application/vnd.docker.distribution.manifest.list.v2+json",
            "application/vnd.oci.image.index.v1+json",
        }:
            total_size = 0
            manifests = manifest.get("manifests")
            if not isinstance(manifests, list):
                return None
            for item in manifests:
                if isinstance(item, dict):
                    item_size = item.get("size")
                    if isinstance(item_size, int):
                        total_size += item_size
            return total_size

        return None
