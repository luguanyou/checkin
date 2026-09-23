export type ScoreCategory = 'HOMEWORK' | 'CLASSROOM' | 'LAB' | 'OTHER';
export interface ScoreSettings { base_score: string | null; factors: Record<ScoreCategory, string | null> }
export interface ScoreItem { id: string; category: ScoreCategory; name: string; occurred_on: string; description: string; default_points: string | null }
export interface ScoreStudent { enrollment_id: string; student_id: string; student_number: string; student_name: string; enrollment_status: 'ACTIVE' | 'REMOVED' }
export interface ScoreRecord { id: string; item_id: string; enrollment_id: string; points: string | null; note: string; updated_at: string }
export interface ScoreSummary {
  enrollment_id: string;
  categories: { category: ScoreCategory; points: string; contribution: string | null; pending: number }[];
  raw_score: string | null; final_score: string | null;
  status: 'READY' | 'RULES_PENDING' | 'RECORDS_PENDING';
}
export interface ScoreBook {
  class_group: { id: string; name: string; status: 'ACTIVE' | 'ARCHIVED' };
  course: { id: string; name: string; status: 'ACTIVE' | 'ARCHIVED' };
  version: number; readonly: boolean; rules_ready: boolean;
  settings: ScoreSettings; items: ScoreItem[]; students: ScoreStudent[];
  records: ScoreRecord[]; summaries: ScoreSummary[];
}
export interface ScoreHistory { id: string; action: string; actor_name: string; created_at: string; before_value: Record<string, unknown> | null; after_value: Record<string, unknown> | null }
export interface ScoreRecordInput { enrollment_id: string; points: string | null; note: string }
export interface ScoreItemInput { category: ScoreCategory; name: string; occurred_on: string; description: string; default_points: string | null }
