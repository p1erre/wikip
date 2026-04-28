#!/usr/bin/env python3
"""
Extract unique slides from a presentation video.

Usage: extract.py <video.mp4> --out-dir <dir> [--fps 2.0] [--build-policy build_collapse|build_preserve]

Writes:
  <out-dir>/slide_NNN.jpg     one image per unique slide
  <out-dir>/metadata.json     [{slide_number, image_path, timestamp, duration, num_occurrences}, ...]

Idempotent: skips if metadata.json exists and is non-empty.

Algorithm: perceptual hashing + SSIM verification + edge-based build detection.
"""

import argparse
import json
import sys
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class Config:
    target_width: int = 1024
    fps_sample: float = 2.0
    presenter_roi: Optional[tuple[float, float, float, float]] = None
    motion_buffer_len: int = 7
    motion_std_thresh: float = 4.0
    mask_fill_value: int = 128
    phash_size: int = 8
    ham_keep: int = 10
    ham_new: int = 18
    ssim_keep: float = 0.93
    build_policy: str = "build_collapse"
    ssim_build: float = 0.98
    build_add_ratio_max: float = 0.15
    build_remove_ratio_max: float = 0.03
    confirm_k: int = 3
    min_seg_secs: float = 2.0
    cluster_merge_ham: int = 10
    cluster_verify_ssim: Optional[float] = 0.92
    ssim_short_w: int = 640


@dataclass
class Segment:
    start: float
    end: float
    keyframe: Any
    keyframe_original: Any
    phash: Any
    builds: list[dict] = field(default_factory=list)
    cluster_id: Optional[int] = None


class SlideDeduplicator:
    def __init__(self, **kwargs):
        self.cfg = Config(**kwargs)
        self._reset()

    def _reset(self):
        self.curr_hash = None
        self.curr_keyframe = None
        self.curr_keyframe_original = None
        self.curr_start_t = None
        self.pending_fail = 0
        self.motion_buf = deque(maxlen=self.cfg.motion_buffer_len)
        self.segments: list[Segment] = []
        self._open_builds = []

    def process_video(self, path: str) -> dict:
        import cv2

        self._reset()
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise RuntimeError(f"cannot open video: {path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        sample_stride = max(1, int(round(fps / self.cfg.fps_sample)))
        t = 0.0
        frame_idx = 0

        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_idx % sample_stride == 0:
                self._step(t, frame)
            frame_idx += 1
            t = frame_idx / max(fps, 1e-6)

        cap.release()
        self._end_segment(t)
        clusters = self._global_dedup(self.segments)
        return {"segments": [self._ser(s) for s in self.segments], "clusters": clusters}

    def _step(self, t, frame_bgr):
        gray = self._preprocess(frame_bgr)
        masked = self._apply_mask(gray)
        h = self._phash(masked)

        if self.curr_hash is None:
            self._start_segment(t, masked, h, frame_bgr)
            return

        ham = self.curr_hash - h
        if ham <= self.cfg.ham_keep:
            self.pending_fail = 0
            return

        if ham < self.cfg.ham_new:
            s = self._ssim(self.curr_keyframe, masked)
            if s >= self.cfg.ssim_keep:
                if self._is_build_step(self.curr_keyframe, masked, s):
                    self._record_build(t, masked, frame_bgr)
                    self.pending_fail = 0
                    return
                self.pending_fail = 0
                return

        self.pending_fail += 1
        if self.pending_fail >= self.cfg.confirm_k:
            if (t - self.curr_start_t) >= self.cfg.min_seg_secs:
                self._end_segment(t)
                self._start_segment(t, masked, h, frame_bgr)
            self.pending_fail = 0

    def _start_segment(self, t, keyframe, ph, original):
        self.curr_start_t = t
        self.curr_keyframe = keyframe
        self.curr_keyframe_original = original
        self.curr_hash = ph
        self.pending_fail = 0

    def _end_segment(self, t):
        if self.curr_start_t is None:
            return
        self.segments.append(Segment(
            start=self.curr_start_t,
            end=t,
            keyframe=self.curr_keyframe,
            keyframe_original=self.curr_keyframe_original,
            phash=self.curr_hash,
            builds=self._open_builds.copy(),
        ))
        self.curr_start_t = None
        self.curr_keyframe = None
        self.curr_keyframe_original = None
        self.curr_hash = None
        self.pending_fail = 0
        self._open_builds = []

    def _record_build(self, t, new_img, original):
        add, rem = self._build_signature(self.curr_keyframe, new_img)
        entry = {"t": t, "add_ratio": float(add), "rem_ratio": float(rem)}
        if self.cfg.build_policy == "build_collapse":
            self.curr_keyframe = new_img
            self.curr_keyframe_original = original
            self.curr_hash = self._phash(new_img)
            self._open_builds.append(entry)
        elif self.cfg.build_policy == "build_preserve":
            if (t - self.curr_start_t) >= max(0.5, self.cfg.min_seg_secs / 2):
                self._end_segment(t)
                self._start_segment(t, new_img, self._phash(new_img), original)
            else:
                self.curr_keyframe = new_img
                self.curr_keyframe_original = original
                self.curr_hash = self._phash(new_img)
                self._open_builds.append(entry)
        else:
            raise ValueError(f"unknown build_policy: {self.cfg.build_policy}")

    def _preprocess(self, frame_bgr):
        import cv2

        h, w = frame_bgr.shape[:2]
        scale = self.cfg.target_width / float(w)
        frame = cv2.resize(frame_bgr, (self.cfg.target_width, int(h * scale)), interpolation=cv2.INTER_AREA)
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    def _apply_mask(self, gray):
        import numpy as np

        self.motion_buf.append(gray)
        masked = gray.copy()
        if len(self.motion_buf) == self.motion_buf.maxlen:
            stack = np.stack(list(self.motion_buf), axis=0).astype(np.int16)
            std = stack.std(axis=0)
            stable = std < self.cfg.motion_std_thresh
            masked[~stable] = self.cfg.mask_fill_value
        if self.cfg.presenter_roi is not None:
            x1, y1, x2, y2 = self.cfg.presenter_roi
            H, W = gray.shape
            masked[int(y1 * H):int(y2 * H), int(x1 * W):int(x2 * W)] = self.cfg.mask_fill_value
        return masked

    def _phash(self, gray):
        from PIL import Image
        import imagehash

        return imagehash.phash(Image.fromarray(gray), hash_size=self.cfg.phash_size)

    def _ssim(self, a, b):
        import cv2
        from skimage.metrics import structural_similarity as ssim

        if a.shape[1] > self.cfg.ssim_short_w:
            scale = self.cfg.ssim_short_w / a.shape[1]
            a = cv2.resize(a, (self.cfg.ssim_short_w, int(a.shape[0] * scale)), interpolation=cv2.INTER_AREA)
            b = cv2.resize(b, (self.cfg.ssim_short_w, int(b.shape[0] * scale)), interpolation=cv2.INTER_AREA)
        return float(ssim(a, b, data_range=255))

    def _edge_map(self, gray):
        import cv2
        import numpy as np

        g = cv2.GaussianBlur(gray, (3, 3), 0)
        e = cv2.Canny(g, 50, 150)
        return (e > 0).astype(np.uint8)

    def _build_signature(self, prev, curr):
        import numpy as np

        E1, E2 = self._edge_map(prev), self._edge_map(curr)
        union = int(np.logical_or(E1, E2).sum())
        if union == 0:
            return 0.0, 0.0
        add = float(np.logical_and(E2, np.logical_not(E1)).sum()) / union
        rem = float(np.logical_and(E1, np.logical_not(E2)).sum()) / union
        return add, rem

    def _is_build_step(self, prev, curr, ssim_val):
        if ssim_val < self.cfg.ssim_build:
            return False
        add, rem = self._build_signature(prev, curr)
        return add <= self.cfg.build_add_ratio_max and rem <= self.cfg.build_remove_ratio_max

    def _global_dedup(self, segments):
        clusters: list[dict] = []
        for i, seg in enumerate(segments):
            assigned = False
            for c in clusters:
                rep = segments[c["rep_idx"]]
                if rep.phash - seg.phash <= self.cfg.cluster_merge_ham:
                    if self.cfg.cluster_verify_ssim is not None:
                        if self._ssim(rep.keyframe, seg.keyframe) < self.cfg.cluster_verify_ssim:
                            continue
                    c["members"].append(i)
                    assigned = True
                    break
            if not assigned:
                clusters.append({"rep_idx": i, "members": [i]})
        for cid, c in enumerate(clusters):
            for idx in c["members"]:
                segments[idx].cluster_id = cid
        return clusters

    def _ser(self, s):
        return {"start": float(s.start), "end": float(s.end), "cluster_id": s.cluster_id, "builds": s.builds}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("video", help="Path to input video file")
    p.add_argument("--out-dir", required=True, help="Output directory for slides")
    p.add_argument("--fps", type=float, default=2.0, help="Sampling rate (default: 2.0)")
    p.add_argument("--build-policy", choices=["build_collapse", "build_preserve"], default="build_collapse")
    args = p.parse_args()

    video_path = Path(args.video)
    if not video_path.exists():
        print(f"error: {video_path} not found", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = out_dir / "metadata.json"

    if metadata_path.exists() and metadata_path.stat().st_size > 0:
        print(f"skip: {metadata_path} already exists")
        return 0

    import cv2

    dedup = SlideDeduplicator(fps_sample=args.fps, build_policy=args.build_policy)
    result = dedup.process_video(str(video_path))

    slides = []
    for cid, cluster in enumerate(result["clusters"]):
        rep_idx = cluster["rep_idx"]
        seg_data = result["segments"][rep_idx]
        segment = dedup.segments[rep_idx]

        slide_path = out_dir / f"slide_{cid + 1:03d}.jpg"
        cv2.imwrite(str(slide_path), segment.keyframe_original)

        slides.append({
            "slide_number": cid + 1,
            "image_path": str(slide_path),
            "timestamp": seg_data["start"],
            "duration": seg_data["end"] - seg_data["start"],
            "num_occurrences": len(cluster["members"]),
            "num_builds": len(seg_data.get("builds") or []),
        })

    metadata = {
        "video_path": str(video_path),
        "fps_sample": args.fps,
        "build_policy": args.build_policy,
        "num_unique_slides": len(slides),
        "num_segments": len(result["segments"]),
        "slides": slides,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2))

    print(f"wrote {len(slides)} unique slides ({len(result['segments'])} segments) to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
