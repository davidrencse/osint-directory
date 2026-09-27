from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.geo import layers

router = APIRouter(prefix="/api/geo", tags=["geo"])


@router.get("/layers")
def list_layers():
    return layers.describe(get_settings())


@router.get("/{layer_id}")
async def get_layer(layer_id: str, bbox: str | None = None):
    if layer_id not in layers.LAYERS:
        raise HTTPException(404, f"Unknown layer '{layer_id}'")
    try:
        return await layers.get_layer(layer_id, layers.normalise_bbox(bbox))
    except Exception as exc:
        raise HTTPException(502, f"{layer_id} upstream failed: {type(exc).__name__}: {exc}") from exc
