import Anthropic from '@anthropic-ai/sdk';

import { UTILITY_MODEL_API_KEY } from './config.js';
import { logger } from './logger.js';

const MODEL = 'claude-sonnet-4-6';

let client: Anthropic | null = null;

function getClient(): Anthropic {
  if (!client) {
    client = new Anthropic({ apiKey: UTILITY_MODEL_API_KEY });
  }
  return client;
}

export function isGeminiAvailable(): boolean {
  return !!UTILITY_MODEL_API_KEY;
}

export async function callGemini(
  message: string,
  options?: { systemInstruction?: string; maxTokens?: number },
): Promise<string> {
  const ai = getClient();
  const response = await ai.messages.create({
    model: MODEL,
    max_tokens: options?.maxTokens ?? 1024,
    temperature: 0.2,
    system: options?.systemInstruction || '',
    messages: [{ role: 'user', content: message }],
  });
  const block = response.content[0];
  return block.type === 'text' ? block.text : '';
}

export async function callGeminiJSON<T>(
  message: string,
  options?: { systemInstruction?: string; maxTokens?: number },
): Promise<T> {
  const ai = getClient();
  const systemText = (options?.systemInstruction || '') +
    '\n\nIMPORTANT: Respond with ONLY valid JSON. No markdown fences, no extra text.';

  const response = await ai.messages.create({
    model: MODEL,
    max_tokens: options?.maxTokens ?? 1024,
    temperature: 0.1,
    system: systemText,
    messages: [{ role: 'user', content: message }],
  });

  const block = response.content[0];
  const text = block.type === 'text' ? block.text : '';

  // Try direct parse first
  try {
    return JSON.parse(text) as T;
  } catch {
    // Fallback: extract from markdown code fence
    const match = text.match(/```(?:json)?\s*\n?([\s\S]*?)\n?\s*```/);
    if (match) {
      return JSON.parse(match[1]) as T;
    }
    logger.warn({ text: text.slice(0, 200) }, 'Utility model JSON parse failed');
    throw new Error('Failed to parse utility model JSON response');
  }
}
