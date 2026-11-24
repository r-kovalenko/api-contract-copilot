# Typed model providers — #37

`ModelProvider.generate(GenerationRequest)` is an async boundary returning a validated `StructuredAnswer` of cited claims and explicit evidence gaps. It is preparation for the impact-analysis API (#38), not an implemented report workflow. No route or tool currently calls a model. Deterministic contract compatibility remains owned by oasdiff; source lookup stays in application tools.

## Offline checkpoint

```powershell
python backend/demo_model_provider.py
```

Or rebuild the backend and run `docker compose exec backend python demo_model_provider.py`. The demo always uses `FakeProvider`, irrespective of environment variables, and never connects to a provider. Its deterministic response describes the supplied evidence count and explicitly states that analysis was not performed. Ordinary CI uses this fake and HTTPX MockTransport only.

## Optional live construction

`provider_from_environment()` defaults to `fake`. Live construction requires all of:

- `LLM_PROVIDER=openai`
- `LLM_ENABLE_LIVE=1`
- `OPENAI_MODEL`: an explicitly selected OpenAI model supporting Responses structured outputs
- `OPENAI_API_KEY`: a server-side secret

Missing/unsupported configuration fails with safe codes. Python does not load `.env` automatically, and Compose does not currently forward provider secrets. Export configuration only in the backend process that intentionally calls `await provider.generate(request)`; never place credentials in frontend variables, source files or command arguments. See [credential handling](secrets.md). No live call was made for this checkpoint; account/model availability and live schema compatibility require a separately opted-in smoke test.

The adapter uses the existing HTTPX dependency, the fixed HTTPS Responses endpoint, `store: false`, strict JSON-schema output, no tools, no redirects and no inherited proxy settings. The model and credentials are application-owned configuration, never user/tool payload fields. Evidence is serialized as untrusted input separately from fixed instructions. Prompt instructions alone do not guarantee semantic correctness: citation membership is checked, but claim support must still be validated by the future report flow.

## Bounds and failures

Requests accept a question up to 1,000 characters and up to 20 uniquely identified sources, each at most 2,000 characters. Serialized request data is capped at 12,000 UTF-8 bytes; the complete outgoing JSON (including schema/instructions) is capped at 16,000 bytes. This bounds input size conservatively rather than estimating exact model tokens. Unicode escaping can make the wire cap stricter. Each attempt requests at most 1,024 output tokens, for a maximum of 2,048 requested output tokens across two attempts. These are per-call limits, not an account-wide spend quota.

There are at most two calls in flight per process. Each attempt has an eight-second wall deadline; the entire call including retry delay has a twenty-second deadline. Only transport failures, 429 and 5xx responses retry once after 250 ms. A retry may incur duplicate provider cost if the first response was lost. Cancellation closes the client and releases the slot but cannot guarantee remote generation stops.

Response bodies are capped at 64 KiB; compressed responses are rejected. Refusals, incomplete generation, invalid JSON/schema, unknown citations, unauthorized responses and other HTTP errors fail explicitly without partial results or repair retries. No response/error body, prompt, or credential is logged by the adapter. Callers must not log input models, transport objects, raw exceptions with locals, or configured secrets.

Safe error codes include `missing_credentials`, `invalid_model`, `unsupported_provider`, `live_disabled`, `input_budget`, `output_budget`, `busy`, `timeout`, `provider_unavailable`, `retry_exhausted`, `authentication_failed`, `request_rejected`, `invalid_output`, `incomplete_output`, `refused`, and `unknown_citation`. Empty claims require at least one evidence gap. Unknown citations are rejected even when the JSON schema is valid. Returned claim text remains untrusted and must be escaped in a future UI.

## References and validation

Protocol follows the official [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create) and [structured outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs). Run `python -m pytest backend/tests/test_model_provider.py` for offline request-shape, output validation, retry/time/input/output budget, configuration, cancellation and log-sanitization tests. No SDK/dependency updates are needed.
