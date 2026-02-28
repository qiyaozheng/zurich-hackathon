"""Gemini Vision tools — multi-mode inspection with structured output."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import threading
import time
from typing import Any

import cv2
import numpy as np
from PIL import Image

from config import settings
from models import DefectInspection, PartClassification

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
# Camera — WebSocket primary, ZED 2i secondary, OpenCV fallback
# ---------------------------------------------------------------------------

class Camera:
    """Unified camera interface: WebSocket > ZED 2i SDK > OpenCV."""

    def __init__(self, device_id: int = 0, width: int = 1280, height: int = 720,
                 fps: int = 30, camera_type: str = "websocket",
                 ws_url: str = ""):
        self._device_id = device_id
        self._width = width
        self._height = height
        self._fps = fps
        self._requested_type = camera_type
        self._ws_url = ws_url
        self._backend: str = "none"

        self._zed = None
        self._zed_mat = None
        self._zed_runtime = None
        self._cap: cv2.VideoCapture | None = None

        self._ws_frame: np.ndarray | None = None
        self._ws_lock = threading.Lock()
        self._ws_connected = False
        self._ws_task: asyncio.Task | None = None
        self._ws_stop = False

    def open(self) -> None:
        if self._requested_type == "websocket" and self._ws_url:
            self._backend = "websocket"
            self._ws_connected = False
            host, port = self._parse_ws_url(self._ws_url)
            self._tcp_host = host
            self._tcp_port = port
            logger.info("TCP camera configured — %s:%d (will connect async)", host, port)
            return

        if self._requested_type in ("zed", "websocket"):
            if self._try_open_zed():
                return
            logger.warning("ZED 2i not available — falling back to OpenCV")

        self._try_open_opencv()

    @staticmethod
    def _parse_ws_url(url: str) -> tuple[str, int]:
        """Parse 'ws://host:port' or 'host:port' into (host, port)."""
        url = url.replace("ws://", "").replace("wss://", "").rstrip("/")
        if ":" in url:
            host, port_str = url.rsplit(":", 1)
            return host, int(port_str)
        return url, 5000

    async def start_ws_receiver(self) -> None:
        """Start the background TCP frame receiver. Must be called from async context."""
        if self._backend != "websocket":
            return
        self._ws_stop = False
        self._ws_task = asyncio.create_task(self._tcp_receive_loop())
        logger.info("TCP camera receiver started")

    async def _tcp_receive_loop(self) -> None:
        """Background loop: connects to ZED PC via raw TCP socket, reads framed JPEGs.

        Protocol: 8-byte unsigned long long (Q) = payload size, then payload = JPEG bytes.
        """
        import struct
        import socket as _socket

        payload_header_size = struct.calcsize("Q")

        while not self._ws_stop:
            sock = None
            try:
                sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
                sock.settimeout(5.0)

                logger.info("TCP camera connecting to %s:%d ...", self._tcp_host, self._tcp_port)
                await asyncio.to_thread(sock.connect, (self._tcp_host, self._tcp_port))
                sock.settimeout(10.0)

                self._ws_connected = True
                logger.info("TCP camera connected to %s:%d", self._tcp_host, self._tcp_port)

                buf = b""

                while not self._ws_stop:
                    while len(buf) < payload_header_size:
                        chunk = await asyncio.to_thread(sock.recv, 4096)
                        if not chunk:
                            raise ConnectionError("Connection closed by remote")
                        buf += chunk

                    msg_size = struct.unpack("Q", buf[:payload_header_size])[0]
                    buf = buf[payload_header_size:]

                    while len(buf) < msg_size:
                        chunk = await asyncio.to_thread(sock.recv, min(65536, msg_size - len(buf)))
                        if not chunk:
                            raise ConnectionError("Connection closed during frame read")
                        buf += chunk

                    frame_data = buf[:msg_size]
                    buf = buf[msg_size:]

                    arr = np.frombuffer(frame_data, dtype=np.uint8)
                    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if frame is not None:
                        with self._ws_lock:
                            self._ws_frame = frame

            except Exception as e:
                self._ws_connected = False
                if not self._ws_stop:
                    logger.warning("TCP camera disconnected: %s — reconnecting in 2s", e)
                    await asyncio.sleep(2)
            finally:
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass

    def _try_open_zed(self) -> bool:
        try:
            import pyzed.sl as sl

            zed = sl.Camera()
            init_params = sl.InitParameters()
            init_params.camera_resolution = sl.RESOLUTION.HD1080
            init_params.camera_fps = self._fps
            init_params.depth_mode = sl.DEPTH_MODE.NONE

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
        if self._backend == "websocket":
            return self._ws_connected or self._ws_frame is not None
        if self._backend == "zed":
            return self._zed is not None and self._zed.is_opened()
        if self._backend == "opencv":
            return self._cap is not None and self._cap.isOpened()
        return False

    def _grab_ws_frame(self) -> Any | None:
        with self._ws_lock:
            return self._ws_frame.copy() if self._ws_frame is not None else None

    def _grab_zed_frame(self) -> Any | None:
        import pyzed.sl as sl
        if self._zed.grab(self._zed_runtime) == sl.ERROR_CODE.SUCCESS:
            self._zed.retrieve_image(self._zed_mat, sl.VIEW.LEFT)
            bgra = self._zed_mat.get_data()
            return cv2.cvtColor(bgra, cv2.COLOR_BGRA2BGR)
        return None

    def _grab_opencv_frame(self) -> Any | None:
        if not self._cap or not self._cap.isOpened():
            return None
        ret, frame = self._cap.read()
        if not ret or frame is None:
            return None
        h, w = frame.shape[:2]
        if w > h * 2.5:
            frame = frame[:, : w // 2]
        return frame

    def _grab_frame(self) -> Any | None:
        if self._backend == "websocket":
            return self._grab_ws_frame()
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
                time.sleep(0.05)
                continue
            _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
            )
            if self._backend == "websocket":
                time.sleep(1.0 / max(self._fps, 1))

    def release(self) -> None:
        self._ws_stop = True
        if self._ws_task and not self._ws_task.done():
            self._ws_task.cancel()
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
