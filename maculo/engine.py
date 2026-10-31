"""Model inference: SAM for outlining, a CLIP-style model for zero-shot matching.

The SAM image encoder is the slow part, so `embed` runs it once per upload and
`segment` reuses the result for every click.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Literal, Protocol, Sequence

import numpy as np
from PIL import Image

from .config import Settings
from .labels import ALL_LABELS, TEMPLATES

log = logging.getLogger("maculo.engine")

MaskMode = Literal["best", "small", "large"]


@dataclass(frozen=True)
class Point:
    x: float  # pixels
    y: float  # pixels
    include: bool = True


@dataclass
class Segmentation:
    mask: np.ndarray  # (H, W) bool
    score: float  # SAM's own estimate of outline quality, 0 to 1
    confidence: np.ndarray | None = None  # (H, W) float 0..1, how sure SAM is per pixel


# SAM's mask logits run from about -4 at the soft edge to about 7 in a firm core.
# Mapping that range linearly to 0..1 gives a readable gradient.
LOGIT_RANGE = (-4.0, 7.0)


def logits_to_confidence(logits: np.ndarray) -> np.ndarray:
    lo, hi = LOGIT_RANGE
    return np.clip((logits - lo) / (hi - lo), 0.0, 1.0).astype(np.float32)


class Engine(Protocol):
    ready: bool
    device: str

    def load(self) -> None: ...
    def embed(self, img: Image.Image) -> object: ...
    def segment(
        self,
        img: Image.Image,
        embedding: object,
        points: Sequence[Point],
        mode: MaskMode,
        box: tuple[float, float, float, float] | None = None,
    ) -> Segmentation: ...
    def classify(
        self, img: Image.Image, labels: Sequence[str], top_k: int
    ) -> list[tuple[str, float]]: ...


def pick_mask(masks: np.ndarray, scores: np.ndarray, mode: MaskMode) -> int:
    """Choose one of SAM's candidate masks."""
    if mode == "small":
        areas = masks.reshape(len(masks), -1).sum(1)
        return int(np.where(areas > 0, areas, areas.max() + 1).argmin())
    if mode == "large":
        return int(masks.reshape(len(masks), -1).sum(1).argmax())
    return int(scores.argmax())


class TorchEngine:
    """The production engine. Model calls are serialized with a lock so a single
    GPU never runs two forward passes at once."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.device = "cpu"
        self.ready = False
        self._lock = threading.Lock()
        self._text_cache: OrderedDict[str, object] = OrderedDict()

    # ---- loading ----
    def load(self) -> None:
        import open_clip
        import torch
        from transformers import SamModel, SamProcessor

        s = self.settings
        if not (s.sam_dir / "config.json").exists():
            raise FileNotFoundError(
                f"SAM model not found in {s.sam_dir}. See README.md, 'Models'."
            )
        self.device = s.resolve_device()
        self._torch = torch
        t = time.perf_counter()

        clip, self._clip_pre = open_clip.create_model_from_pretrained(s.clip_id)
        self._clip = clip.to(self.device).eval()
        self._tok = open_clip.get_tokenizer(s.clip_id)
        scale = getattr(self._clip, "logit_scale", None)
        self._logit_scale = float(scale.exp()) if scale is not None else 100.0

        self._sam_proc = SamProcessor.from_pretrained(str(s.sam_dir))
        self._sam = SamModel.from_pretrained(str(s.sam_dir)).to(self.device).eval()

        self._text_features(ALL_LABELS)  # warm the cache with every preset
        self.ready = True
        log.info(
            "models loaded on %s in %.1fs", self.device, time.perf_counter() - t
        )

    def _autocast(self):
        return self._torch.autocast(
            device_type=self.device.split(":")[0],
            dtype=self._torch.float16,
            enabled=self.device.startswith("cuda"),
        )

    # ---- SAM ----
    def embed(self, img: Image.Image) -> object:
        with self._lock, self._torch.inference_mode(), self._autocast():
            inp = self._sam_proc(img, return_tensors="pt").to(self.device)
            return self._sam.get_image_embeddings(inp["pixel_values"])

    def segment(self, img, embedding, points, mode, box=None):
        """Outline from click points, a box dragged around the spot, or both."""
        kw = {}
        if points:
            kw["input_points"] = [[[[p.x, p.y] for p in points]]]
            kw["input_labels"] = [[[1 if p.include else 0 for p in points]]]
        if box is not None:
            kw["input_boxes"] = [[list(box)]]
        inp = self._sam_proc(img, return_tensors="pt", **kw)
        inp.pop("pixel_values", None)
        prompts = {k: v.to(self.device) for k, v in inp.items() if k.startswith("input_")}
        with self._lock, self._torch.inference_mode(), self._autocast():
            out = self._sam(image_embeddings=embedding, **prompts)
        logits = self._sam_proc.image_processor.post_process_masks(
            out.pred_masks.float().cpu(),
            inp["original_sizes"],
            inp["reshaped_input_sizes"],
            binarize=False,
        )[0][0].numpy()  # (3, H, W) float
        masks = logits > 0.0
        scores = out.iou_scores.float().cpu()[0, 0].numpy()
        i = pick_mask(masks, scores, mode)
        return Segmentation(masks[i], float(scores[i]), logits_to_confidence(logits[i]))

    # ---- CLIP ----
    def _text_features(self, labels: Sequence[str]):
        torch = self._torch
        missing = [l for l in dict.fromkeys(labels) if l not in self._text_cache]
        if missing:
            prompts = [t.format(l) for l in missing for t in TEMPLATES]
            with self._lock, torch.inference_mode():
                f = self._clip.encode_text(self._tok(prompts).to(self.device)).float()
                f = f / f.norm(dim=-1, keepdim=True)
                f = f.view(len(missing), len(TEMPLATES), -1).mean(1)
                f = f / f.norm(dim=-1, keepdim=True)
            for label, vec in zip(missing, f):
                self._text_cache[label] = vec
        for l in labels:
            self._text_cache.move_to_end(l)
        while len(self._text_cache) > 4096:
            self._text_cache.popitem(last=False)
        return torch.stack([self._text_cache[l] for l in labels])

    def classify(self, img, labels, top_k):
        torch = self._torch
        txt = self._text_features(labels)
        with self._lock, torch.inference_mode():
            x = self._clip_pre(img).unsqueeze(0).to(self.device)
            f = self._clip.encode_image(x).float()
            f = f / f.norm(dim=-1, keepdim=True)
            p = (self._logit_scale * f @ txt.T).softmax(-1)[0]
        top = p.topk(min(top_k, len(labels)))
        return [
            (labels[i], float(s)) for s, i in zip(top.values.tolist(), top.indices.tolist())
        ]
