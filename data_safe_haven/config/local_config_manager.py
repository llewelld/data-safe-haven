"""Local settings for account confirmation caching"""

# For postponed evaluation of annotations https://peps.python.org/pep-0563
from __future__ import annotations

from logging import Logger
from pathlib import Path
from typing import ClassVar

from data_safe_haven.directories import config_dir
from data_safe_haven.logging import get_logger
from data_safe_haven.serialisers import YAMLSerialisableModel

from .account_confirm_config import ConfigAccountConfirm


class LocalConfigManager(YAMLSerialisableModel):
    """Load local configuration from YAML files structured as follows:

    Example structure:

    accountconfirm:
        cache: true
        time_confirmed:
            azure: 1777544021
            graph: 1777544036
        timeout_in_milliseconds: 86400
        ...
    """

    _instance: ClassVar[LocalConfigManager | None] = None
    config_type: ClassVar[str] = "LocalConfigManager"
    _config_file_path: Path | None = None
    accountconfirm: ConfigAccountConfirm = ConfigAccountConfirm()
    logger: ClassVar[Logger] = get_logger()

    @staticmethod
    def default_config_file_path() -> Path:
        """Returns the default location for storing the local tool configuration"""
        return config_dir() / "local.yaml"

    @classmethod
    def getinstance(cls, config_file_path: Path | None = None) -> LocalConfigManager:
        """Returns the singleton instance of this class, creating it if necessary"""
        if not cls._instance:
            try:
                cls._instance = cls.from_file(config_file_path)
            except FileNotFoundError:
                cls._instance = LocalConfigManager()
        return cls._instance

    @classmethod
    def from_file(cls, config_file_path: Path | None = None) -> LocalConfigManager:
        """Read local configuration from YAML file"""
        if config_file_path is None:
            config_file_path = cls.default_config_file_path()
        cls.logger.debug(
            f"Reading local configuration from '[green]{config_file_path}[/]'."
        )
        instance = cls.from_filepath_raw(config_file_path)
        instance._config_file_path = config_file_path
        return instance

    def write(self, config_file_path: Path | None = None) -> None:
        """Write local configuration to YAML file"""
        if config_file_path is None:
            if self._config_file_path:
                config_file_path = self._config_file_path
            else:
                config_file_path = self.default_config_file_path()
        self._config_file_path = config_file_path
        self.to_filepath(config_file_path)
        self.logger.debug(
            f"Saved local configuration to '[green]{config_file_path}[/]'."
        )
