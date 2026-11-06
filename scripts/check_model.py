"""Real inference smoke check on a local image, never synthetic landmarks."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2

from wathba.inference import estimate
from wathba.motion import measure_keypoints

image = cv2.imread(sys.argv[1])
if image is None:
    raise SystemExit("Provide a readable local image.")
pose = estimate(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
if pose is None:
    raise SystemExit("Image must show exactly one detected person.")
points, scores = pose
assert points.shape == (17, 2)
print({"landmarks": len(points), "right_angle_and_confidence": measure_keypoints(points, scores, "Right"),
       "left_angle_and_confidence": measure_keypoints(points, scores, "Left")})
