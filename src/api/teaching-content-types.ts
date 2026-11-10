export type ContentKind = 'MATERIAL' | 'ASSIGNMENT';
export type MaterialCategory = 'CLASSROOM' | 'SELF_STUDY';

export interface TeachingContent {
  id: string;
  kind: ContentKind;
  title: string;
  description: string;
  chapter: string | null;
  category: MaterialCategory | null;
  url: string | null;
  due_at: string | null;
  submission_method: string | null;
  resource_id: string | null;
  attachment_name: string | null;
}

export interface TeacherTeachingContent extends TeachingContent {
  class_ids: string[];
}

export interface PublicationClass {
  id: string;
  name: string;
  status: 'ACTIVE' | 'ARCHIVED';
}

export interface TeacherTeachingContentList {
  course_name: string;
  classes: PublicationClass[];
  items: TeacherTeachingContent[];
}

export type TeachingContentInput = Omit<TeacherTeachingContent, 'id' | 'attachment_name'> & {
  remove_attachment: boolean;
};
