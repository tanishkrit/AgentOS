"""
OCR Module — Text Extraction from Screen Regions

Uses Tesseract OCR (via pytesseract) to extract text from
screenshots or specific screen regions. Used for:
- Validating that the correct page/dialog is displayed
- Reading error messages
- Extracting data from non-selectable UI text
"""

import logging
import pyautogui
import pytesseract
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)


class OCR:
    """
    Extracts text from screen captures using Tesseract OCR.
    """

    def extract_from_screen(
        self,
        region: tuple[int, int, int, int] | None = None,
    ) -> str:
        """
        Capture the screen (or a region) and extract text.

        Args:
            region: Optional (x, y, width, height) to capture.
                    If None, captures the full screen.

        Returns:
            Extracted text as a string.
        """
        screenshot = pyautogui.screenshot(region=region)
        text = pytesseract.image_to_string(screenshot)
        logger.info(f"OCR extracted {len(text)} characters from screen.")
        return text.strip()

    def extract_from_image(self, image_path: str) -> str:
        """
        Extract text from an image file.

        Args:
            image_path: Path to the image file.

        Returns:
            Extracted text as a string.
        """
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        logger.info(f"OCR extracted {len(text)} characters from {image_path}.")
        return text.strip()

    def find_text_on_screen(
        self,
        target_text: str,
        region: tuple[int, int, int, int] | None = None,
    ) -> tuple[int, int] | None:
        """
        Find the approximate screen coordinates of specific text.

        Uses OCR with bounding box data to locate where text appears.

        Args:
            target_text: The text string to search for (case-insensitive).
            region: Optional screen region to search within.

        Returns:
            (x, y) center coordinates of the text, or None if not found.
        """
        screenshot = pyautogui.screenshot(region=region)
        data = pytesseract.image_to_data(screenshot, output_type=pytesseract.Output.DICT)

        target_lower = target_text.lower()
        n_boxes = len(data["text"])

        for i in range(n_boxes):
            word = data["text"][i].strip()
            if word.lower() == target_lower:
                x = data["left"][i] + data["width"][i] // 2
                y = data["top"][i] + data["height"][i] // 2

                # Adjust for region offset
                if region:
                    x += region[0]
                    y += region[1]

                logger.info(f"Found text '{target_text}' at ({x}, {y})")
                return (x, y)

        logger.warning(f"Text '{target_text}' not found on screen.")
        return None
