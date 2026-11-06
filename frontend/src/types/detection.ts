import { PredictionResponse } from './research';

export interface DetectionFeatureMeta {
  name: string;
  category: string;
  category_title: string;
  unit: string;
  default_value: number;
}

export interface DetectionCategoryMeta {
  id: string;
  title: string;
  feature_count: number;
}

export interface DetectionSchemaResponse {
  total_features: number;
  features: DetectionFeatureMeta[];
  categories: DetectionCategoryMeta[];
  trained_classes: string[];
  absent_categories: string[];
}

export interface FlowPredictionItem extends PredictionResponse {
  ground_truth_label?: string | null;
}

export interface SingleFlowAnalyzeResponse {
  session_id: string;
  prediction: FlowPredictionItem;
  scientific_note?: string | null;
  is_synthetic?: boolean;
}

export interface BatchAnalyzeResponse {
  session_id: string;
  total_flows: number;
  normal_count: number;
  suspicious_known_count: number;
  suspicious_unknown_count: number;
  review_required_count: number;
  decision_counts: Record<string, number>;
  predictions: FlowPredictionItem[];
}

export interface CsvUploadResponse {
  session_id: string;
  filename: string;
  total_rows_evaluated: number;
  total_csv_rows: number;
  invalid_rows_cleaned: number;
  has_ground_truth_labels: boolean;
  normal_count: number;
  suspicious_known_count: number;
  suspicious_unknown_count: number;
  review_required_count: number;
  decision_counts: Record<string, number>;
  predictions: FlowPredictionItem[];
}

export interface DetectionSessionSummary {
  id: string;
  timestamp: string;
  source: string;
  flow_count: number;
  normal_count: number;
  suspicious_known_count: number;
  suspicious_unknown_count: number;
  review_required_count: number;
  status: string;
}

export interface DetectionSessionDetail extends DetectionSessionSummary {
  predictions: FlowPredictionItem[];
}

export interface DetectionStats {
  total_sessions: number;
  total_flows_analyzed: number;
  normal_flows: number;
  suspicious_flows: number;
  suspicious_known_flows: number;
  suspicious_unknown_flows: number;
  review_required_flows: number;
  recent_sessions: Array<{
    id: string;
    timestamp: string;
    source: string;
    flow_count: number;
    normal_count: number;
    suspicious_count: number;
    review_required_count: number;
  }>;
}

