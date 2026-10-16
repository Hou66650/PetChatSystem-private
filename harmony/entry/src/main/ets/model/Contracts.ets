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
