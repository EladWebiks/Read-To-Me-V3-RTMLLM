---
name: add-llm-provider
description: Add a new LLM provider adapter behind the RTM v3 LLMProvider abstraction (e.g. OpenAI, Anthropic, OpenRouter, a local model) with capability metadata, cost tracking, and a contract test. Use when integrating a new model vendor or local runtime.
---

# Add an LLM provider

Keeps RTM v3 provider-agnostic: business logic depends only on the `LLMProvider` interface. See rule `40-llm-provider`.

## Steps

1. **Create the adapter** in `modules/llm/providers/<name>_provider.py` implementing the `LLMProvider` protocol:
   `generate_text`, `stream_text`, `generate_structured_output`, `call_tools`, optional `create_embeddings`.
   - You MAY use litellm or the vendor SDK **inside** the adapter. Nothing outside `modules/llm` may import it.
   - Normalize requests/responses to RTM's internal types — providers differ on tool schema, token accounting, streaming, and system-prompt semantics.
2. **Declare capabilities & features** for each model: which of `FAST_CHAT`, `TOOL_CALLING`, `STRUCTURED_EXTRACTION`, `LONG_CONTEXT_SUMMARIZATION`, `RERANKING`, `EMBEDDING`, `LOCAL_PRIVATE_INFERENCE`; context window; `supports_tools/structured/streaming`. Store as `model_configuration` data, not hardcoded in logic.
3. **Config & secrets:** read API keys via `pydantic-settings` (`app/core/config`); keep keys isolated to `modules/llm`. Never log keys.
4. **Reliability:** honor the router's retry/timeout/circuit-breaker; implement graceful errors so fallback to the next candidate works.
5. **Cost/telemetry:** emit `provider, model, tokens_in, tokens_out, cost, latency_ms` for `llm_execution`/`cost_record` on every call.
6. **Register** the provider + its models so the router can select them.
7. **Contract test** (`tests/llm/test_<name>_provider.py`): run the shared provider contract suite (mock the network) asserting each protocol method returns normalized types, structured output validates, tool-calls parse, and feature detection is honored.

## Checklist
- [ ] Implements the full `LLMProvider` protocol with normalized types
- [ ] Capabilities + context window + feature flags declared as data
- [ ] Keys via settings, isolated to `modules/llm`, never logged
- [ ] Cost/token/latency recorded; works with router fallback
- [ ] Passes the shared provider contract test (no live network)
