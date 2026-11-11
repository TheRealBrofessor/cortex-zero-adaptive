"""Cortex Zero Adaptive — Hermes plugin for adaptive browser automation."""

from .tools import (
    configure,
    cz_adaptive_config,
    cz_adaptive_demo,
    cz_adaptive_run,
    cz_adaptive_status,
)


def register(ctx) -> None:
    """Register native Hermes tools and load only user-configured settings."""
    configure(ctx)
    ctx.register_tool(
        name="cz_adaptive_run",
        toolset="cortex_zero_adaptive",
        description="Run Cortex Zero Adaptive browser automation within configured domain and operation allowlists.",
        schema={
            "name": "cz_adaptive_run",
            "description": "Run an adaptive browser automation session.",
            "parameters": {
                "type": "object",
                "properties": {
                    "objective": {"type": "string", "description": "High-level objective."},
                    "initial_plan": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["objective"],
                "additionalProperties": False,
            },
        },
        handler=cz_adaptive_run,
    )
    ctx.register_tool(
        name="cz_adaptive_status",
        toolset="cortex_zero_adaptive",
        description="Return the current Cortex Zero Adaptive session report.",
        schema={
            "name": "cz_adaptive_status",
            "description": "Get the current or last adaptive session status.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        handler=cz_adaptive_status,
    )
    ctx.register_tool(
        name="cz_adaptive_demo",
        toolset="cortex_zero_adaptive",
        description="Run a deterministic mock demonstration of adaptive failure recovery.",
        schema={
            "name": "cz_adaptive_demo",
            "description": "Run one of the built-in mock recovery demonstrations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "demo": {
                        "type": "string",
                        "enum": ["navigation_failure", "element_not_found", "policy_blocked"],
                    }
                },
                "additionalProperties": False,
            },
        },
        handler=cz_adaptive_demo,
    )
    ctx.register_tool(
        name="cz_adaptive_config",
        toolset="cortex_zero_adaptive",
        description="Show the effective Cortex Zero Adaptive configuration.",
        schema={
            "name": "cz_adaptive_config",
            "description": "Show the effective user-configured adaptive settings.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        handler=cz_adaptive_config,
    )


__all__ = ["register"]
