from cleansolve_workflow.graph import run_mock_workflow


def test_workflow_auto_revises_before_human_review():
    state = run_mock_workflow(job_id="job_workflow")

    assert state["status"] == "APPROVED"
    assert state["revision_attempts"] == 1
    assert state["max_revision_attempts"] == 2
    assert state["review_items"] == []
    assert state["correction_plans"][0]["actions"][0]["type"] == "spec_patch"
