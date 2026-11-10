"""Secure dataset download with a pinned SHA-256 and atomic cache writes."""

from __future__ import annotations

import contextlib
import hashlib
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests

from upliftlab.datasets.base import DatasetSpec
from upliftlab.errors import ChecksumError, DataError

DOWNLOAD_TIMEOUT = (10, 120)
MAX_DOWNLOAD_BYTES = 500 * 1024 * 1024
CHUNK_SIZE = 1 << 20


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksum(path: Path, expected: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise ChecksumError(f"{path}: expected sha256 {expected}, got {actual}")


def download_dataset(spec: DatasetSpec, data_dir: Path, *, force: bool = False) -> Path:
    """Return a verified local copy, downloading only when needed.

    The URL is a literal in the dataset registry. HTTPS, a byte cap, and a
    pinned digest are enforced before the file enters the cache.
    """
    parsed = urlparse(spec.url)
    if parsed.scheme != "https":
        raise DataError(f"{spec.name}: download URL must use HTTPS")
    if not spec.filename or Path(spec.filename).name != spec.filename:
        raise DataError(f"{spec.name}: filename must be a plain basename")

    data_dir = data_dir.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    destination = data_dir / spec.filename

    if destination.exists() and not force:
        verify_checksum(destination, spec.sha256)
        return destination

    temporary: Path | None = None
    try:
        with requests.get(
            spec.url,
            stream=True,
            timeout=DOWNLOAD_TIMEOUT,
            headers={"Accept-Encoding": "identity"},
        ) as response:
            response.raise_for_status()
            final_url = getattr(response, "url", spec.url)
            if urlparse(str(final_url)).scheme != "https":
                raise DataError(f"{spec.name}: redirect left HTTPS")
            declared_header = response.headers.get("Content-Length")
            declared: int | None = None
            if declared_header is not None:
                try:
                    declared = int(declared_header)
                except ValueError:
                    declared = None
            if declared is not None and declared > MAX_DOWNLOAD_BYTES:
                raise DataError(
                    f"{spec.name}: declared download exceeds {MAX_DOWNLOAD_BYTES} bytes"
                )

            with tempfile.NamedTemporaryFile(
                dir=data_dir,
                prefix=f".{spec.filename}.",
                suffix=".part",
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                digest = hashlib.sha256()
                total = 0
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > MAX_DOWNLOAD_BYTES:
                        raise DataError(f"{spec.name}: download exceeds {MAX_DOWNLOAD_BYTES} bytes")
                    digest.update(chunk)
                    handle.write(chunk)

        actual = digest.hexdigest()
        if actual != spec.sha256:
            raise ChecksumError(f"{spec.name}: expected sha256 {spec.sha256}, got {actual}")
        temporary.replace(destination)
        temporary = None
        return destination
    except requests.RequestException as exc:
        raise DataError(f"{spec.name}: download failed: {exc}") from exc
    except OSError as exc:
        raise DataError(f"{spec.name}: cannot store download: {exc}") from exc
    finally:
        if temporary is not None:
            with contextlib.suppress(OSError):
                temporary.unlink(missing_ok=True)
