# Contributing to Project Aegis (AgentPay)

Thank you for your interest in contributing to Project Aegis! This project aims to provide a secure and manageable payment layer for Agentic AI, ensuring that agents can perform financial transactions within human-defined boundaries.

## Project Architecture

Aegis is built on three core pillars that work together to provide a secure "Human-in-the-Loop" payment experience:

### 🛡️ The Vault (Visualization & Management)
The Vault is our local dashboard and state management system.
- **Console:** A Streamlit-powered dashboard (`dashboard/app.py`) for real-time monitoring of agent spending and issued seals.
- **State:** A local SQLite database (`aegis_state.db`) that tracks every transaction, audit log, and budget status.

### 📜 The Seal (Virtual Transaction Unit)
The Seal is the fundamental unit of authorization in Aegis.
- When an agent requests a payment, Aegis issues a `VirtualSeal`.
- A `VirtualSeal` contains the virtual card details (pan, cvv, expiry) or a rejection reason.
- Seals are tracked in the Vault to prevent reuse and ensure transparency.

### 🧠 Semantic Guardrails (Policy & Enforcement)
Guardrails are the "brains" that decide whether a payment should be approved or rejected based on the agent's context.
- **GuardrailEngine:** A fast, keyword-based interceptor that blocks common failure patterns (e.g., loops, hallucinations).
- **LLMGuardrailEngine:** A deep semantic analyzer (powered by GPT-4o-mini) that evaluates the agent's reasoning against the requested `GuardrailPolicy`.
- **GuardrailPolicy:** A set of rules (e.g., `max_amount`, `allowed_vendors`, `purpose_description`) defined by the human user.

### 🌐 Browser Injector (Secure Fulfillment)
For agent frameworks evaluating DOMs, Aegis securely fulfills authorized payments without leaking the card directly to the LLM.
- **AegisBrowserInjector**: Connects strictly out-of-band via CDP (`Chrome DevTools Protocol`). Traverses cross-origin iframes (i.e. Stripe Elements) and auto-populates `<input>` elements safely.

---

## Local Development Setup

We use `uv` for lightning-fast Python package management.

### Prerequisites
- Install **uv**:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

### Setup
1. Clone the repository.
2. Run `uv sync` to create a virtual environment and install all dependencies (including dev tools).
   ```bash
   uv sync
   ```

### Running Tests
We use `pytest` for our test suite. To run all tests:
```bash
pytest
```

---

## 🚀 Call for Contributions

We are actively looking for community help to expand the Aegis ecosystem. Specifically, we are looking for:

### 1. New Payment Providers
Help us expand the range of virtual cards Aegis can issue by implementing new providers in `aegis/providers/`:
- **CoinbaseWalletProvider:** Enable agents to spend via USDC or other crypto-backed virtual cards.
- **PrivacyComProvider:** Integration with Privacy.com for consumer-grade virtual card issuance.

### 2. Dashboard Enhancements
The Vault needs more robust management features:
- **Real Budget-writeback logic:** Currently, the Max Daily Budget slider in the Dashboard is temporary. We need logic to save and persist these limits to the `aegis_state.db` and enforce them within the `AegisClient`.

### 3. Guardrail Improvements
- New semantic analysis patterns for the `LLMGuardrailEngine`.
- Integration with other LLM providers (Anthropic, local models via Ollama).

If you have an idea for a feature or a bug fix, please open an issue or submit a Pull Request!
