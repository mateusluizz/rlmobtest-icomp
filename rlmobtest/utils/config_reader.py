#!/usr/bin/env python3
"""
Configuration reader module for parsing settings files.
"""

import json

from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    """Model for application configuration."""

    apk_name: str = Field(..., description="Name of the APK file")
    package_name: str = Field(..., description="Android package name")
    is_coverage: bool = Field(default=False, description="Coverage analysis flag")
    is_req_analysis: bool = Field(
        default=False, alias="is_req", description="Requirement analysis flag"
    )
    time_exploration: int = Field(
        ..., description="Time in seconds for exploration training (Step 1 / standalone train)"
    )
    time_guided: int = Field(
        ..., description="Time in seconds for guided training with requirements (Step 3)"
    )
    source_code: str = Field(default="", description="Source code zip in inputs/source_codes/")

    def to_tuple(self) -> tuple:
        """Convert to legacy tuple format for backwards compatibility."""
        return (
            self.apk_name,
            self.package_name,
            self.is_coverage,
            self.is_req_analysis,
            str(self.time_exploration),
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
