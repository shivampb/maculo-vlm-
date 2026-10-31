"""Request and response models for the HTTP API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PointIn(BaseModel):
    x: float = Field(ge=0, le=1, description="Horizontal position, 0 = left edge, 1 = right.")
    y: float = Field(ge=0, le=1, description="Vertical position, 0 = top edge, 1 = bottom.")
    include: bool = Field(True, description="False marks an area to leave out.")


class AnalyzeIn(BaseModel):
    image_id: str = Field(min_length=8, max_length=64)
    points: list[PointIn] = Field(default_factory=list, max_length=24)
    box: list[float] | None = Field(
        None,
        min_length=4,
        max_length=4,
        description="Optional [x0, y0, x1, y1] around the spot, fractions of the image size.",
    )
    labels: list[str] = Field(min_length=2, max_length=500)
    mask_mode: Literal["best", "small", "large"] = "best"
    crop: bool = Field(True, description="Match only the outlined area plus a margin.")
    top_k: int = Field(5, ge=1, le=20)
    heatmap: bool = Field(True, description="Include SAM's per-pixel confidence map.")


class ImageOut(BaseModel):
    image_id: str
    width: int
    height: int
    expires_in: int


class Prediction(BaseModel):
    label: str
    score: float


class Outline(BaseModel):
    box: list[float] | None = Field(description="[x0, y0, x1, y1], fractions of the image size.")
    polygons: list[list[list[float]]] = Field(description="Outline rings in pixel coordinates.")
    score: float = Field(description="SAM's own estimate of outline quality, 0 to 1.")
    area: float = Field(description="Fraction of the image covered by the outline.")
    heatmap: str | None = Field(
        None,
        description="PNG data URL, grayscale: how sure SAM is that each pixel belongs "
        "to the spot (white = sure). Not a measure of severity.",
    )


class AnalyzeOut(BaseModel):
    predictions: list[Prediction]
    confidence: Literal["high", "moderate", "low"]
    notes: list[str]
    outline: Outline
    classified_region: Literal["outline", "full_image"]
    timings_ms: dict[str, float]


class Meta(BaseModel):
    name: str
    version: str
    ready: bool
    device: str
    label_groups: dict[str, list[str]]
    default_selection: list[str]
    limits: dict[str, float]
