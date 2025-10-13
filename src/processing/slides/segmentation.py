# slideseg.py
# Robust unique-slide detection with progressive-reveal (build) handling.
# Author: Your Team
# License: MIT

import cv2
import numpy as np
from PIL import Image
import imagehash
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from skimage.metrics import structural_similarity as ssim


@dataclass
class Config:
    # Sampling / preprocessing
    target_width: int = 1024
    fps_sample: float = 2.0  # frames per second sampling

    # Masking
    presenter_roi: Optional[Tuple[float, float, float, float]] = None  # (x1,y1,x2,y2) in [0,1]
    motion_buffer_len: int = 7
    motion_std_thresh: float = 4.0
    mask_fill_value: int = 128

    # Hashing thresholds (Hamming)
    # Keep-same if ham <= H1; likely-new if ham >= H2; between → confirm with SSIM/build logic
    phash_size: int = 8  # 8→64b; 16→256b
    ham_keep: int = 10   # H1
    ham_new: int = 18    # H2

    # SSIM thresholds
    ssim_keep: float = 0.93  # keep under normal (non-build) check

    # Build detection (progressive reveals)
    build_policy: str = "build_collapse"  # or "build_preserve"
    ssim_build: float = 0.98
    build_add_ratio_max: float = 0.15
    build_remove_ratio_max: float = 0.03

    # Decision hysteresis
    confirm_k: int = 3     # consecutive mismatches before cutting
    min_seg_secs: float = 2.0

    # Global de-dup
    cluster_merge_ham: int = 10
    cluster_verify_ssim: Optional[float] = 0.92  # set None to skip

    # Speed
    ssim_short_w: int = 640  # downscale width for SSIM


@dataclass
class Segment:
    start: float
    end: float
    keyframe: np.ndarray  # Processed grayscale for comparison
    keyframe_original: np.ndarray  # Original color frame
    phash: Any
    builds: List[Dict[str, Any]] = field(default_factory=list)
    cluster_id: Optional[int] = None


class SlideDeduplicator:
    def __init__(self, **kwargs):
        self.cfg = Config(**kwargs)
        self._reset_runtime()

    def _reset_runtime(self):
        self.curr_hash = None
        self.curr_keyframe = None
        self.curr_keyframe_original = None
        self.curr_start_t = None
        self.pending_fail = 0
        self.motion_buf = deque(maxlen=self.cfg.motion_buffer_len)
        self.segments: List[Segment] = []
        self._open_builds = []

    # ---------- Public API ----------

    def process_video(self, path: str) -> Dict[str, Any]:
        self._reset_runtime()

        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {path}")

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

        # Global de-dup
        clusters = self._global_dedup(self.segments)

        return {
            "segments": [self._ser_seg(s) for s in self.segments],
            "clusters": clusters,
        }

    # ---------- Core Pipeline ----------

    def _step(self, t: float, frame_bgr: np.ndarray):
        gray = self._preprocess(frame_bgr)
        masked = self._apply_mask(gray)  # motion mask takes effect after buffer fills
        h = self._phash(masked)

        if self.curr_hash is None:
            self._start_segment(t, masked, h, frame_bgr)
            return

        ham = self.curr_hash - h
        # 1) Fast path: hash says "same"
        if ham <= self.cfg.ham_keep:
            self.pending_fail = 0
            # Optional: build update when extremely similar? We do build in borderline branch.
            return

        # 2) Borderline: confirm with SSIM & build logic
        if ham < self.cfg.ham_new:
            s = self._ssim(self.curr_keyframe, masked)
            # If very similar, check for build
            if s >= self.cfg.ssim_keep:
                # Build detection (stricter ssim + small edge deltas)
                if self._is_build_step(self.curr_keyframe, masked, s):
                    self._record_build(t, masked, frame_bgr)
                    self.pending_fail = 0
                    return
                # Similar enough to be same slide (non-build minor noise)
                self.pending_fail = 0
                return

        # 3) Likely new slide: require K consecutive mismatches and min duration
        self.pending_fail += 1
        if self.pending_fail >= self.cfg.confirm_k:
            if (t - self.curr_start_t) >= self.cfg.min_seg_secs:
                self._end_segment(t)
                self._start_segment(t, masked, h, frame_bgr)
            # if too short, keep extending current segment and reset counter
            self.pending_fail = 0

    # ---------- Segment Bookkeeping ----------

    def _start_segment(self, t: float, keyframe: np.ndarray, ph, original_frame: np.ndarray):
        self.curr_start_t = t
        self.curr_keyframe = keyframe
        self.curr_keyframe_original = original_frame
        self.curr_hash = ph
        self.pending_fail = 0

    def _end_segment(self, t: float):
        if self.curr_start_t is None:
            return
        seg = Segment(
            start=self.curr_start_t,
            end=t,
            keyframe=self.curr_keyframe,
            keyframe_original=self.curr_keyframe_original,
            phash=self.curr_hash,
            builds=self._open_builds.copy(),
        )
        self.segments.append(seg)
        self.curr_start_t = None
        self.curr_keyframe = None
        self.curr_keyframe_original = None
        self.curr_hash = None
        self.pending_fail = 0
        self._open_builds = []

    def _record_build(self, t: float, new_img: np.ndarray, original_frame: np.ndarray):
        # Build handling per policy
        add_ratio, rem_ratio = self._build_signature(self.curr_keyframe, new_img)
        build_entry = {
            "t": t,
            "add_ratio": float(add_ratio),
            "rem_ratio": float(rem_ratio),
        }
        # Update the *current* (open) segment
        if self.cfg.build_policy == "build_collapse":
            # record step; update keyframe/hash to the latest fully revealed frame
            # builds get attached when we finalize the segment
            self.curr_keyframe = new_img
            self.curr_keyframe_original = original_frame
            self.curr_hash = self._phash(new_img)
            self._open_builds.append(build_entry)

        elif self.cfg.build_policy == "build_preserve":
            # End current subslide and start a new subslide; keep builds empty (each is its own)
            now = t
            # emit the current segment if it exists long enough; otherwise extend
            if (now - self.curr_start_t) >= max(0.5, self.cfg.min_seg_secs / 2):
                self._end_segment(now)
                # start new subslide with the new image
                self._start_segment(now, new_img, self._phash(new_img), original_frame)
            else:
                # if the subslide is too short, just update keyframe/hash in place
                self.curr_keyframe = new_img
                self.curr_keyframe_original = original_frame
                self.curr_hash = self._phash(new_img)
                self._open_builds.append(build_entry)

        else:
            raise ValueError(f"Unknown build_policy: {self.cfg.build_policy}")

    # ---------- Preprocess / Mask / Features ----------

    def _preprocess(self, frame_bgr: np.ndarray) -> np.ndarray:
        h, w = frame_bgr.shape[:2]
        scale = self.cfg.target_width / float(w)
        frame = cv2.resize(frame_bgr, (self.cfg.target_width, int(h * scale)),
                           interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return gray

    def _apply_mask(self, gray: np.ndarray) -> np.ndarray:
        # Prefer motion-stability mask; fall back to ROI crop-out if provided
        self.motion_buf.append(gray)
        masked = gray.copy()

        # Motion-stability mask (after buffer is full)
        if len(self.motion_buf) == self.motion_buf.maxlen:
            stack = np.stack(list(self.motion_buf), axis=0).astype(np.int16)
            std = stack.std(axis=0)
            stable = (std < self.cfg.motion_std_thresh)
            masked[~stable] = self.cfg.mask_fill_value

        # Presenter ROI mask (if known and desired)
        if self.cfg.presenter_roi is not None:
            x1, y1, x2, y2 = self.cfg.presenter_roi
            H, W = gray.shape
            X1, Y1, X2, Y2 = int(x1 * W), int(y1 * H), int(x2 * W), int(y2 * H)
            masked[Y1:Y2, X1:X2] = self.cfg.mask_fill_value

        return masked

    def _phash(self, gray: np.ndarray):
        pil = Image.fromarray(gray)
        return imagehash.phash(pil, hash_size=self.cfg.phash_size)

    def _ssim(self, a: np.ndarray, b: np.ndarray) -> float:
        if a.shape[1] > self.cfg.ssim_short_w:
            scale = self.cfg.ssim_short_w / a.shape[1]
            a = cv2.resize(a, (self.cfg.ssim_short_w, int(a.shape[0] * scale)), interpolation=cv2.INTER_AREA)
            b = cv2.resize(b, (self.cfg.ssim_short_w, int(b.shape[0] * scale)), interpolation=cv2.INTER_AREA)
        return float(ssim(a, b, data_range=255))

    # ---------- Build detection ----------

    def _edge_map(self, gray: np.ndarray) -> np.ndarray:
        g = cv2.GaussianBlur(gray, (3, 3), 0)
        e = cv2.Canny(g, 50, 150)
        return (e > 0).astype(np.uint8)

    def _build_signature(self, prev_img: np.ndarray, curr_img: np.ndarray) -> Tuple[float, float]:
        E1, E2 = self._edge_map(prev_img), self._edge_map(curr_img)
        union = int(np.logical_or(E1, E2).sum())
        if union == 0:
            return 0.0, 0.0
        add_ratio = float(np.logical_and(E2, np.logical_not(E1)).sum()) / union
        rem_ratio = float(np.logical_and(E1, np.logical_not(E2)).sum()) / union
        return add_ratio, rem_ratio

    def _is_build_step(self, prev_img: np.ndarray, curr_img: np.ndarray, ssim_val: float) -> bool:
        if ssim_val < self.cfg.ssim_build:
            return False
        add_ratio, rem_ratio = self._build_signature(prev_img, curr_img)
        return (add_ratio <= self.cfg.build_add_ratio_max) and (rem_ratio <= self.cfg.build_remove_ratio_max)

    # ---------- Global de-dup ----------

    def _global_dedup(self, segments: List[Segment]) -> List[Dict[str, Any]]:
        clusters: List[Dict[str, Any]] = []
        for i, seg in enumerate(segments):
            assigned = False
            for c in clusters:
                rep_idx = c["rep_idx"]
                rep = segments[rep_idx]
                ham = rep.phash - seg.phash
                if ham <= self.cfg.cluster_merge_ham:
                    # Optional SSIM verification on keyframes
                    if self.cfg.cluster_verify_ssim is not None:
                        s = self._ssim(rep.keyframe, seg.keyframe)
                        if s < self.cfg.cluster_verify_ssim:
                            continue
                    c["members"].append(i)
                    assigned = True
                    break
            if not assigned:
                clusters.append({"rep_idx": i, "members": [i]})

        # Write back cluster IDs
        for cid, c in enumerate(clusters):
            for idx in c["members"]:
                segments[idx].cluster_id = cid

        return clusters

    # ---------- Serialization ----------

    def _ser_seg(self, s: Segment) -> Dict[str, Any]:
        # Note: we don't export raw images; caller can save frames if needed.
        return dict(
            start=float(s.start),
            end=float(s.end),
            cluster_id=s.cluster_id,
            builds=s.builds,
        )
