"""Settings only relevant for local tool execution"""

# For postponed evaluation of annotations https://peps.python.org/pep-0563
from __future__ import annotations

from logging import Logger
from time import time
from typing import ClassVar

from pydantic import BaseModel

from data_safe_haven.logging import get_logger


class ConfigAccountConfirm(BaseModel, validate_assignment=True):
    """Store account confirmation info in the local configuration

    Example structure:

    cache: true
    time_confirmed:
        azure: 1777544021
        graph: 1777544036
    timeout_in_milliseconds: 86400
    """

    logger: ClassVar[Logger] = get_logger()

    # Set to true if confirmations should be cached, false otherwise
    cache: bool = True
    # A dictionary for storing the time confirmation was last given
    # Keyed by the credential type (e.g. Azure; Graph API)
    time_confirmed: dict[str, int] = {}
    # Cached confirmation timeout, measured in milliseconds
    # Default to 8 hours timeout on credential reconfirmation
    timeout_in_milliseconds: int = 8 * 60 * 60

    def confirmation_still_active(self, key: str) -> bool:
        """Check whether account confirmation should used the previous cached result"""
        now = int(time())
        skip = (
            self.cache
            and (key in self.time_confirmed)
            and (now < (self.time_confirmed[key] + self.timeout_in_milliseconds))
        )
        self.time_confirmed[key] = now
        if skip:
            self.logger.debug(
                f"Using fresh cached account confirmation for '[green]{key}[/]'."
            )
        else:
            self.logger.debug(
                f"Ignoring stale cached account confirmation for '[green]{key}[/]'."
            )
        return skip

    def clear_confirm(self, key: str) -> None:
        """Clear the cached account confirmation result"""
        self.time_confirmed.pop(key)

    def clear_confirm_all(self) -> None:
        """Clear all cached account confirmation results"""
        self.time_confirmed.clear()
