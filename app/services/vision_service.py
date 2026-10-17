"""Opt-in, memory-only landmark inference. Never store or forward camera images."""
from pathlib import Path
from threading import Lock
import io
import time

from PIL import Image, UnidentifiedImageError


class VisionBusy(Exception):
    pass


class VisionEngine:
    def __init__(self, models):
        self.models = Path(models)
        self.lock = Lock()
        self.tasks = {}

    def detect(self, raw, face=True, hands=True):
        # No queue of stale camera frames and no unbounded model/session pool.
        if not self.lock.acquire(blocking=False):
            raise VisionBusy()
        try:
            with Image.open(io.BytesIO(raw)) as image:
                if image.format != 'JPEG' or not (1 <= image.width <= 640 and 1 <= image.height <= 480):
                    raise ValueError('Expected JPEG up to 640x480')
                rgb = image.convert('RGB')
            import mediapipe as mp
            import numpy as np
            vision = mp.tasks.vision
            pixels = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.asarray(rgb))
            started = time.perf_counter()
            result = {'face': None, 'hand': None}
            for name, enabled in [('face', face), ('hand', hands)]:
                if not enabled:
                    continue
                if name not in self.tasks:
                    base = mp.tasks.BaseOptions(model_asset_path=str(self.models / (name + '_landmarker.task')))
                    # IMAGE mode never carries one user's tracking state to another.
                    options = (vision.FaceLandmarkerOptions(base_options=base, num_faces=1)
                               if name == 'face' else vision.HandLandmarkerOptions(base_options=base, num_hands=2))
                    task_type = vision.FaceLandmarker if name == 'face' else vision.HandLandmarker
                    self.tasks[name] = task_type.create_from_options(options)
                detected = self.tasks[name].detect(pixels)
                points = detected.face_landmarks if name == 'face' else detected.hand_landmarks
                result[name] = {'faceLandmarks' if name == 'face' else 'landmarks': [
                    [{'x': p.x, 'y': p.y, 'z': p.z} for p in group] for group in points]}
            result['elapsedMs'] = round((time.perf_counter() - started) * 1000, 2)
            return result
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
            raise ValueError('Invalid camera image') from exc
        finally:
            self.lock.release()

    def close(self):
        with self.lock:
            for task in self.tasks.values():
                task.close()
            self.tasks.clear()
