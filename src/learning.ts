import { LEARNING_ENABLED } from './config.js';
import {
  deleteMemory,
  saveMemory,
  searchMemories,
  updateMemoryContent,
  type Memory,
} from './db.js';
import { callGeminiJSON, isGeminiAvailable } from './gemini.js';
import { logger } from './logger.js';
import {
  buildConsolidationMessage,
  buildFragmentExtractionMessage,
  buildSolutionExtractionMessage,
  CONSOLIDATION_SYSTEM,
  FRAGMENT_EXTRACTION_SYSTEM,
  SOLUTION_EXTRACTION_SYSTEM,
} from './prompts.js';

interface ExtractedItem {
  content: string;
  topic: string;
}

interface ConsolidationResult {
  action: 'merge' | 'replace' | 'update' | 'keep_separate' | 'skip';
  content?: string;
}

const SOLUTION_SALIENCE = 3.0;
const FRAGMENT_SALIENCE = 1.5;
const MERGE_SALIENCE_BOOST = 0.5;

async function extractSolutions(
  userMessage: string,
  assistantResponse: string,
): Promise<ExtractedItem[]> {
  try {
    return await callGeminiJSON<ExtractedItem[]>(
      buildSolutionExtractionMessage(userMessage, assistantResponse),
      { systemInstruction: SOLUTION_EXTRACTION_SYSTEM },
    );
  } catch (err) {
    logger.warn({ err }, 'Solution extraction failed');
    return [];
  }
}

async function extractFragments(
  userMessage: string,
  assistantResponse: string,
): Promise<ExtractedItem[]> {
  try {
    return await callGeminiJSON<ExtractedItem[]>(
      buildFragmentExtractionMessage(userMessage, assistantResponse),
      { systemInstruction: FRAGMENT_EXTRACTION_SYSTEM },
    );
  } catch (err) {
    logger.warn({ err }, 'Fragment extraction failed');
    return [];
  }
}

async function consolidateWithExisting(
  chatId: string,
  newContent: string,
  sector: string,
  topicKey: string,
  salience: number,
  source: string,
): Promise<void> {
  // Search for similar memories across all sectors
  const similar = searchMemories(chatId, newContent, 3);

  if (similar.length === 0) {
    // No similar memories, direct insert
    saveMemory(chatId, newContent, sector, topicKey, salience, source);
    return;
  }

  // Try consolidation with the most relevant match
  const best = similar[0];
  try {
    const result = await callGeminiJSON<ConsolidationResult>(
      buildConsolidationMessage(newContent, best.content),
      { systemInstruction: CONSOLIDATION_SYSTEM },
    );

    switch (result.action) {
      case 'merge': {
        const mergedContent = result.content ?? `${best.content}\n${newContent}`;
        const mergedSalience = Math.min(best.salience + MERGE_SALIENCE_BOOST, 5.0);
        deleteMemory(best.id);
        saveMemory(chatId, mergedContent, sector, topicKey, mergedSalience, source);
        logger.info({ action: 'merge', sector, oldId: best.id }, 'Memory consolidated');
        break;
      }
      case 'replace': {
        const replacedContent = result.content ?? newContent;
        deleteMemory(best.id);
        saveMemory(chatId, replacedContent, sector, topicKey, salience, source);
        logger.info({ action: 'replace', sector, oldId: best.id }, 'Memory consolidated');
        break;
      }
      case 'update': {
        const updatedContent = result.content ?? `${best.content} | ${newContent}`;
        updateMemoryContent(best.id, updatedContent);
        logger.info({ action: 'update', sector, id: best.id }, 'Memory consolidated');
        break;
      }
      case 'skip':
        logger.debug({ action: 'skip', sector }, 'New memory skipped (duplicate)');
        break;
      case 'keep_separate':
      default:
        saveMemory(chatId, newContent, sector, topicKey, salience, source);
        break;
    }
  } catch (err) {
    // Consolidation failed, fallback to direct insert
    logger.warn({ err }, 'Consolidation failed, inserting directly');
    saveMemory(chatId, newContent, sector, topicKey, salience, source);
  }
}

export async function runLearningPipeline(
  chatId: string,
  userMessage: string,
  assistantResponse: string,
): Promise<void> {
  if (!LEARNING_ENABLED || !isGeminiAvailable()) return;
  if (userMessage.length < 40 || userMessage.startsWith('/')) return;

  try {
    // Run solution + fragment extraction in parallel
    const [solutionResult, fragmentResult] = await Promise.allSettled([
      extractSolutions(userMessage, assistantResponse),
      extractFragments(userMessage, assistantResponse),
    ]);

    const solutions =
      solutionResult.status === 'fulfilled' ? solutionResult.value : [];
    const fragments =
      fragmentResult.status === 'fulfilled' ? fragmentResult.value : [];

    if (solutions.length > 0) {
      logger.info({ count: solutions.length }, 'Solutions extracted');
    }
    if (fragments.length > 0) {
      logger.info({ count: fragments.length }, 'Fragments extracted');
    }

    // Process each extracted item through consolidation
    const tasks: Promise<void>[] = [];

    for (const sol of solutions) {
      if (sol.content?.trim()) {
        tasks.push(
          consolidateWithExisting(
            chatId,
            sol.content.trim(),
            'solution',
            sol.topic || 'general',
            SOLUTION_SALIENCE,
            'auto_solution',
          ),
        );
      }
    }

    for (const frag of fragments) {
      if (frag.content?.trim()) {
        tasks.push(
          consolidateWithExisting(
            chatId,
            frag.content.trim(),
            'fragment',
            frag.topic || 'general',
            FRAGMENT_SALIENCE,
            'auto_fragment',
          ),
        );
      }
    }

    await Promise.allSettled(tasks);
  } catch (err) {
    logger.error({ err }, 'Learning pipeline failed');
  }
}
