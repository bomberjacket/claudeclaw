// ── Solution Extraction ──────────────────────────────────────────────

export const SOLUTION_EXTRACTION_SYSTEM = `You extract successfully executed technical solutions from conversations.
A "solution" is a concrete fix, workaround, configuration, command, or code snippet that solved a problem.
Only extract solutions that were actually applied and confirmed working in the conversation.
Respond with a JSON array of objects: [{"content": "description of the solution", "topic": "short topic key"}]
If no solutions found, return an empty array: []`;

export function buildSolutionExtractionMessage(
  userMessage: string,
  assistantResponse: string,
): string {
  return `Extract any successfully executed technical solutions from this conversation turn.

USER: ${userMessage}

ASSISTANT: ${assistantResponse}`;
}

// ── Fragment Extraction ──────────────────────────────────────────────

export const FRAGMENT_EXTRACTION_SYSTEM = `You extract important facts and knowledge fragments worth remembering from conversations.
A "fragment" is a user preference, stated fact, project detail, technical context, or personal information.
Do NOT extract: greetings, small talk, questions without answers, or things already implied by the conversation structure.
Respond with a JSON array of objects: [{"content": "the fact or knowledge", "topic": "short topic key"}]
If nothing worth memorizing, return an empty array: []`;

export function buildFragmentExtractionMessage(
  userMessage: string,
  assistantResponse: string,
): string {
  return `Extract important facts or knowledge worth memorizing from this conversation turn.

USER: ${userMessage}

ASSISTANT: ${assistantResponse}`;
}

// ── Consolidation ────────────────────────────────────────────────────

export const CONSOLIDATION_SYSTEM = `You decide how to consolidate a new memory with an existing similar memory.
Actions:
- "merge": Combine both into a single richer memory. Provide merged content.
- "replace": The new memory supersedes the old one entirely. Provide the new content.
- "update": Enhance the existing memory with new details. Provide updated content.
- "keep_separate": Both are distinct enough to keep as separate memories.
- "skip": The new memory adds nothing new; discard it.

Respond with JSON: {"action": "merge|replace|update|keep_separate|skip", "content": "merged/replaced/updated content if applicable"}`;

export function buildConsolidationMessage(
  newContent: string,
  existingContent: string,
): string {
  return `Decide how to consolidate these two memories:

EXISTING MEMORY: ${existingContent}

NEW MEMORY: ${newContent}

What action should be taken?`;
}

// ── Recall Query Prep ────────────────────────────────────────────────

export const RECALL_QUERY_SYSTEM = `You generate search queries to find relevant memories for a user's message.
Given a user message and recent conversation context, produce 2-4 short keyword search queries
that would retrieve useful memories from a full-text search index.
Focus on key topics, entities, and technical terms.
Respond with a JSON array of strings: ["query1", "query2", ...]`;

export function buildRecallQueryMessage(
  userMessage: string,
  recentContext: string,
): string {
  return `Generate search queries to find relevant memories for this user message.

RECENT CONTEXT:
${recentContext}

CURRENT MESSAGE: ${userMessage}`;
}

// ── Recall Filter ────────────────────────────────────────────────────

export const RECALL_FILTER_SYSTEM = `You filter candidate memories for relevance to the current conversation.
Given a user message and a list of candidate memories, return only the IDs of memories
that are genuinely relevant and useful for responding to the user.
Respond with a JSON array of memory IDs: [1, 5, 12]
If none are relevant, return an empty array: []`;

export function buildRecallFilterMessage(
  userMessage: string,
  candidates: Array<{ id: number; content: string; sector: string }>,
): string {
  const candidateList = candidates
    .map((c) => `[ID:${c.id}] (${c.sector}) ${c.content}`)
    .join('\n');

  return `Which of these memories are relevant to the user's current message?

USER MESSAGE: ${userMessage}

CANDIDATE MEMORIES:
${candidateList}`;
}
