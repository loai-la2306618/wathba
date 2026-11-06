"""Hugging Face person detection + pose inference; loaded lazily."""

import os
import threading
from functools import lru_cache

import numpy as np

POSE_ID = "usyd-community/vitpose-plus-small"
DETECTOR_ID = "PekingU/rtdetr_r18vd"
INFERENCE_LOCK = threading.Lock()


@lru_cache(maxsize=1)
def models():
    import torch
    from transformers import (
        AutoImageProcessor,
        AutoModelForObjectDetection,
        VitPoseForPoseEstimation,
    )
    torch.set_num_threads(4)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    offline = os.getenv("WATHBA_OFFLINE", "0") == "1"
    pose_processor = AutoImageProcessor.from_pretrained(POSE_ID, local_files_only=offline, use_fast=False)
    pose_model = VitPoseForPoseEstimation.from_pretrained(POSE_ID, local_files_only=offline).to(device).eval()
    detector_processor = AutoImageProcessor.from_pretrained(DETECTOR_ID, local_files_only=offline, use_fast=False)
    detector_model = AutoModelForObjectDetection.from_pretrained(DETECTOR_ID, local_files_only=offline).to(device).eval()
    return torch, device, pose_processor, pose_model, detector_processor, detector_model


def intersection_over_union(a, b):
    lo, hi = np.maximum(a[:2], b[:2]), np.minimum(a[2:], b[2:])
    intersect = float(np.prod(np.maximum(0, hi - lo)))
    area_a, area_b = float(np.prod(a[2:] - a[:2])), float(np.prod(b[2:] - b[:2]))
    return intersect / max(1, area_a + area_b - intersect)


def select_person(boxes, previous=None):
    """Keep the same subject; ambiguous initial detections require a subject crop."""
    boxes = np.asarray(boxes, float).reshape(-1, 4)
    if not len(boxes):
        return None, "No person detected"
    if previous is not None:
        overlaps = [intersection_over_union(b, previous) for b in boxes]
        index = int(np.argmax(overlaps))
        if overlaps[index] < .15:
            return None, "Selected person left the tracked region"
        return boxes[index], ""
    areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    order = np.argsort(areas)[::-1]
    if len(order) > 1 and areas[order[0]] < areas[order[1]] * 1.3:
        return None, "Multiple similar-sized people; select a subject region"
    return boxes[order[0]], ""


class PoseTracker:
    def __init__(self, roi=None):
        self.roi = roi
        self.box = None
        self.last_detection = -float("inf")
        self.reason = ""
        self.people = 0
        self.tracking_visible = False

    def update(self, rgb, seconds):
        from PIL import Image
        torch, device, processor, model, det_processor, detector = models()
        height, width = rgb.shape[:2]
        if self.roi:
            x1, y1, x2, y2 = self.roi
            offset = np.array([round(x1 * width), round(y1 * height)])
            rgb = rgb[offset[1]:round(y2 * height), offset[0]:round(x2 * width)]
        else:
            offset = np.zeros(2)
        image = Image.fromarray(rgb)
        with INFERENCE_LOCK, torch.inference_mode():
            if not self.tracking_visible or self.box is None or seconds - self.last_detection >= .5:
                inputs = det_processor(images=image, return_tensors="pt").to(device)
                result = det_processor.post_process_object_detection(detector(**inputs), target_sizes=[(image.height, image.width)], threshold=.6)[0]
                boxes = result["boxes"][result["labels"] == 0].cpu().numpy()
                box, self.reason = select_person(boxes, self.box)
                self.people = len(boxes)
                self.last_detection = seconds
                if box is None:
                    self.tracking_visible = False
                    # Retain the subject region for matching rather than silently switching people.
                    return None
                self.box = box.copy()
                self.tracking_visible = True
            box = self.box.copy()
            box[0::2] = np.clip(box[0::2], 0, image.width)
            box[1::2] = np.clip(box[1::2], 0, image.height)
            box[2:] -= box[:2]
            if min(box[2:]) < 20:
                self.reason = "Person is too small in the recording"
                return None
            inputs = processor(images=image, boxes=[[box.tolist()]], return_tensors="pt").to(device)
            outputs = model(**inputs, dataset_index=torch.tensor([0], device=device))
            pose = processor.post_process_pose_estimation(outputs, boxes=[[box.tolist()]])[0][0]
            points = pose["keypoints"].cpu().numpy() + offset
            scores = pose["scores"].cpu().numpy().reshape(-1)
            return points, scores


def estimate(rgb):
    return PoseTracker().update(rgb, 0)
