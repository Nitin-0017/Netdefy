import {
  ResearchOverview,
  ModelComparisonItem,
  ThresholdTier,
  ConfusionMatrixResponse,
  FeatureImportanceItem,
  ExplainabilitySpec,
  CuratedSample,
  PredictionResponse,
} from '../types/research';

const API_BASE = '/api/v1';

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`API error ${res.status}: ${errorText}`);
  }
  return res.json();
}

export const apiService = {
  getOverview: (): Promise<ResearchOverview> =>
    fetchJson<ResearchOverview>(`${API_BASE}/research/overview`),

  getComparison: (): Promise<{ benchmark_partition: string; models: ModelComparisonItem[]; key_takeaways: string[] }> =>
    fetchJson<{ benchmark_partition: string; models: ModelComparisonItem[]; key_takeaways: string[] }>(
      `${API_BASE}/research/comparison`
    ),

  getThresholds: (): Promise<{ calibration_dataset: string; methodology: string; threshold_tiers: ThresholdTier[] }> =>
    fetchJson<{ calibration_dataset: string; methodology: string; threshold_tiers: ThresholdTier[] }>(
      `${API_BASE}/research/thresholds`
    ),

  getConfusionMatrices: (): Promise<ConfusionMatrixResponse> =>
    fetchJson<ConfusionMatrixResponse>(`${API_BASE}/research/confusion-matrix`),

  getFeatureImportance: (): Promise<{
    xgboost_feature_importance_gain: FeatureImportanceItem[];
    total_features_ranked: number;
    methodology: string;
    top_5_summary: FeatureImportanceItem[];
  }> =>
    fetchJson<{
      xgboost_feature_importance_gain: FeatureImportanceItem[];
      total_features_ranked: number;
      methodology: string;
      top_5_summary: FeatureImportanceItem[];
    }>(`${API_BASE}/research/feature-importance`),

  getExplainabilitySpec: (): Promise<ExplainabilitySpec> =>
    fetchJson<ExplainabilitySpec>(`${API_BASE}/research/explainability-spec`),

  getCuratedSamples: (): Promise<{ samples: CuratedSample[]; count: number }> =>
    fetchJson<{ samples: CuratedSample[]; count: number }>(`${API_BASE}/playground/samples`),

  predictFlow: async (payload: {
    features: Record<string, number>;
    flow_id?: string | number | null;
    is_synthetic?: boolean;
  }): Promise<PredictionResponse> => {
    const res = await fetch(`${API_BASE}/playground/predict`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Inference error: ${res.status}`);
    }
    return res.json();
  },
};
