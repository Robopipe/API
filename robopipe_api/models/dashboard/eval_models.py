from __future__ import annotations

from enum import Enum

from ..base_model import BaseModel
from .label import Label
from .eval_threshold import EvalThreshold


class EvalSeverity(str, Enum):
    ALERT = "ALERT"
    WARNING = "WARNING"


# --- Limit Item ---


class EvalLimitItemEdge(str, Enum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    TOP = "TOP"
    BOTTOM = "BOTTOM"
    CENTER = "CENTER"


class EvalLimitItemParameter(str, Enum):
    POSITION = "POSITION"
    AREA = "AREA"
    COUNT = "COUNT"


class EvalLimitItemOperator(str, Enum):
    AND = "AND"
    OR = "OR"


class EvalLimitItemQuantifierType(str, Enum):
    MIN = "MIN"
    MAX = "MAX"
    EXACT = "EXACT"


class EvalLimitItemQuantifierUnit(str, Enum):
    PCS = "PCS"
    PERCENT = "PERCENT"


class EvalLimitItem(BaseModel):
    id: str
    limitFrom: float | None = None
    limitTo: float | None = None
    parameter: EvalLimitItemParameter
    operator: EvalLimitItemOperator = EvalLimitItemOperator.AND
    quantifierType: EvalLimitItemQuantifierType = EvalLimitItemQuantifierType.EXACT
    quantifierUnit: EvalLimitItemQuantifierUnit = EvalLimitItemQuantifierUnit.PERCENT
    quantifierValue: int = 100
    targetEdge: EvalLimitItemEdge
    parentEdge: EvalLimitItemEdge


# --- Limit ---


class EvalLimit(BaseModel):
    id: str
    name: str
    targetLabel: Label
    targetParentLabel: Label | None = None
    severity: EvalSeverity | None = None
    enabled: bool = True
    limitItems: list[EvalLimitItem] = []


# --- Logic Nodes ---


class EvalLogicNodeType(str, Enum):
    GROUP = "GROUP"
    LIMIT = "LIMIT"
    OPERATOR = "OPERATOR"


class EvalLogicOperatorValue(str, Enum):
    AND = "AND"
    OR = "OR"
    NOT = "NOT"


class EvalLogicNode(BaseModel):
    id: str
    type: EvalLogicNodeType
    children: list[EvalLogicNode] | None = None
    operatorValue: EvalLogicOperatorValue | None = None


# --- Test Case ---


class EvalTestCaseType(str, Enum):
    CHECK = "CHECK"
    DEFECT = "DEFECT"


class EvalTestCase(BaseModel):
    id: str
    name: str
    type: EvalTestCaseType
    severity: EvalSeverity | None = None
    limits: list[EvalLimit]
    logicNodes: list[EvalLogicNode] = []
    thresholds: list[EvalThreshold] = []
    enabled: bool = True
