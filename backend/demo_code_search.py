"""Run a synthetic consumer-code search without a server, database, or LLM."""

from pathlib import Path
from tempfile import TemporaryDirectory

from app.code_search import RepositorySearch
from app.tool_registry import ToolRegistry


def main():
    with TemporaryDirectory(prefix="copilot-search-demo-") as temporary:
        root = Path(temporary).resolve()
        (root / "customer_client.py").write_text(
            'def customer_label(customer):\n    return customer["full_name"]\n', encoding="utf-8"
        )
        registry = ToolRegistry(RepositorySearch({"consumer-demo": root}))
        result = registry.invoke(
            {
                "operation": "search_code",
                "repository": "consumer-demo",
                "query": "full_name",
            }
        )
        print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
