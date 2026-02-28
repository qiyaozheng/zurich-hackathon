"""Gemini Vision tools — multi-mode inspection with structured output."""

from __future__ import annotations

import base64
import io
import json
import logging
from typing import Any

import cv2
from PIL import Image

from config import settings
from models import DefectInspection, PartClassification, PlacementVerification

logger = logging.getLogger(__name__)

_genai_client = None


def _get_client():
    global _genai_client
    if _genai_client is not None:
        return _genai_client
    from google import genai
    _genai_client = genai.Client(api_key=settings.google_api_key)
    return _genai_client


# ---------------------------------------------------------------------------
# Camera — ZED 2i primary, OpenCV fallback
# ---------------------------------------------------------------------------

class Camera:
    """Unified camera interface: tries ZED 2i SDK first, falls back to OpenCV."""

    def __init__(self, device_id: int = 0, width: int = 1280, height: int = 720,
                 fps: int = 30, camera_type: str = "zed"):
        self._device_id = device_id
        self._width = width
        self._height = height
        self._fps = fps
        self._requested_type = camera_type
        self._backend: str = "none"
        self._zed = None          # pyzed.sl.Camera
        self._zed_mat = None      # pyzed.sl.Mat for reuse
        self._zed_runtime = None  # pyzed.sl.RuntimeParameters
        self._cap: cv2.VideoCapture | None = None  # OpenCV fallback

    def open(self) -> None:
        if self._requested_type == "zed":
            if self._try_open_zed():
                return
            logger.warning("ZED 2i not available — falling back to OpenCV")

        self._try_open_opencv()

    def _try_open_zed(self) -> bool:
        try:
            import pyzed.sl as sl

            zed = sl.Camera()
            init_params = sl.InitParameters()
            init_params.camera_resolution = sl.RESOLUTION.HD1080
            init_params.camera_fps = self._fps
            init_params.depth_mode = sl.DEPTH_MODE.NONE  # we only need RGB

            err = zed.open(init_params)
            if err != sl.ERROR_CODE.SUCCESS:
                logger.warning("ZED open failed: %s", err)
                return False

            self._zed = zed
            self._zed_mat = sl.Mat()
            self._zed_runtime = sl.RuntimeParameters()
            self._backend = "zed"
            logger.info("ZED 2i camera opened — %dx%d @ %dfps", self._width, self._height, self._fps)
            return True
        except ImportError:
            logger.info("pyzed SDK not installed — ZED not available")
            return False
        except Exception as e:
            logger.warning("ZED init error: %s", e)
            return False

    def _try_open_opencv(self) -> None:
        self._cap = cv2.VideoCapture(self._device_id)
        if self._cap.isOpened():
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
            self._backend = "opencv"
            logger.info("OpenCV camera opened — device %d", self._device_id)
        else:
            self._backend = "none"
            logger.warning("No camera available")

    def is_open(self) -> bool:
        if self._backend == "zed":
            return self._zed is not None and self._zed.is_opened()
        if self._backend == "opencv":
            return self._cap is not None and self._cap.isOpened()
        return False

    def _grab_zed_frame(self) -> Any | None:
        """Grab a frame from ZED as a numpy BGR array."""
        import pyzed.sl as sl
        if self._zed.grab(self._zed_runtime) == sl.ERROR_CODE.SUCCESS:
            self._zed.retrieve_image(self._zed_mat, sl.VIEW.LEFT)
            # ZED returns BGRA — convert to BGR for consistency with OpenCV
            bgra = self._zed_mat.get_data()
            return cv2.cvtColor(bgra, cv2.COLOR_BGRA2BGR)
        return None

    def _grab_opencv_frame(self) -> Any | None:
        if not self._cap or not self._cap.isOpened():
            return None
        ret, frame = self._cap.read()
        return frame if ret else None

    def _grab_frame(self) -> Any | None:
        if self._backend == "zed":
            return self._grab_zed_frame()
        return self._grab_opencv_frame()

    def capture(self) -> Image.Image | None:
        frame = self._grab_frame()
        if frame is None:
            return None
        return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    def capture_base64(self) -> str | None:
        frame = self._grab_frame()
        if frame is None:
            return None
        _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return base64.b64encode(buffer).decode("utf-8")

    def generate_mjpeg(self):
        """Generator yielding MJPEG frames for streaming."""
        while self.is_open():
            frame = self._grab_frame()
            if frame is None:
                break
            _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
            )

    def release(self) -> None:
        if self._backend == "zed" and self._zed:
            self._zed.close()
            self._zed = None
        if self._cap:
            self._cap.release()
            self._cap = None
        self._backend = "none"


def image_to_base64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ---------------------------------------------------------------------------
# Gemini Vision — Structured Output
# ---------------------------------------------------------------------------

async def gemini_classify(image: Image.Image, prompt: str) -> PartClassification:
    """Classify a part using Gemini Vision with structured JSON output."""
    from google import genai

    client = _get_client()

    full_prompt = (
        f"{prompt}\n\n"
        "Return a JSON object with these exact fields:\n"
        '{"color": "red|blue|green|yellow|other", "color_hex": "#RRGGBB", '
        '"size_mm": <float>, "size_category": "small|medium|large", '
        '"part_type": "<string>", "shape": "round|square|irregular", '
        '"confidence": <0.0-1.0>}'
    )

    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=[full_prompt, image],
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        data = json.loads(response.text)
        return PartClassification(**data)
    except Exception as e:
        logger.error("Vision classify failed: %s", e)
        return PartClassification(confidence=0.0)


async def gemini_inspect_defects(image: Image.Image, prompt: str) -> DefectInspection:
    """Inspect for defects using Gemini Vision with structured JSON output."""
    from google import genai

    client = _get_client()

    full_prompt = (
        f"{prompt}\n\n"
        "Return a JSON object with these exact fields:\n"
        '{"defect_detected": <bool>, "defects": [{"type": "crack|scratch|discoloration|dent|chip|contamination", '
        '"severity": "minor|major|critical", "location": "<string>", "confidence": <0.0-1.0>}], '
        '"surface_quality": "perfect|acceptable|poor|reject", "overall_confidence": <0.0-1.0>}'
    )

    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=[full_prompt, image],
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        data = json.loads(response.text)
        return DefectInspection(**data)
    except Exception as e:
        logger.error("Vision defect inspect failed: %s", e)
        return DefectInspection(overall_confidence=0.0)


async def gemini_verify_placement(image: Image.Image, expected_bin: str) -> PlacementVerification:
    """Verify part was placed in the correct bin."""
    from google import genai

    client = _get_client()

    prompt = (
        f"Look at this image of a sorting bin. Is there a part visible? "
        f"Is it in bin '{expected_bin}'? "
        "Return JSON: {\"part_visible\": <bool>, \"correct_bin\": <bool>, "
        f"\"bin_id\": \"{expected_bin}\", \"confidence\": <0.0-1.0>}}"
    )

    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=[prompt, image],
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        data = json.loads(response.text)
        return PlacementVerification(**data)
    except Exception as e:
        logger.error("Vision verify failed: %s", e)
        return PlacementVerification(confidence=0.0)
