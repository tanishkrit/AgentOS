"""
Vision Detector — Screen Element Detection via Computer Vision

Uses OpenCV template matching and image analysis to locate
UI elements (buttons, icons, text fields) on screen.

This enables the self-healing execution engine: when UI elements
move or change appearance, the vision layer adapts.
"""

import logging
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import pyautogui

logger = logging.getLogger(__name__)


class Detector:
    """
    Finds visual elements on screen using template matching.
    """

    def find_element(
        self,
        template_path: str,
        confidence: float = 0.8,
        region: tuple[int, int, int, int] | None = None,
    ) -> tuple[int, int] | None:
        """
        Find a UI element on screen by matching a template image.

        Args:
            template_path: Path to the template image (e.g., a button icon).
            confidence: Minimum match confidence (0.0 to 1.0).
            region: Optional (x, y, width, height) to limit the search area.

        Returns:
            (x, y) center coordinates of the best match, or None if not found.
        """
        template = cv2.imread(template_path, cv2.IMREAD_COLOR)
        if template is None:
            logger.error(f"Template image not found: {template_path}")
            return None

        # Capture current screen
        screenshot = pyautogui.screenshot(region=region)
        screen = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        # Template matching
        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= confidence:
            # Calculate center of the matched region
            h, w = template.shape[:2]
            center_x = max_loc[0] + w // 2
            center_y = max_loc[1] + h // 2

            # Adjust for region offset
            if region:
                center_x += region[0]
                center_y += region[1]

            logger.info(
                f"Found element at ({center_x}, {center_y}) "
                f"with confidence {max_val:.2f}"
            )
            return (center_x, center_y)
        else:
            logger.warning(
                f"Element not found. Best confidence: {max_val:.2f} "
                f"(required: {confidence})"
            )
            return None

    def find_all_elements(
        self,
        template_path: str,
        confidence: float = 0.8,
    ) -> list[tuple[int, int]]:
        """
        Find ALL occurrences of a template on screen.

        Returns:
            List of (x, y) center coordinates for each match.
        """
        template = cv2.imread(template_path, cv2.IMREAD_COLOR)
        if template is None:
            logger.error(f"Template image not found: {template_path}")
            return []

        screenshot = pyautogui.screenshot()
        screen = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= confidence)

        h, w = template.shape[:2]
        matches = []
        for pt in zip(*locations[::-1]):
            center = (pt[0] + w // 2, pt[1] + h // 2)
            matches.append(center)

        # Remove near-duplicates (within 10px)
        filtered = []
        for m in matches:
            if not any(abs(m[0] - f[0]) < 10 and abs(m[1] - f[1]) < 10 for f in filtered):
                filtered.append(m)

        logger.info(f"Found {len(filtered)} instances of template.")
        return filtered

    def wait_for_element(
        self,
        template_path: str,
        timeout: float = 10.0,
        interval: float = 0.5,
        confidence: float = 0.8,
    ) -> tuple[int, int] | None:
        """
        Wait for an element to appear on screen.

        Polls at the given interval until the element is found or timeout.

        Returns:
            (x, y) coordinates if found, None if timed out.
        """
        import time

        start = time.time()
        while time.time() - start < timeout:
            result = self.find_element(template_path, confidence)
            if result:
                return result
            time.sleep(interval)

        logger.warning(f"Timed out waiting for element: {template_path}")
        return None
