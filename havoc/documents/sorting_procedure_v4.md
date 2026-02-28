# Sorting Procedure v4.0

## Document Information
- Document ID: SOP-SORT-004
- Revision: 4.0
- Effective Date: 2026-02-28
- Department: Quality & Production

## 1. Purpose

This document defines the updated standard operating procedure for automated part sorting at Station 7. Changes from v3: adjusted size thresholds, added yellow part category.

## 2. Sorting Criteria

| Part Type | Color  | Size Range (mm) | Target Bin |
|-----------|--------|-----------------|------------|
| Type A    | red    | >45             | BIN_A      |
| Type B    | blue   | 30-50           | BIN_B      |
| Type C    | green  | <30             | BIN_C      |
| Type D    | yellow | any             | BIN_D      |
| Defective | any    | any             | REJECT     |

## 3. Quality Inspection

Parts with visible surface defects, cracks, or discoloration must be rejected regardless of color or size classification.

## 4. Safety Constraints

- Maximum robot speed during sorting: 85%
- Grip force must not exceed 15N
