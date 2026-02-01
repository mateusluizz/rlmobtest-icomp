#!/usr/bin/env python3
"""
Configuration reader module for parsing settings files.
"""

import json

from pydantic import BaseModel, Field, field_validator


class AppConfig(BaseModel):
    """Model for application configuration."""

    apk_name: str = Field(..., description="Name of the APK file")
    package_name: str = Field(..., description="Android package name")
    resolution: str = Field(..., description="Screen resolution in WxH format")
    is_coverage: bool = Field(default=False, description="Coverage analysis flag")
    is_req_analysis: bool = Field(
        default=False, description="Requirement analysis flag"
    )
    time: int = Field(..., description="Execution time in seconds")

    @field_validator("resolution")
    @classmethod
    def validate_resolution(cls, v: str) -> str:
        """Validate resolution format (WxH)."""
        if "x" not in v:
            raise ValueError("Resolution must be in format WIDTHxHEIGHT")
        parts = v.split("x")
        if len(parts) != 2:
            raise ValueError("Resolution must be in format WIDTHxHEIGHT")
        try:
            int(parts[0])
            int(parts[1])
        except ValueError as e:
            raise ValueError("Resolution width and height must be integers") from e
        return v

    @property
    def width(self) -> int:
        """Get screen width from resolution."""
        return int(self.resolution.split("x")[0])

    @property
    def height(self) -> int:
        """Get screen height from resolution."""
        return int(self.resolution.split("x")[1])

    def to_tuple(self) -> tuple:
        """Convert to legacy tuple format for backwards compatibility."""
        return (
            self.apk_name,
            self.package_name,
            str(self.width),
            str(self.height),
            self.is_coverage,
            self.is_req_analysis,
            str(self.time),
        )


class ConfRead:
    """Configuration reader for settings.json file."""

    def __init__(self, settingsfile: str):
        self.settingsfile = settingsfile

    def read_setting(self) -> AppConfig:
        """Read a single configuration (first one in the list)."""
        configs = self.read_all_settings()
        if not configs:
            raise ValueError("No configurations found in settings file")
        return configs[0]

    def read_all_settings(self) -> list[AppConfig]:
        """Read all configurations from the JSON file.

        Raises:
            FileNotFoundError: If settings file doesn't exist
            json.JSONDecodeError: If JSON is invalid
            ValueError: If configuration validation fails
        """
        with open(self.settingsfile, encoding="utf-8") as f:
            data = json.load(f)

        # Garante que é uma lista
        if not isinstance(data, list):
            data = [data]

        # Valida e cria objetos Pydantic (pode lançar ValidationError)
        configs = [AppConfig(**config) for config in data]
        return configs

    def read_all_settings_safe(self) -> list[AppConfig]:
        """Read all configurations, returning empty list on error.

        This is a safe version that won't raise exceptions.
        Use this when you want to handle missing/invalid configs gracefully.
        """
        try:
            return self.read_all_settings()
        except Exception as e:
            print(f"Warning: Failed to read settings - {e}")
            return []

    def read_setting_tuple(self) -> tuple | None:
        """Read single configuration as tuple (legacy format)."""
        config = self.read_setting()
        return config.to_tuple() if config else None

    def read_all_settings_tuple(self) -> list[tuple]:
        """Read all configurations as tuples (legacy format)."""
        configs = self.read_all_settings()
        return [config.to_tuple() for config in configs]
