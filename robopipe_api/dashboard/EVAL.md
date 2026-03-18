# Dashboard Evaluation System

## Overview

The evaluation system determines whether detections from NN inference trigger
alerts or warnings. It processes detections that cross a configurable line and
evaluates them against a tree of test cases, limits, and logic nodes.

## Architecture

```
DashboardConfig
├── lineDirection / linePosition / lineFlow   ← line crossing filter
├── labels[]                                  ← maps detection.label index → Label
└── testCases[]
    ├── type (CHECK / DEFECT)
    ├── severity (ALERT / WARNING)
    ├── limits[]
    │   ├── targetLabel / targetParentLabel
    │   └── limitItems[]
    │       ├── parameter (POS_LEFT / COUNT / AREA / ...)
    │       ├── limitFrom / limitTo
    │       └── operator (AND / OR)          ← between consecutive items
    └── logicNodes[]                          ← combines limits (tree)
        ├── LIMIT  { id }                    ← references a limit by id
        ├── OPERATOR { AND / OR / NOT }
        └── GROUP  { children[] }            ← nested sub-expression
```

## Evaluation flow

```
Raw detections
    │
    ▼
LineCrossingTracker.find_crossed_detections()
    │  Filters to detections that have crossed the line.
    │  Returns early (None) if no NEW crossings this frame.
    ▼
For each TestCase:
    │
    ▼
LogicTreeEvaluator.evaluate()
    │  If logicNodes is empty → AND all limits (default).
    │  Otherwise, walks the node tree (infix, left-to-right).
    ▼
LimitEvaluator.evaluate()
    │  Resolves target detections by label (+ optional parent filter).
    │  Evaluates each LimitItem and combines with AND/OR operators.
    ▼
LimitItemEvaluator.evaluate()
    │  Computes metric based on parameter:
    │    COUNT  → len(targets)
    │    AREA   → sum of bbox areas as % (of parent or frame)
    │    POS_*  → position % for each detection within reference bbox
    │  Checks value against [limitFrom, limitTo].
    ▼
TestCaseEvaluator.is_violated()
    CHECK  → violated when combined result is False  (NOT of result)
    DEFECT → violated when combined result is True   (result directly)
```

## Line crossing

The `LineCrossingTracker` tracks detection movement across a line configured by:

- **lineDirection**: `HORIZONTAL` (line is a horizontal bar) or `VERTICAL`
- **linePosition**: 0.0–1.0 normalized coordinate
- **lineFlow**: direction of "past"
  - `POSITIVE`: past = coord ≥ linePosition (top→bottom / left→right)
  - `NEGATIVE`: past = coord ≤ linePosition (bottom→top / right→left)

Detections are matched between frames using nearest-neighbour distance per label.
A detection is "crossed" when it transitions from before the line to past it.
Once crossed, it stays crossed as long as it's visible.

The evaluator only runs test cases when at least one NEW crossing occurs in the
current frame. Otherwise it returns `None` (no `dashboard_detections` in the WS
message), which tells the frontend that nothing changed.

## CHECK vs DEFECT

| Type   | Meaning                         | Violated when        |
|--------|---------------------------------|----------------------|
| CHECK  | Expected condition must hold    | Result is **False**  |
| DEFECT | Defect condition must not occur | Result is **True**   |

CHECK acts as a NOT operator on the logic tree result.

## Logic nodes

Logic nodes combine limit results into a single boolean. They form an infix
expression evaluated **left-to-right** with no implicit precedence.

| Node type | Behavior                                       |
|-----------|------------------------------------------------|
| LIMIT     | Evaluates the limit matching `node.id`         |
| OPERATOR  | AND / OR (binary), NOT (unary prefix)          |
| GROUP     | Evaluates `children` as a sub-expression       |

Use GROUPs to control precedence. Example:

```
A OR (B AND C)  →  [LIMIT(A), OP(OR), GROUP([LIMIT(B), OP(AND), LIMIT(C)])]
```

When `logicNodes` is empty (default), all limits are AND-ed together.

## Limit item operators

Within a single limit, limit items are combined with their `operator` field,
which specifies the operator **after** the item (between item[i] and item[i+1]).
The last item's operator is unused.

```
items: [A(AND), B(OR), C]  →  A AND B OR C   (left-to-right)
```

## Positional evaluation

Positional parameters (`POS_LEFT`, `POS_RIGHT`, `POS_TOP`, `POS_BOTTOM`,
`POS_CENTER`) compute a detection's center position as a percentage within a
reference bounding box:

- If `targetParentLabel` is set: reference = containing parent bbox
- Otherwise: reference = full frame `(0, 0, 1, 1)`

The implicit quantifier is **ALL**: all target detections must satisfy the
positional range for the limit item to evaluate to `True`. Future versions will
add explicit quantifiers per limit.

When there are zero target detections, positional items evaluate to `False`.

## COUNT and AREA

- **COUNT**: absolute count of target detections. Checked directly against
  `[limitFrom, limitTo]`.
- **AREA**: total area of target bounding boxes as a percentage:
  - With parent label: `(target_area / parent_area) * 100`
  - Without parent: `target_area * 100` (percentage of full frame)

## Output format

The `handle_detections()` function returns the detection payload enriched with a
`dashboard_detections` key:

```json
{
  "detections": [...],
  "dashboard_detections": [
    { "test_case_id": "uuid-string", "type": "alert" },
    { "test_case_id": "uuid-string", "type": "warning" }
  ]
}
```

`dashboard_detections` is `null` when no new line crossings occurred, and an
empty list is normalized to `null`.

## Running tests

```bash
python3 -m pytest tests/dashboard/ -v
```
