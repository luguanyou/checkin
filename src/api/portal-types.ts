export interface StudentVisibility { attendance_visible: boolean; score_visibility: 'HIDDEN' | 'TOTAL' | 'DETAILS' }
export interface StudentClass extends StudentVisibility { id: string; name: string; course_name: string; term: string; teacher_name?: string; can_record_scores?: boolean; can_review_registrations?: boolean }
export interface StudentClassData extends StudentVisibility {
  attendance: { id: string; date: string; status: string; session_status: string }[] | null;
  score: { final_score: string | null; status: string } | null;
  details: {
    settings: import('./scores-types').ScoreSettings;
    summary: import('./scores-types').ScoreSummary | null;
    items: import('./scores-types').ScoreItem[];
    records: import('./scores-types').ScoreRecord[];
  } | null;
}
