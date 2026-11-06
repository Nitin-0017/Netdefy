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

import {
  DetectionSchemaResponse,
  SingleFlowAnalyzeResponse,
  BatchAnalyzeResponse,
  CsvUploadResponse,
  DetectionSessionSummary,
  DetectionSessionDetail,
  DetectionStats,
} from '../types/detection';

const API_BASE = '/api/v1';

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    let errorDetail = res.statusText;
    try {
      const errObj = await res.json();
      if (errObj && errObj.detail) {
        errorDetail =
          typeof errObj.detail === 'string'
            ? errObj.detail
            : JSON.stringify(errObj.detail);
      }
    } catch {
      // Ignore JSON parse failure on raw error text
    }
    throw new Error(errorDetail || `API request failed with status ${res.status}`);
  }
  return res.json();
}

export const apiService = {
  // ==========================================
  // DETECTION CONSOLE APIS
  // ==========================================
  getDetectionSchema: (): Promise<DetectionSchemaResponse> =>
    fetchJson<DetectionSchemaResponse>(`${API_BASE}/detection/schema`),

  getDetectionStats: (): Promise<DetectionStats> =>
    fetchJson<DetectionStats>(`${API_BASE}/detection/stats`),

  analyzeFlow: (payload: {
    features: Record<string, number>;
    flow_id?: string | null;
    source?: string | null;
    is_synthetic?: boolean;
  }): Promise<SingleFlowAnalyzeResponse> =>
    fetchJson<SingleFlowAnalyzeResponse>(`${API_BASE}/detection/analyze-flow`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  analyzeBatch: (payload: {
    flows: Array<{ flow_id?: string | number | null; features: Record<string, number>; label?: string | null }>;
    source_name?: string;
  }): Promise<BatchAnalyzeResponse> =>
    fetchJson<BatchAnalyzeResponse>(`${API_BASE}/detection/analyze-batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  uploadCsv: async (file: File, maxRows: number = 500): Promise<CsvUploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('max_rows', maxRows.toString());

    return fetchJson<CsvUploadResponse>(`${API_BASE}/detection/upload-csv`, {
      method: 'POST',
      body: formData,
    });
  },

  getDetectionHistory: (
    limit: number = 50,
    offset: number = 0
  ): Promise<{ sessions: DetectionSessionSummary[]; total_count: number; limit: number; offset: number }> =>
    fetchJson<{ sessions: DetectionSessionSummary[]; total_count: number; limit: number; offset: number }>(
      `${API_BASE}/detection/history?limit=${limit}&offset=${offset}`
    ),

  getDetectionSession: (sessionId: string): Promise<DetectionSessionDetail> =>
    fetchJson<DetectionSessionDetail>(`${API_BASE}/detection/history/${sessionId}`),

  clearDetectionHistory: (): Promise<{ message: string }> =>
    fetchJson<{ message: string }>(`${API_BASE}/detection/history`, {
      method: 'DELETE',
    }),

  getSampleCsvUrl: (): string => `${API_BASE}/detection/sample-csv`,

  // ==========================================
  // RESEARCH WORKBENCH APIS (PRESERVED)
  // ==========================================
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
    return fetchJson<PredictionResponse>(`${API_BASE}/playground/predict`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
  },
};
