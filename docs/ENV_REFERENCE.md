# Environment Variable Reference

All `POP_*` environment variables for pop-pay. Set in `~/.config/pop-pay/.env` or export in shell.

## Guardrail Policy

| Variable | Default | Description |
|----------|---------|-------------|
| `POP_ALLOWED_CATEGORIES` | `[]` | JSON array of allowed vendor keywords (e.g. `["amazon","shopify"]`) |
| `POP_MAX_PER_TX` | *(required)* | Max amount per transaction (USD) |
| `POP_MAX_DAILY` | *(required)* | Max total spend per day (USD) |
| `POP_BLOCK_LOOPS` | `true` | Block repeated identical purchase attempts |
| `POP_EXTRA_BLOCK_KEYWORDS` | `""` | Comma-separated extra keywords to block |
| `POP_GUARDRAIL_ENGINE` | `keyword` | `keyword` (local, zero API cost) or `llm` (semantic, needs API key) |
| `POP_REQUIRE_HUMAN_APPROVAL` | `false` | Require human confirmation before every payment |

## LLM Guardrail (opt-in)

| Variable | Default | Description |
|----------|---------|-------------|
| `POP_LLM_API_KEY` | `""` | API key for LLM guardrail (OpenAI-compatible) |
| `POP_LLM_BASE_URL` | *(none)* | Custom base URL (for Ollama, vLLM, OpenRouter) |
| `POP_LLM_MODEL` | `gpt-4o-mini` | Model name for LLM guardrail |

## Card Credentials (auto-loaded from vault)

| Variable | Default | Description |
|----------|---------|-------------|
| `POP_BYOC_NUMBER` | *(from vault)* | Card number (auto-set from encrypted vault) |
| `POP_BYOC_CVV` | *(from vault)* | CVV (auto-set from encrypted vault) |
| `POP_BYOC_EXP_MONTH` | *(from vault)* | Expiration month (auto-set from encrypted vault) |
| `POP_BYOC_EXP_YEAR` | *(from vault)* | Expiration year (auto-set from encrypted vault) |

## Billing Info

| Variable | Default | Description |
|----------|---------|-------------|
| `POP_BILLING_FIRST_NAME` | `""` | Billing first name |
| `POP_BILLING_LAST_NAME` | `""` | Billing last name |
| `POP_BILLING_STREET` | `""` | Street address |
| `POP_BILLING_CITY` | `""` | City |
| `POP_BILLING_STATE` | `""` | State (2-letter code auto-expands: `CA` → `California`) |
| `POP_BILLING_ZIP` | `""` | Zip / postal code |
| `POP_BILLING_COUNTRY` | `""` | Country |
| `POP_BILLING_EMAIL` | `""` | Email address |
| `POP_BILLING_PHONE` | `""` | Phone number (E.164 format) |
| `POP_BILLING_PHONE_COUNTRY_CODE` | `""` | Phone country dial code (e.g. `+1`) |

## Browser / CDP

| Variable | Default | Description |
|----------|---------|-------------|
| `POP_CDP_URL` | `http://localhost:9222` | Chrome DevTools Protocol endpoint |
| `POP_AUTO_INJECT` | `false` | Auto-inject card into checkout form after guardrail approval |
| `POP_BLACKOUT_MODE` | `after` | Screenshot protection: `before` (mask before injection), `after` (mask after, default), `off` (no masking) |
| `POP_ALLOWED_PAYMENT_PROCESSORS` | *(built-in list)* | Extra allowed domains for TOCTOU check |

## Webhooks / Approval

| Variable | Default | Description |
|----------|---------|-------------|
| `POP_WEBHOOK_URL` | *(disabled)* | POST payment notifications to this URL (Slack/Teams/PagerDuty) |
| `POP_APPROVAL_WEBHOOK` | *(disabled)* | POST approval requests to this URL; expects `{"approved": bool, "reason": "..."}` response (120s timeout) |

## Enterprise / Stripe

| Variable | Default | Description |
|----------|---------|-------------|
| `POP_STRIPE_KEY` | *(none)* | Stripe API key for virtual card issuing |

## x402 Protocol (experimental)

| Variable | Default | Description |
|----------|---------|-------------|
| `POP_X402_WALLET_KEY` | *(none)* | Crypto wallet key for x402 micropayments (stubbed) |
