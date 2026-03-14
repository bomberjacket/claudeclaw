// WhatsApp integration removed — not used in this deployment.
// This stub prevents import errors from bot.ts until references are fully cleaned up.

export interface WaChat {
  id: string;
  name: string;
  unreadCount: number;
  lastMessage: string;
  lastMessageTime: number;
  isGroup: boolean;
}

export interface WaMessage {
  body: string;
  fromMe: boolean;
  senderName: string;
  timestamp: number;
}

export async function initWhatsApp(_onIncoming?: unknown): Promise<void> {}
export async function getWaChats(_limit?: number): Promise<WaChat[]> { return []; }
export async function getWaChatMessages(_chatId?: string, _limit?: number): Promise<WaMessage[]> { return []; }
export async function sendWhatsAppMessage(_chatId?: string, _text?: string): Promise<void> {}
export function isWhatsAppReady(): boolean { return false; }
export async function notifyWhatsAppIncoming(): Promise<void> {}
