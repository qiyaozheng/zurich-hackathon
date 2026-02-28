# Sorting Procedure v3.0

## Document Information
- Document ID: SOP-SORT-003
- Revision: 3.0
- Effective Date: 2026-01-15
- Department: Quality & Production

## 1. Purpose

This document defines the standard operating procedure for automated part sorting at Station 7. All parts arriving from the assembly line must be classified by color, size, and quality before routing to the appropriate collection bin.

## 2. Sorting Criteria

| Part Type | Color | Size Range (mm) | Target Bin |
|-----------|-------|-----------------|------------|
| Type A    | red   | >50             | BIN_A      |
| Type B    | blue  | 30-50           | BIN_B      |
| Type C    | green | <30             | BIN_C      |
| Defective | any   | any             | REJECT     |

## 3. Quality Inspection

Parts with visible surface defects, cracks, or discoloration must be rejected regardless of color or size classification. The following defect types require immediate rejection:

- Surface cracks (any severity)
- Deep scratches (major or critical)
- Discoloration exceeding 20% of surface area
- Dents deeper than 0.5mm
- Foreign material contamination

## 4. Decision Priority

1. Defect check (highest priority — reject if defective)
2. Confidence check (if below 70%, request manual review)
3. Color + Size classification (route to appropriate bin)
4. Default action: Manual review if no rule matches

## 5. Safety Constraints

- Maximum robot speed during sorting: 80%
- Grip force must not exceed 15N
- Minimum clearance between robot arm and bin edges: 20mm
- Emergency stop must be accessible at all times

## 6. Tolerance Specifications

- Color detection confidence threshold: 0.70
- Size measurement tolerance: ±2mm
- Defect detection sensitivity: HIGH
- Maximum inspection time per part: 10 seconds
