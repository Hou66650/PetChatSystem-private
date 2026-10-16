export interface PetInfo {
  id: number;
  name: string;
  role: string;
  avatar: string;
  background: string;
}

export interface Bootstrap {
  apiVersion: number;
  appVersion: string;
  pets: PetInfo[];
  maxMessageChars: number;
  sessionCookieName: string;
}

export interface Account { username: string; }
export interface LoginRequest { username: string; password: string; }
export interface ApiError { error?: string; }
export interface ChatRequest { petId: number; message: string; requestId: string; }
export interface ChatReply { reply: string; requestId?: string; }
export interface ChatMessage {
  id: number;
  petId: number;
  role: string;
  content: string;
  created_at: string;
}
export interface History { messages: ChatMessage[]; }

export interface CompanionMemory { id: number; category: string; petId: number; label: string; value: string; }
export interface CompanionProfile {
  petId: number;
  name: string;
  species: string;
  role: string;
  companionStyle: string;
  interactionCount: number;
  enabled: boolean;
  memories: CompanionMemory[];
}
export interface MemorySettings { enabled: boolean; }

export interface MemoryInput { category: string; value: string; }
export interface CareSettings { enabled: number; emotion: number; quiet_start: number; quiet_end: number; }
export interface CareSettingsInput { enabled: boolean; emotion: boolean; quiet_start: number; quiet_end: number; }
export interface CareEvent {
  id: string; title: string; source: string; event_at: number; remind_at: number; state: string;
}
export interface CareState { petId: number; memoryEnabled: boolean; settings: CareSettings; events: CareEvent[]; }
export interface CareEventInput { title: string; event_at: number; remind_at: number; }
export interface CareNotice { id: string; title: string; message: string; }
export interface CareClaim { notice: CareNotice | null; }
