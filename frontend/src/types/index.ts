export interface TranscriptEntry {
  role: "customer" | "agent" | "user" | "system";
  text: string;
  timestamp: string;
  attachment?: {
    type: "location" | "image";
    label: string;
    url?: string;
  };
}

export interface ToolCallEntry {
  tool: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  timestamp: string;
}

export interface GarageInfo {
  name: string;
  address: string;
  distance_miles: number;
  eta_minutes: number;
  phone: string;
}

export interface CoverageDecision {
  status: "covered" | "not_covered" | "uncertain";
  confidence: number;
  cited_clauses: string[];
  explanation: string;
  requires_human_review: boolean;
}

export interface NextAction {
  recommended_action: string;
  service_type: string;
  assigned_garage: GarageInfo;
  estimated_arrival: string;
}

export interface CustomerNotification {
  reference_number: string;
  message_text: string;
  coverage_summary: string;
  assistance_type: string;
  eta: string | null;
}

export interface IncidentData {
  customer_name: string | null;
  policy_number: string | null;
  vehicle: string | null;
  location: string | null;
  incident_type: string | null;
  situation_summary: string | null;
}

export interface WSEvent {
  event_type: string;
  call_id: string;
  timestamp: string;
  payload: Record<string, unknown>;
}

export interface CallState {
  callId: string;
  status: "active" | "processing" | "completed" | "idle";
  transcript: TranscriptEntry[];
  toolCalls: ToolCallEntry[];
  coverage: CoverageDecision | null;
  action: NextAction | null;
  notification: CustomerNotification | null;
  humanOverride: string | null;
}
