export interface RegistrationClass { id: string; name: string; course_name: string; term: string }
export interface RegistrationApplication { id: string; student_number: string; name: string; status: 'PENDING'|'APPROVED'|'REJECTED'; created_at: string; updated_at: string; reviewer_name: string|null; reason: string|null; can_review: boolean; history?: { reviewer_name: string; status: 'APPROVED'|'REJECTED'; reason: string|null; created_at: string }[] }
export interface StudentRegistrationInput { student_number: string; name: string; class_id: string; password: string }
