export interface ResearchOverview {
  dataset_name: string;
  benchmark_version: string;
  total_benchmark_records: number;
  total_raw_dataset_records: number;
  feature_count: number;
  feature_type: string;
  random_seed: number;
  zero_leakage_invariants: number;
  class_architecture: {
    cicids_total_classes: number;
    classifier_trained_classes_count: number;
    classifier_trained_classes: string[];
    absent_unseen_classes_count: number;
    absent_unseen_classes: Array<{
      name: string;
      day: string;
      test_count: number;
      diagnostic_count?: number;
      reason: string;
    }>;
    scientific_rationale: string;
  };
  partitions: Array<{
    name: string;
    records: number;
    source_day: string;
    purpose: string;
    class_distribution: Record<string, number>;
  }>;
}

export interface ModelComparisonItem {
  id: string;
  name: string;
  paradigm: string;
  parameters: string;
  trained_on: string;
  latency_ms: number;
  closed_set_validation?: {
    accuracy?: number;
    balanced_accuracy?: number;
    macro_f1?: number;
    weighted_f1?: number;
    log_loss?: number;
    ovr_roc_auc?: number;
    roc_auc?: number;
    pr_auc?: number;
    f1?: number;
  };
  holdout_test_view_a?: {
    roc_auc?: number;
    pr_auc?: number;
    precision?: number;
    recall?: number;
    f1?: number;
    benign_fpr?: number;
    false_alarms_per_1000?: number;
    operational_alert_precision?: number;
    benign_false_alarm_rate_per_1000?: number;
    false_alarm_reduction_vs_ae?: string;
    false_alarm_reduction_vs_if?: string;
    total_attacks_escalated?: number;
    open_set_blindness?: string;
    triage_distribution?: Record<string, number>;
  };
  holdout_test_view_b?: {
    roc_auc?: number;
    f1?: number;
    attack_detection_recall?: number;
    operational_f1?: number;
    disambiguation_gain?: string;
  };
}

export interface ThresholdTier {
  tier: string;
  name: string;
  description: string;
  autoencoder_mse_threshold: number;
  isolation_forest_threshold: number;
  hybrid_fused_threshold: number;
  benign_fpr: string;
  operational_use: string;
}

export interface ConfusionMatrixResponse {
  validation_closed_set: {
    title: string;
    description: string;
    labels: string[];
    matrix: number[][];
    per_class_metrics: Record<
      string,
      {
        precision: number;
        recall: number;
        f1: number;
        support: number;
      }
    >;
  };
  test_open_set: {
    title: string;
    description: string;
    true_labels: string[];
    predicted_labels: string[];
    matrix: number[][];
  };
}

export interface FeatureImportanceItem {
  feature: string;
  gain: number;
}

export interface ExplainabilityMethod {
  model: string;
  method_name: string;
  mathematical_formulation: string;
  rationale: string;
  computational_complexity: string;
  limitations: string;
}

export interface ExplainabilitySpec {
  principles: string[];
  methods: ExplainabilityMethod[];
  why_not_bruteforce_kernel_shap: {
    title: string;
    reasons: string[];
  };
}

export interface CuratedSample {
  id: string;
  name: string;
  true_label: string;
  category_type: 'BENIGN' | 'KNOWN_ATTACK' | 'UNSEEN_ATTACK';
  in_classifier_training: boolean;
  source_split: string;
  description: string;
  key_features: Record<string, number>;
  features: Record<string, number>;
}

export interface FeatureAttribution {
  feature_name: string;
  reconstruction_error: number;
  input_value: number;
  reconstructed_value: number;
}

export interface PredictionResponse {
  flow_id: string | number | null;
  decision: 'NORMAL' | 'SUSPICIOUS_KNOWN' | 'SUSPICIOUS_UNKNOWN' | 'REVIEW_REQUIRED';
  decision_reason: string;
  anomaly: {
    isolation_forest_raw_score: number;
    isolation_forest_calibrated_score: number;
    autoencoder_raw_error: number;
    autoencoder_calibrated_score: number;
    fused_score: number;
    threshold: number;
    is_anomaly: boolean;
    threshold_tier: string;
  };
  classifier: {
    predicted_class: string;
    top_probability: number;
    second_probability: number;
    probability_margin: number;
    entropy: number;
    rejected: boolean;
    rejection_reason: string | null;
    class_probabilities: Record<string, number>;
  };
  explanation: {
    decision: string;
    decision_reason: string;
    evidence_summary: string[];
    top_contributing_features: FeatureAttribution[];
  };
  model_versions: Record<string, string>;
  scientific_note?: string | null;
  is_synthetic?: boolean;
}
