from copy import deepcopy
from typing import Any, Dict, List


ALLOWED_GRAPH_NODE_KINDS = {"artifact", "capability", "approval", "bounded_model_call"}


def workflow_dsl_to_graph(dsl_document: Dict[str, Any]) -> Dict[str, Any]:
    steps = dsl_document.get("steps") if isinstance(dsl_document.get("steps"), list) else []
    nodes = []
    edges = []
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        node_id = str(step.get("key") or f"step_{index + 1}")
        kind = "bounded_model_call" if step.get("bounded_model_call") is True else str(step.get("type") or "artifact")
        nodes.append(
            {
                "id": node_id,
                "kind": kind,
                "title": str(step.get("title") or node_id),
                "position": {"x": index * 280, "y": 40 if index % 2 == 0 else 150},
                "config": deepcopy(step),
            }
        )
        if index:
            previous = steps[index - 1]
            previous_id = str(previous.get("key") or f"step_{index}") if isinstance(previous, dict) else f"step_{index}"
            edges.append({"id": f"{previous_id}:{node_id}", "source": previous_id, "target": node_id})
    return {
        "schema": "localos_agent_workflow_graph_v1",
        "dsl_schema": str(dsl_document.get("schema") or ""),
        "nodes": nodes,
        "edges": edges,
    }


def validate_workflow_graph(graph: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[Dict[str, str]] = []
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
    node_ids = []
    for node in nodes:
        if not isinstance(node, dict):
            errors.append({"code": "invalid_node", "message": "Each graph node must be an object"})
            continue
        node_id = str(node.get("id") or "").strip()
        kind = str(node.get("kind") or "").strip()
        if not node_id:
            errors.append({"code": "missing_node_id", "message": "Each graph node needs an id"})
        elif node_id in node_ids:
            errors.append({"code": "duplicate_node_id", "node_id": node_id, "message": "Node ids must be unique"})
        else:
            node_ids.append(node_id)
        if kind not in ALLOWED_GRAPH_NODE_KINDS:
            errors.append({"code": "unknown_node_kind", "node_id": node_id, "message": "Node kind is not registered"})
        if not isinstance(node.get("config"), dict):
            errors.append({"code": "missing_node_config", "node_id": node_id, "message": "Node config is required"})
    incoming = {node_id: 0 for node_id in node_ids}
    outgoing: Dict[str, List[str]] = {node_id: [] for node_id in node_ids}
    for edge in edges:
        if not isinstance(edge, dict):
            errors.append({"code": "invalid_edge", "message": "Each graph edge must be an object"})
            continue
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        if source not in outgoing or target not in incoming:
            errors.append({"code": "dangling_edge", "message": "Every edge must connect registered nodes"})
            continue
        outgoing[source].append(target)
        incoming[target] += 1
    for node_id in node_ids:
        if incoming[node_id] > 1 or len(outgoing[node_id]) > 1:
            errors.append({"code": "branching_not_supported", "node_id": node_id, "message": "This editor supports a single safe path"})
    if node_ids:
        starts = [node_id for node_id in node_ids if incoming[node_id] == 0]
        ends = [node_id for node_id in node_ids if not outgoing[node_id]]
        if len(starts) != 1 or len(ends) != 1:
            errors.append({"code": "invalid_topology", "message": "Graph needs one start and one result path"})
        elif not errors:
            visited = []
            current = starts[0]
            while current and current not in visited:
                visited.append(current)
                current = outgoing[current][0] if outgoing[current] else ""
            if current or len(visited) != len(node_ids):
                errors.append({"code": "cycle_or_unreachable_node", "message": "All nodes must be reachable without a cycle"})
    return {"valid": not errors, "errors": errors}


def workflow_graph_to_steps(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    validation = validate_workflow_graph(graph)
    if not validation["valid"]:
        raise ValueError("Invalid workflow graph")
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
    nodes_by_id = {str(node["id"]): node for node in nodes}
    incoming = {node_id: 0 for node_id in nodes_by_id}
    outgoing = {node_id: "" for node_id in nodes_by_id}
    for edge in edges:
        source = str(edge["source"])
        target = str(edge["target"])
        outgoing[source] = target
        incoming[target] += 1
    current = next((node_id for node_id, count in incoming.items() if count == 0), "")
    result = []
    while current:
        node = nodes_by_id[current]
        config = deepcopy(node["config"])
        config["key"] = current
        result.append(config)
        current = outgoing[current]
    return result


def validate_workflow_step_approval_order(steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    errors = []
    approval_positions = {
        str(step.get("approval_type") or ""): index
        for index, step in enumerate(steps)
        if str(step.get("type") or "") == "approval" and str(step.get("approval_type") or "").strip()
    }
    for index, step in enumerate(steps):
        required_approval_type = str(step.get("required_approval_type") or "").strip()
        if step.get("requires_approval") is not True or not required_approval_type:
            continue
        if required_approval_type not in approval_positions or approval_positions[required_approval_type] >= index:
            errors.append(
                {
                    "code": "approval_order_invalid",
                    "step_key": str(step.get("key") or ""),
                    "message": "Approval must be placed before the protected action",
                }
            )
    return {"valid": not errors, "errors": errors}
