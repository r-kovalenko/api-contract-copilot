import pytest
from pydantic import ValidationError

from app.migration_schemas import PlanDraft


@pytest.mark.parametrize(
    "steps",
    [
        [],
        [{"action": "create_issue", "source_ids": ["x"]}],
        [{"action": "review_change", "source_ids": []}],
        [{"action": "review_change", "source_ids": ["x"], "command": "run"}],
    ],
)
def test_plan_draft_rejects_invalid_steps(steps):
    with pytest.raises(ValidationError):
        PlanDraft(steps=steps)
