from check_environment import main, missing_configuration


def test_rejects_missing_configuration():
    assert missing_configuration({"LLM_PROVIDER": "openai"}) == [
        "DATABASE_URL",
        "OPENAI_API_KEY",
    ]


def test_provider_requires_only_its_own_key():
    assert (
        missing_configuration(
            {
                "LLM_PROVIDER": "anthropic",
                "DATABASE_URL": "synthetic",
                "ANTHROPIC_API_KEY": "synthetic",
            }
        )
        == []
    )


def test_rejects_unsupported_provider():
    assert missing_configuration({"LLM_PROVIDER": "unknown"}) == [
        "LLM_PROVIDER (must be openai or anthropic)"
    ]


def test_whitespace_is_not_a_credential():
    assert missing_configuration(
        {"LLM_PROVIDER": "openai", "DATABASE_URL": "synthetic", "OPENAI_API_KEY": "  "}
    ) == ["OPENAI_API_KEY"]


def test_output_does_not_reveal_values(monkeypatch, capsys):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("DATABASE_URL", "synthetic-private-database")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-private-key")
    assert main() == 0
    output = capsys.readouterr().out
    assert "synthetic-private" not in output
