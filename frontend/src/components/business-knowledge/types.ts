export type FieldType = 'text' | 'long_text' | 'integer' | 'decimal' | 'boolean' | 'date' | 'url' | 'select' | 'multi_select';
export type Audience = 'team' | 'management';
export type KnowledgePayload = {
  label?: string; type?: FieldType; group?: string; hint?: string; unit?: string;
  min?: number; max?: number; location_only?: boolean; template_key?: string;
  options?: { id: string; label: string; archived: boolean }[];
  state?: 'set' | 'unknown' | 'not_applicable'; value?: string | number | boolean | string[] | null;
  text?: string; valid_until?: string; source?: string; status?: string; filename?: string; origin_id?: string;
};
export type KnowledgeRecord = {
  id: string; kind: string; record_key: string; scope_type: string; scope_id: string;
  payload_json: KnowledgePayload; audience: Audience; version: number; archived: boolean;
  updated_at: string; updated_by: string; inherited?: boolean; value_record?: KnowledgeRecord | null;
};
export type KnowledgeData = {
  enabled: boolean; name: string; business_type?: string; can_edit: boolean; can_configure: boolean;
  fields: KnowledgeRecord[]; rules: KnowledgeRecord[]; documents: KnowledgeRecord[];
  archived?: KnowledgeRecord[];
  proposals?:{id:string;original_text:string;user_id:string;occurred_at:string;applied?:boolean;facts_json:{knowledge_proposal:{record_id:string;kind:string;label:string}}}[];
  members: {user_id: string; name: string; role: string}[];
  editors: {user_id: string; enabled: boolean; version: number}[];
  existing_sources: {label: string; href: string}[];
  inventory?: {available: boolean; complete: boolean; classification_notice?:string; active_resource_count?:number|null; version?: number; message?: string;
    items: {id: string; name: string; type: string}[];
    mismatches?: {field_id: string; label: string; declared: number; listed: number}[]};
  locations?: {total: number; items: {id: string; name: string; address?: string | null}[];
    summaries: {label: string; unit: string; value: number; coverage: number}[]};
};
export type KnowledgeChange = {
  operation: string; id?: string; version?: number; audience?: Audience; archived?: boolean;
  payload?: KnowledgePayload | Record<string, unknown>;
};
export type KnowledgeTemplate = {type_key: string; label: string; fields: KnowledgePayload[]};
export type KnowledgeHistory = {id: string; actor_id: string; created_at: string; before_json: KnowledgeRecord | null; after_json: KnowledgeRecord};
export type KnowledgeScope = {type: 'business' | 'network'; id: string};
