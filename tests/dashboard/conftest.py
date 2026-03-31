import pytest

from robopipe_api.models.dashboard.label import Label
from robopipe_api.models.dashboard.dashboard_config import (
    DashboardConfig,
    DashboardLineDirection,
    DashboardLineFlow,
)
from robopipe_api.models.dashboard.eval_models import (
    EvalLimit,
    EvalLimitItem,
    EvalLimitItemOperator,
    EvalLimitItemParameter,
    EvalLogicNode,
    EvalLogicNodeType,
    EvalLogicOperatorValue,
    EvalTestCase,
    EvalTestCaseType,
    EvalTestCaseSeverity,
)
from robopipe_api.models.detection.bbox_detection import BBoxDetection


# ---------------------------------------------------------------------------
# Labels — index in the list must match detection.label
# ---------------------------------------------------------------------------

LABEL_DEFECT = Label(
    id=1, name="defect", color="#ff0000",
    createdAt="", updatedAt="", deletedAt=None,
)
LABEL_PART = Label(
    id=2, name="part", color="#00ff00",
    createdAt="", updatedAt="", deletedAt=None,
)
LABEL_CONTAINER = Label(
    id=3, name="container", color="#0000ff",
    createdAt="", updatedAt="", deletedAt=None,
)
# Index 0 → LABEL_DEFECT, index 1 → LABEL_PART, index 2 → LABEL_CONTAINER
LABELS = [LABEL_DEFECT, LABEL_PART, LABEL_CONTAINER]


# ---------------------------------------------------------------------------
# Detection factories
# ---------------------------------------------------------------------------

def make_detection(
    label: int = 0,
    confidence: float = 0.9,
    coords: tuple[float, float, float, float] = (0.3, 0.3, 0.5, 0.5),
) -> BBoxDetection:
    return BBoxDetection(label=label, confidence=confidence, coords=coords)


# ---------------------------------------------------------------------------
# Model factories
# ---------------------------------------------------------------------------

def make_limit_item(
    parameter: EvalLimitItemParameter = EvalLimitItemParameter.COUNT,
    limit_from: float | None = None,
    limit_to: float | None = None,
    operator: EvalLimitItemOperator = EvalLimitItemOperator.AND,
    item_id: str = "li-1",
) -> EvalLimitItem:
    return EvalLimitItem(
        id=item_id,
        limitFrom=limit_from,
        limitTo=limit_to,
        parameter=parameter,
        operator=operator,
    )


def make_limit(
    limit_id: str = "lim-1",
    target_label: Label = LABEL_DEFECT,
    target_parent_label: Label | None = None,
    limit_items: list[EvalLimitItem] | None = None,
) -> EvalLimit:
    return EvalLimit(
        id=limit_id,
        name=f"Limit {limit_id}",
        targetLabel=target_label,
        targetParentLabel=target_parent_label,
        limitItems=limit_items or [],
    )


def make_test_case(
    tc_id: str = "tc-1",
    tc_type: EvalTestCaseType = EvalTestCaseType.DEFECT,
    severity: EvalTestCaseSeverity = EvalTestCaseSeverity.ALERT,
    limits: list[EvalLimit] | None = None,
    logic_nodes: list[EvalLogicNode] | None = None,
) -> EvalTestCase:
    return EvalTestCase(
        id=tc_id,
        name=f"TestCase {tc_id}",
        type=tc_type,
        severity=severity,
        limits=limits or [],
        logicNodes=logic_nodes or [],
    )


def make_config(
    test_cases: list[EvalTestCase] | None = None,
    labels: list[Label] | None = None,
    line_direction: DashboardLineDirection = DashboardLineDirection.HORIZONTAL,
    line_position: float = 0.5,
    line_flow: DashboardLineFlow = DashboardLineFlow.POSITIVE,
    config_id: int = 1,
) -> DashboardConfig:
    return DashboardConfig(
        id=config_id,
        name="Test config",
        lineDirection=line_direction,
        linePosition=line_position,
        lineFlow=line_flow,
        testCases=test_cases or [],
        labels=labels if labels is not None else LABELS,
    )


# ---------------------------------------------------------------------------
# Logic node helpers
# ---------------------------------------------------------------------------

def limit_node(limit_id: str) -> EvalLogicNode:
    return EvalLogicNode(id=limit_id, type=EvalLogicNodeType.LIMIT)


def operator_node(op: EvalLogicOperatorValue) -> EvalLogicNode:
    return EvalLogicNode(
        id=f"op-{op.value.lower()}",
        type=EvalLogicNodeType.OPERATOR,
        operatorValue=op,
    )


def group_node(children: list[EvalLogicNode]) -> EvalLogicNode:
    return EvalLogicNode(
        id="grp", type=EvalLogicNodeType.GROUP, children=children,
    )
