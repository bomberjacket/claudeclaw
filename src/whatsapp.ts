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

export async function initWhatsApp(): Promise<void> {}
export async function getWaChats(): Promise<WaChat[]> { return []; }
export async function getWaChatMessages(): Promise<WaMessage[]> { return []; }
export async function sendWhatsAppMessage(): Promise<void> {}
export function isWhatsAppReady(): boolean { return false; }
export async function notifyWhatsAppIncoming(): Promise<void> {}
