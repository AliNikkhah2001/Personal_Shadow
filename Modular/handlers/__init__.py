"""Action handler registry for SystemBridge."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from system_bridge import SystemBridge


class ActionHandler:
    """Base class for action handlers that process specific domain actions."""

    actions: ClassVar[dict[str, str]] = {}

    def __init__(self, bridge: SystemBridge) -> None:
        self.bridge = bridge

    def handle(self, action: str, req: dict[str, Any]) -> str | None:
        """Handle an action. Returns JSON string or None if not handled."""
        method_name = self.actions.get(action)
        if method_name and hasattr(self, method_name):
            return getattr(self, method_name)(req)
        return None
