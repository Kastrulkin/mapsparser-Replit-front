from copy import deepcopy

import pytest

from tests.test_agent_template_catalog_contract import BETA_TEMPLATE_KEYS


@pytest.mark.parametrize("template_key", BETA_TEMPLATE_KEYS)
def test_template_dsl_graph_roundtrip_preserves_every_runtime_step(template_key):
    from services.agent_template_catalog import get_agent_template
    from services.agent_workflow_graph import validate_workflow_graph, workflow_dsl_to_graph, workflow_graph_to_steps

    workflow = get_agent_template(template_key)["workflow_dsl"]
    graph = workflow_dsl_to_graph(workflow)

    assert validate_workflow_graph(graph)["valid"] is True
    assert workflow_graph_to_steps(graph) == workflow["steps"]
    assert len(graph["nodes"]) == len(workflow["steps"])


def test_graph_rejects_empty_unknown_dangling_branching_and_cycles():
    from services.agent_template_catalog import get_agent_template
    from services.agent_workflow_graph import validate_workflow_graph, workflow_dsl_to_graph

    workflow = get_agent_template("daily_owner_digest")["workflow_dsl"]
    base = workflow_dsl_to_graph(workflow)
    cases = []

    cases.append({"schema": base["schema"], "nodes": [], "edges": []})
    unknown = deepcopy(base)
    unknown["nodes"][0]["kind"] = "shell"
    cases.append(unknown)
    dangling = deepcopy(base)
    dangling["edges"][0]["target"] = "missing"
    cases.append(dangling)
    branching = deepcopy(base)
    branching["edges"].append({"id": "branch", "source": branching["nodes"][0]["id"], "target": branching["nodes"][-1]["id"]})
    cases.append(branching)
    cyclic = deepcopy(base)
    cyclic["edges"].append({"id": "cycle", "source": cyclic["nodes"][-1]["id"], "target": cyclic["nodes"][0]["id"]})
    cases.append(cyclic)

    for graph in cases:
        assert validate_workflow_graph(graph)["valid"] is False


def test_graph_coordinates_never_change_runtime_semantics():
    from services.agent_template_catalog import get_agent_template
    from services.agent_workflow_graph import workflow_dsl_to_graph, workflow_graph_to_steps

    workflow = get_agent_template("negative_review_reply")["workflow_dsl"]
    graph = workflow_dsl_to_graph(workflow)
    for index, node in enumerate(graph["nodes"]):
        node["position"] = {"x": index * -913, "y": index * 777}

    assert workflow_graph_to_steps(graph) == workflow["steps"]
