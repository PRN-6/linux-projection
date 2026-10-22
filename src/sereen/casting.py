"""Screen casting module using GStreamer and PipeWire.

This module handles the capture of the Linux desktop and attempts to stream it
to the projector's network projection service.
"""

from __future__ import annotations

import subprocess
import logging
from typing import Optional
from .models import Projector

logger = logging.getLogger(__name__)

class CastingEngine:
    """Handles the GStreamer pipeline for screen capture and streaming."""

    def __init__(self) -> None:
        self.process: Optional[subprocess.Popen] = None

    def start_cast(self, projector: Projector) -> bool:
        """
        Start streaming the desktop to the projector.

        Uses a PipeWire source (via GStreamer) and sends it over the
        projector's streaming port (usually 8889 or proprietary).
        """
        try:
            # This is a conceptual GStreamer pipeline for Linux screen casting:
            # 1. Capture screen via PipeWire (pipewiresrc)
            # 2. Encode using H.264 (x264enc)
            # 3. Payloads via RTP (rtpjpegpay or rtp h264pay)
            # 4. Send to Projector IP

            pipeline = (
                "pipewiresrc ! videoconvert ! x264enc tune=zerolatency ! "
                f"rtph264pay ! udpsink host={projector.host} port=8889"
            )

            logger.info(f"Starting cast pipeline: {pipeline}")

            self.process = subprocess.Popen(
                ["gst-launch-1.0", pipeline],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to start cast: {e}")
            return False

    def stop_cast(self) -> None:
        """Stop the active stream."""
        if self.process:
            self.process.terminate()
            self.process = None
            logger.info("Casting stopped.")

def cast_to_projector(projector: Projector):
    """Helper function to trigger casting."""
    engine = CastingEngine()
    return engine.start_cast(projector)
