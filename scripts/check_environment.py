"""Validate configured names without logging secret values or contacting providers."""

import os
from collections.abc import Mapping


def missing_configuration(environment: Mapping[str, str]) -> list[str]:
    provider = environment.get("LLM_PROVIDER", "").strip()
    provider_keys = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
    if provider not in provider_keys:
        return ["LLM_PROVIDER (must be openai or anthropic)"]
    required = ["DATABASE_URL", provider_keys[provider]]
    return [name for name in required if not environment.get(name, "").strip()]


def main() -> int:
    missing = missing_configuration(os.environ)
    if missing:
        print("Missing or invalid configuration names: " + ", ".join(missing))
        return 1
    print(
        "Required configuration is present; values and connectivity were not inspected."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
