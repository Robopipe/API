from __future__ import annotations

from enum import Enum

from ..base_model import BaseModel
from .label import Label
from .eval_threshold import EvalThreshold


# --- Limit Item ---


class EvalLimitItemParameter(str, Enum):
    POS_LEFT = "POS_LEFT"
    POS_RIGHT = "POS_RIGHT"
    POS_TOP = "POS_TOP"
    POS_BOTTOM = "POS_BOTTOM"
    POS_CENTER = "POS_CENTER"
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


# --- Limit ---


class EvalLimit(BaseModel):
    id: str
    name: str
    targetLabel: Label
    targetParentLabel: Label | None = None
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


class EvalTestCaseSeverity(str, Enum):
    ALERT = "ALERT"
    WARNING = "WARNING"


class EvalTestCase(BaseModel):
    id: str
    name: str
    type: EvalTestCaseType
    severity: EvalTestCaseSeverity
    limits: list[EvalLimit]
    logicNodes: list[EvalLogicNode] = []
    thresholds: list[EvalThreshold] = []
