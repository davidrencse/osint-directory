import asyncio
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import Response

from app.config import get_settings
from app.core import store
from app.metadata import extract as ex
from app.metadata.strip import StripError, strip

router = APIRouter(prefix="/api/metadata", tags=["metadata"])


@contextmanager
def _tempdir():
    d = Path(tempfile.mkdtemp(prefix="osint-meta-"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


async def _save(upload: UploadFile, dest: Path) -> None:
    limit = get_settings().max_upload_mb * 1024 * 1024
    if upload.size is not None and upload.size > limit:
        raise HTTPException(413, f"File exceeds {get_settings().max_upload_mb} MB")
    written = 0
    with dest.open("wb") as f:
        while chunk := await upload.read(1 << 20):
            written += len(chunk)
            if written > limit:
                raise HTTPException(413, f"File exceeds {get_settings().max_upload_mb} MB")
            f.write(chunk)


def _safe_name(name: str | None) -> str:
    return Path(name or "upload.bin").name or "upload.bin"


@router.get("/capabilities")
def capabilities():
    return {"exiftool": ex.exiftool_available(), "max_upload_mb": get_settings().max_upload_mb}


@router.post("")
async def analyse(file: UploadFile):
    name = _safe_name(file.filename)
    with _tempdir() as d:
        path = d / "input"
        await _save(file, path)
        result = await asyncio.to_thread(ex.extract, path, name)
    await asyncio.to_thread(store.audit, "metadata", name, {"sha256": result["hashes"]["sha256"]})
    return result


@router.post("/strip")
async def strip_metadata(file: UploadFile):
    name = _safe_name(file.filename)
    with _tempdir() as d:
        src, dst = d / "input", d / "output"
        await _save(file, src)
        with src.open("rb") as f:
            mime = ex.detect_type(f.read(32), name)
        try:
            method = await asyncio.to_thread(strip, src, mime, dst)
        except StripError as exc:
            raise HTTPException(415, str(exc)) from exc
        except Exception as exc:  # malformed input the parsers choke on (bad zip, broken PDF, ...)
            raise HTTPException(422, f"Could not clean this file: {type(exc).__name__}: {exc}"[:300]) from exc
        data = await asyncio.to_thread(dst.read_bytes)
    stem, dot, ext = name.rpartition(".")
    clean_name = f"{stem}.clean.{ext}" if dot else f"{name}.clean"
    return Response(
        content=data,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{clean_name}"',
            "X-Strip-Method": method,
            "Access-Control-Expose-Headers": "Content-Disposition, X-Strip-Method",
        },
    )
