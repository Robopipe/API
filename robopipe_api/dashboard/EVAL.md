# Dashboard Evaluation System

## Overview

The evaluation system determines whether detections from NN inference trigger
alerts or warnings. It samples detections that dwell inside a configurable
rectangular zone and evaluates them against a tree of test cases, limits, and
logic nodes. Each tracked object contributes to the dashboard metrics exactly
once — the per-frame verdicts are accumulated while the object is in the zone
and reduced to a single verdict when it leaves.

## Architecture

```
DashboardConfig
├── zoneDirection / zoneCenter / zoneThickness   ← evaluation zone
├── optimistic                                    ← per-tracker reducer
├── labels[]                                      ← maps detection.label index → Label
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
ZoneTracker.find_in_zone_detections()
    │  Kalman tracking + debouncing. Emits:
    │    in_zone            — currently dwelling detections
    │    just_entered       — trackers that entered this frame (→ counters)
    │    exited_tracker_ids — trackers that left (→ commit verdict)
    ▼
For each TestCase (per frame, using in_zone as the evaluated set):
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
    ▼
Per-tracker sample accumulator (pass/fail)
    │  One sample per firing test case per frame, attributed to every
    │  tracker currently in the zone.
    ▼
On zone exit (or Kalman ghost expiry while in-zone):
    │  Reduce accumulated samples:
    │    optimistic=True  → passed if any pass sample was observed
    │    optimistic=False → passed only if no fail sample was observed
    │  ThresholdTracker.record() and save_event() fire exactly once per
    │  (tracker, test case).
```

## Evaluation zone

The `ZoneTracker` tracks detection movement against a rectangular zone
configured by:

- **zoneDirection**: `HORIZONTAL` (zone spans full width, thick on y) or
  `VERTICAL` (zone spans full height, thick on x)
- **zoneCenter**: 0.0–1.0 normalized zone center on the direction axis
- **zoneThickness**: 0.0–1.0 normalized zone thickness on the direction axis

The active zone range on the direction axis is
`[zoneCenter − zoneThickness/2, zoneCenter + zoneThickness/2]`, clamped
to `[0, 1]`.

Detections are matched between frames using nearest-neighbour distance per
label (Kalman filter under the hood). A tracker is "in the zone" while its
bbox center lies within the zone; it "enters" on the first confirmed frame
inside and "exits" on the first frame outside (or when its Kalman ghost
expires while still marked in-zone).

- **Counters** (`dashboard_counter`) increment once per tracker on entry.
- **Metric samples** and **violation events** are committed once per
  `(tracker, test case)` on exit, using the optimistic/pessimistic reducer.
- **Live overlay** (`dashboard_detections` + per-detection `violations`)
  still reflects the current-frame evaluation of in-zone detections so the
  UI highlights violating objects in real time.
- **Presumed entries**: a tracker first observed inside the zone (brand-new
  tracklet born in-zone, or matched tracker that confirmed this frame
  while already in-zone) is presumed to have entered from the configured
  direction's expected side, so it is eligible for both counter and commit
  on a clean exit. The exit-side gate still discards wrong-way traversals.

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

`dashboard_detections` is populated every frame an in-zone detection violates
at least one test case.

## Running tests

```bash
python3 -m pytest tests/dashboard/ -v
```
