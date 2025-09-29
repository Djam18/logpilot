"""Plugin registry — discover, validate, and expose plugins.

Discovery order:
  1. Built-in parsers/aggregators/outputs registered at startup.
  2. Entry-points under the "logpilot.plugins" group (third-party packages).
  3. Plugins explicitly registered at runtime via PluginRegistry.register().
"""
from __future__ import annotations

import importlib.metadata
import logging
from typing import Any

from .base import AggregatorPlugin, OutputPlugin, ParserPlugin

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Central registry for all logpilot plugin types.

    Usage::

        registry = PluginRegistry()
        registry.discover()  # loads entry-point plugins

        parser = registry.get_parser("nginx")
        if parser is None:
            raise ValueError("nginx parser not installed")
    """

    def __init__(self) -> None:
        self._parsers: dict[str, ParserPlugin] = {}
        self._aggregators: dict[str, AggregatorPlugin] = {}
        self._outputs: dict[str, OutputPlugin] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_parser(self, plugin: ParserPlugin) -> None:
        if not isinstance(plugin, ParserPlugin):
            raise TypeError(f"{plugin!r} does not implement ParserPlugin")
        self._parsers[plugin.name] = plugin
        logger.debug("Registered parser plugin: %s", plugin.name)

    def register_aggregator(self, plugin: AggregatorPlugin) -> None:
        if not isinstance(plugin, AggregatorPlugin):
            raise TypeError(f"{plugin!r} does not implement AggregatorPlugin")
        self._aggregators[plugin.name] = plugin
        logger.debug("Registered aggregator plugin: %s", plugin.name)

    def register_output(self, plugin: OutputPlugin) -> None:
        if not isinstance(plugin, OutputPlugin):
            raise TypeError(f"{plugin!r} does not implement OutputPlugin")
        self._outputs[plugin.name] = plugin
        logger.debug("Registered output plugin: %s", plugin.name)

    # ------------------------------------------------------------------
    # Discovery via entry-points
    # ------------------------------------------------------------------

    def discover(self) -> int:
        """Load all plugins from the 'logpilot.plugins' entry-point group.

        Returns the number of plugins successfully loaded.
        """
        loaded = 0
        try:
            eps = importlib.metadata.entry_points(group="logpilot.plugins")
        except Exception as exc:
            logger.warning("Entry-point discovery failed: %s", exc)
            return 0

        for ep in eps:
            try:
                obj = ep.load()
                instance = obj() if callable(obj) else obj
                self._auto_register(instance, ep.name)
                loaded += 1
            except Exception as exc:
                logger.warning("Failed to load plugin %r: %s", ep.name, exc)

        return loaded

    def _auto_register(self, instance: Any, ep_name: str) -> None:
        """Register a plugin instance under the correct category."""
        if isinstance(instance, ParserPlugin):
            self.register_parser(instance)
        elif isinstance(instance, AggregatorPlugin):
            self.register_aggregator(instance)
        elif isinstance(instance, OutputPlugin):
            self.register_output(instance)
        else:
            logger.warning(
                "Plugin %r does not implement any known Protocol — skipped", ep_name
            )

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_parser(self, name: str) -> ParserPlugin | None:
        return self._parsers.get(name)

    def get_aggregator(self, name: str) -> AggregatorPlugin | None:
        return self._aggregators.get(name)

    def get_output(self, name: str) -> OutputPlugin | None:
        return self._outputs.get(name)

    def list_parsers(self) -> list[str]:
        return sorted(self._parsers)

    def list_aggregators(self) -> list[str]:
        return sorted(self._aggregators)

    def list_outputs(self) -> list[str]:
        return sorted(self._outputs)


# Module-level singleton — shared across the application
default_registry = PluginRegistry()
