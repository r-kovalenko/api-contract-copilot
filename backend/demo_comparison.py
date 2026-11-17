"""Print deterministic comparison evidence for the repository's synthetic demo contracts."""

from pathlib import Path

from app.comparison import compare_contracts
from app.contract_validation import parse_contract

if __name__ == "__main__":
    examples = Path(__file__).resolve().parents[1] / "docs" / "examples"
    baseline = parse_contract((examples / "customer-v1.json").read_bytes(), "application/json")
    candidate = parse_contract((examples / "customer-v2.yaml").read_bytes(), "application/yaml")
    print(compare_contracts(baseline, candidate).model_dump_json(indent=2))
