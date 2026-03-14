import { AGENT_ID, agentObsidianConfig, SAFETY_ENABLED } from './config.js';
import {
  decayMemories,
  getConversationWindow,
  getPendingHandoffs,
  getRecentMemories,
  getTeamActivity,
  logConversationTurn,
  pruneConversationLog,
  saveMemory,
  searchMemories,
  touchMemory,
  updateHandoffStatus,
  type Memory,
} from './db.js';
import { callGeminiJSON, isGeminiAvailable } from './gemini.js';
import { runLearningPipeline } from './learning.js';
import { logger } from './logger.js';
import { buildObsidianContext } from './obsidian.js';
import { sanitizeMemoryContent } from './safety.js';
import {
  buildRecallFilterMessage,
  buildRecallQueryMessage,
  RECALL_FILTER_SYSTEM,
  RECALL_QUERY_SYSTEM,
} from './prompts.js';

/**
 * Build a compact memory context string to prepend to the user's message.
 *
 * If Gemini is available, uses smart recall:
 *   1. Gemini generates search queries from user message + recent conversation
 *   2. FTS5 search across all sectors using those queries
 *   3. Gemini filters candidates for relevance
 *
 * If Gemini is unavailable, falls back to the basic 2-layer approach:
 *   Layer 1: FTS5 keyword search against user message -> top 3 results
 *   Layer 2: Most recent 5 memories (recency)
 *   Deduplicates between layers.
 *
 * Returns empty string if no memories exist for this chat.
 */
export async function buildMemoryContext(
  chatId: string,
  userMessage: string,
): Promise<string> {
  let lines: string[];

  if (isGeminiAvailable()) {
    lines = await smartRecall(chatId, userMessage);
  } else {
    lines = basicRecall(chatId, userMessage);
  }

  const teamBlock = buildTeamContext();

  if (lines.length === 0 && !agentObsidianConfig && !teamBlock) return '';

  const memBlock = lines.length > 0
    ? `[Memory context]\n${lines.join('\n')}\n[End memory context]`
    : '';
  const obsidianBlock = buildObsidianContext(agentObsidianConfig);

  return [memBlock, obsidianBlock, teamBlock].filter(Boolean).join('\n\n');
}

function buildTeamContext(): string {
  if (AGENT_ID === 'main') return '';

  const lines: string[] = [];

  // Pending handoffs targeted at this agent (highest priority)
  const handoffs = getPendingHandoffs(AGENT_ID);
  if (handoffs.length > 0) {
    lines.push('[Pending handoffs for you]');
    for (const h of handoffs) {
      const safeSummary = SAFETY_ENABLED ? sanitizeMemoryContent(h.summary) : h.summary;
      const safeArtifacts = h.artifacts && SAFETY_ENABLED ? sanitizeMemoryContent(h.artifacts) : h.artifacts;
      lines.push(`- FROM ${h.agent_id}: ${safeSummary}${safeArtifacts ? ` [artifacts: ${safeArtifacts}]` : ''}`);
      updateHandoffStatus(h.id, 'accepted');
    }
    lines.push('[End handoffs]');
  }

  // Recent team activity (last 8 entries from other agents)
  const activity = getTeamActivity(AGENT_ID, 8);
  if (activity.length > 0) {
    lines.push('[Recent team activity]');
    for (const a of activity) {
      const age = Math.floor((Date.now() / 1000 - a.created_at) / 60);
      const timeLabel = age < 60 ? `${age}m ago` : `${Math.floor(age / 60)}h ago`;
      const safeSummary = SAFETY_ENABLED ? sanitizeMemoryContent(a.summary) : a.summary;
      lines.push(`- ${a.agent_id} (${timeLabel}): ${a.action} -- ${safeSummary}`);
    }
    lines.push('[End team activity]');
  }

  return lines.join('\n');
}

function basicRecall(chatId: string, userMessage: string): string[] {
  const seen = new Set<number>();
  const lines: string[] = [];

  // Layer 1: keyword search
  const searched = searchMemories(chatId, userMessage, 3);
  for (const mem of searched) {
    seen.add(mem.id);
    touchMemory(mem.id);
    const content = SAFETY_ENABLED ? sanitizeMemoryContent(mem.content) : mem.content;
    lines.push(`- ${content} (${mem.sector})`);
  }

  // Layer 2: recent memories (deduplicated)
  const recent = getRecentMemories(chatId, 5);
  for (const mem of recent) {
    if (seen.has(mem.id)) continue;
    seen.add(mem.id);
    touchMemory(mem.id);
    const content = SAFETY_ENABLED ? sanitizeMemoryContent(mem.content) : mem.content;
    lines.push(`- ${content} (${mem.sector})`);
  }

  return lines;
}

async function smartRecall(chatId: string, userMessage: string): Promise<string[]> {
  try {
    // Get recent conversation for context
    const recentTurns = getConversationWindow(chatId, 6);
    const recentContext = recentTurns
      .map((t) => `${t.role}: ${t.content.slice(0, 200)}`)
      .join('\n');

    // Step 1: Gemini generates search queries
    const queries = await callGeminiJSON<string[]>(
      buildRecallQueryMessage(userMessage, recentContext),
      { systemInstruction: RECALL_QUERY_SYSTEM },
    );

    if (!Array.isArray(queries) || queries.length === 0) {
      return basicRecall(chatId, userMessage);
    }

    // Step 2: FTS5 search using generated queries
    const seen = new Set<number>();
    const candidates: Memory[] = [];

    for (const query of queries.slice(0, 4)) {
      const results = searchMemories(chatId, query, 5);
      for (const mem of results) {
        if (!seen.has(mem.id)) {
          seen.add(mem.id);
          candidates.push(mem);
        }
      }
    }

    // Also add recent memories as candidates
    const recent = getRecentMemories(chatId, 3);
    for (const mem of recent) {
      if (!seen.has(mem.id)) {
        seen.add(mem.id);
        candidates.push(mem);
      }
    }

    if (candidates.length === 0) return [];

    // Step 3: Gemini filters for relevance
    const candidateList = candidates.map((c) => ({
      id: c.id,
      content: c.content,
      sector: c.sector,
    }));

    const relevantIds = await callGeminiJSON<number[]>(
      buildRecallFilterMessage(userMessage, candidateList),
      { systemInstruction: RECALL_FILTER_SYSTEM },
    );

    const relevantSet = new Set(Array.isArray(relevantIds) ? relevantIds : []);
    const lines: string[] = [];

    // If Gemini returned no relevant IDs, fall back to all candidates (capped)
    const selected = relevantSet.size > 0
      ? candidates.filter((c) => relevantSet.has(c.id))
      : candidates.slice(0, 5);

    for (const mem of selected) {
      touchMemory(mem.id);
      const content = SAFETY_ENABLED ? sanitizeMemoryContent(mem.content) : mem.content;
      lines.push(`- ${content} (${mem.sector})`);
    }

    return lines;
  } catch (err) {
    logger.warn({ err }, 'Smart recall failed, falling back to basic');
    return basicRecall(chatId, userMessage);
  }
}

/**
 * Save a conversation turn and trigger the learning pipeline.
 * Conversation logging is synchronous. Learning runs fire-and-forget in background.
 */
export function saveConversationTurn(
  chatId: string,
  userMessage: string,
  claudeResponse: string,
  sessionId?: string,
  agentId = 'main',
): void {
  try {
    // Always log full conversation to conversation_log (for /respin)
    logConversationTurn(chatId, 'user', userMessage, sessionId, agentId);
    logConversationTurn(chatId, 'assistant', claudeResponse, sessionId, agentId);
  } catch (err) {
    console.error('Failed to log conversation turn:', err);
  }

  // Skip short or command-like messages
  if (userMessage.length <= 20 || userMessage.startsWith('/')) return;

  // Fire-and-forget: Gemini-powered learning pipeline (async, background)
  runLearningPipeline(chatId, userMessage, claudeResponse).catch((err) => {
    logger.error({ err }, 'Learning pipeline error (fire-and-forget)');
  });

  // Fallback: if Gemini is unavailable, use basic regex extraction
  if (!isGeminiAvailable()) {
    try {
      const SEMANTIC_SIGNALS = /\b(my|i am|i'm|i prefer|remember|always|never)\b/i;
      if (SEMANTIC_SIGNALS.test(userMessage)) {
        saveMemory(chatId, userMessage, 'semantic');
      } else {
        saveMemory(chatId, userMessage, 'episodic');
      }
    } catch (err) {
      console.error('Failed to save memory:', err);
    }
  }
}

/**
 * Run the daily decay sweep. Call once on startup and every 24h.
 * Also prunes old conversation_log entries to prevent unbounded growth.
 */
export function runDecaySweep(): void {
  decayMemories();
  pruneConversationLog(500);
}
