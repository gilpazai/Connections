// TypeScript interfaces matching Pydantic models

export interface Contact {
  name: string;
  linkedin_url: string;
  company_current: string;
  title_current: string;
  relationship_strength: "Close" | "Medium" | "Loose";
  tags: string[];
  dealigence_person_id: string;
  last_enriched: string | null;
  status: "Active" | "Inactive";
  notes: string;
  notion_page_id: string;
}

export interface Lead {
  name: string;
  linkedin_url: string;
  company_current: string;
  title_current: string;
  priority: "High" | "Medium" | "Low";
  batch: string;
  dealigence_person_id: string;
  last_enriched: string | null;
  status: "New" | "Enriched" | "Matched" | "Contacted" | "Converted" | "Archived";
  notes: string;
  notion_page_id: string;
}

export interface Match {
  contact_name: string;
  contact_id: string;
  lead_name: string;
  lead_id: string;
  shared_company: string;
  overlap_start: string | null;
  overlap_end: string | null;
  overlap_months: number;
  contact_role: string;
  lead_role: string;
  rule_name: string;
  confidence: "High" | "Medium" | "Low";
  status: "New" | "Request Intro" | "Intro" | "In CRM";
  intro_draft: string;
  date_updated: string | null;
  notes: string;
  contact_linkedin: string;
  lead_linkedin: string;
  lead_company: string;
  lead_title: string;
  notion_page_id: string;
}

export interface WorkHistoryEntry {
  person_name: string;
  person_type: string;
  employer_name: string;
  employer_dealigence_id: string;
  role_title: string;
  seniority: string;
  start_date: string | null;
  end_date: string | null;
  is_advisory: boolean;
  tenure_years: number;
  source_person_id: string;
  notion_page_id: string;
}

export interface ConnectivityStatus {
  notion: boolean;
  anthropic: boolean;
  gemini: boolean;
  openai: boolean;
  ollama: boolean;
}
