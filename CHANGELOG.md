# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- **Developer Tools**: Added `AEGIS_UNMASK_CARDS` environment variable to optionally disable card masking (e.g., `****` default) during local testing and E2E validation.

## [0.2.0] - 2026-03-20
### Added
- **Open-Source Framework Support**: Added explicit MCP configuration and integration documentation for **OpenClaw**, **NemoClaw**, Claude Code, and OpenHands.
- **Multilingual Support**: Added Traditional Chinese (`README.zh-TW.md`) documentation alongside the English version.
- **LLM Provider Flexibility**: `LLMGuardrailEngine` now explicitly supports custom `base_url` and `model` parameters, enabling usage of **Ollama**, **vLLM**, OpenRouter, and any OpenAI-compatible API.
- **Dependency Handling**: Split dependencies into optional extras (`[llm]`, `[stripe]`, `[mcp]`, `[langchain]`, `[all]`) to drastically reduce `pip install aegis-pay` bloat for lightweight agents.
- **Dependency Injection**: `AegisClient` now supports injecting a custom `GuardrailEngine` during initialization.
- **Automated Testing**: Added a comprehensive suite of 20 `pytest` cases covering Pydantic models, budget enforcement, providers, and integration logic.

### Changed
- **MCP Configuration**: The MCP Server is now fully controlled via environment variables (`AEGIS_ALLOWED_CATEGORIES`, `AEGIS_MAX_PER_TX`, `AEGIS_MAX_DAILY`, `AEGIS_BLOCK_LOOPS`, `AEGIS_STRIPE_KEY`) instead of hardcoded policies.
- **State Management**: Migrated from unreliable in-memory lists to a robust SQLite (`aegis_state.db`) back-end (`AegisStateTracker`) with persistent connections.
- **Dashboard Data**: The Streamlit Vault Dashboard now reads directly from the live `aegis_state.db` SQLite database rather than mock data.

### Fixed
- **Daily Budget Enforcement**: Fixed an issue where the daily budget cap was not accurately tracking and blocking agent spend across sequential runs.
- **Stripe Provider Exceptions**: Refactored `StripeIssuingProvider` to gracefully catch and return explicit `stripe.StripeError` codes as formal rejection reasons instead of crashing the agent workflow.
- **Cardholder API**: Fixed the Stripe implementation by properly generating a `Cardholder` object before attempting to issue virtual cards.
- **Burn-after-use Security**: Implemented validation to ensure requested execution attempts correctly utilize issued `seal_id` mapping.

## [0.1.0] - Early 2026
### Added
- Initial release of Project Aegis (AgentPay).
- Basic `GuardrailPolicy`, `VirtualSeal`, and `PaymentIntent` Pydantic models.
- Minimal MVP Streamlit Dashboard (The Vault).
- Initial `MockStripeProvider` for testing workflows.
