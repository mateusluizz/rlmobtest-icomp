"""Multimodal support utilities for future image-based transcription."""

import base64
from pathlib import Path


def encode_image_to_base64(image_path: str | Path) -> str:
    """
    Encode an image file to base64 string.

    Args:
        image_path: Path to the image file

    Returns:
        Base64 encoded string of the image
    """
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


class MultimodalInput:
    """
    Container for multimodal test case inputs.

    Attributes:
        text: The raw interaction log text
        images: List of image paths or base64 encoded images
        metadata: Additional context metadata
    """

    def __init__(
        self,
        text: str,
        images: list[str | Path] | None = None,
        metadata: dict | None = None,
    ):
        self.text = text
        self.images = images or []
        self.metadata = metadata or {}

    def get_encoded_images(self) -> list[str]:
        """Get base64 encoded versions of all images."""
        encoded = []
        for img in self.images:
            if isinstance(img, (str, Path)) and Path(img).exists():
                encoded.append(encode_image_to_base64(img))
            elif isinstance(img, str):
                # Assume already base64 encoded
                encoded.append(img)
        return encoded
