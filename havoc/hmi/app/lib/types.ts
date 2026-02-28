export interface DocumentSource {
  document_id: string;
  document_name: string;
  page: number;
  section: string;
  table_id?: string;
  row?: number;
  cell_text: string;
  bbox?: number[];
  confidence: number;
}

export interface PartClassification {
  color: string;
  color_hex: string;
  size_mm: number;
  size_category: "small" | "medium" | "large";
  part_type: string;
  shape: "round" | "square" | "irregular";
  confidence: number;
}

export interface DefectDetail {
  type: string;
  severity: "minor" | "major" | "critical";
  location: string;
  confidence: number;
}

export interface DefectInspection {
  defect_detected: boolean;
  defects: DefectDetail[];
  surface_quality: "perfect" | "acceptable" | "poor" | "reject";
  overall_confidence: number;
}

export interface Decision {
  part_id: string;
  target_bin: string;
  action: string;
  rule_id: string;
  rule_condition: string;
  source?: DocumentSource;
  confidence: number;
  requires_operator: boolean;
}

export interface InspectionResult {
  part_id: string;
  timestamp: string;
  classification: PartClassification;
  defect_inspection: DefectInspection;
  decision: Decision;
}

export interface DecisionRule {
  id: string;
  priority: number;
  condition: string;
  action: string;
  target_bin: string;
  source?: DocumentSource;
}

export interface ExecutablePolicy {
  policy_id: string;
  version: number;
  status: "DRAFT" | "APPROVED" | "SUSPENDED" | "REJECTED";
  decision_rules: DecisionRule[];
  safety_constraints: Array<{ id: string; parameter: string; operator: string; value: number; unit: string }>;
  source_documents: DocumentSource[];
  created_at: string;
}

export interface WSEvent {
  type: "inspection" | "decision" | "command" | "error" | "policy_update" | "status" | "operator_request" | "factory_floor";
  data: Record<string, unknown>;
  timestamp: string;
}

export interface FactoryFloorEvent {
  animation: "PICK" | "PLACE" | "MOVE" | "STOP" | "INSPECT";
  target?: string;
  part_id?: string;
  part_color?: string;
  status: "OK" | "ERROR";
}

export interface ShiftStats {
  total_inspected: number;
  passed: number;
  rejected: number;
  manual_reviews: number;
  operator_overrides: number;
  pass_rate: number;
  avg_confidence: number;
}
