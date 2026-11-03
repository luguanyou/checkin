import type { Student } from './types';
import type { ScoreItem, ScoreRecord, ScoreStudent, ScoreRecordInput } from './scores-types';
export interface MonitorManagement {
  readonly: boolean;
  items: ScoreItem[];
  members: { student: Student; enrollment_status: string; user_id: string | null; username: string | null; account_status: string | null; item_ids: string[]; can_review_registrations?: boolean }[];
}
export interface MonitorProject {
  version: number; item: ScoreItem;
  students: (ScoreStudent & { can_edit: boolean })[];
  records: ScoreRecord[];
}
export interface MonitorProjectOption extends ScoreItem { class_id: string; class_name: string; course_name: string }
export interface MonitorSaveInput { expected_version: number; records: ScoreRecordInput[] }
