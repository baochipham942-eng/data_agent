import type { 
  Conversation, 
  Message, 
  ServerStatus, 
  SSEMessage,
  QueryAnalysis,
} from '../types';

// 重新导出类型以便其他模块使用
export type { QueryAnalysis } from '../types';

const API_BASE = '/api';

export async function fetchConversations(): Promise<Conversation[]> {
  const res = await fetch(`${API_BASE}/chat/conversations`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return data.conversations || [];
}

export async function fetchConversation(convId: string): Promise<{ messages: Message[] }> {
  const res = await fetch(`${API_BASE}/chat/conversation/${convId}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function deleteConversation(convId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/chat/conversation/${convId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

export async function checkServerStatus(): Promise<ServerStatus> {
  const res = await fetch(`${API_BASE}/server/status`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function startServer(): Promise<{ success: boolean; message?: string }> {
  const res = await fetch(`${API_BASE}/server/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function stopServer(): Promise<{ success: boolean; message?: string }> {
  const res = await fetch(`${API_BASE}/server/stop`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export interface StreamCallbacks {
  onText: (text: string) => void;
  onSSE: (data: SSEMessage) => void;
  onComplete: (fullResponse: string) => void;
  onError: (error: Error) => void;
}

export async function sendChatMessage(
  message: string,
  conversationId: string | null,
  history: { role: string; content: string }[],
  callbacks: StreamCallbacks,
  userInfo?: { userId?: string; userNickname?: string },
): Promise<void> {
  // 构建 Vanna API 请求格式
  const payload: Record<string, unknown> = {
    message,
    conversation_id: conversationId || undefined,
    // Vanna API 使用 messages 数组格式
    messages: history.length > 0 ? history : undefined,
    // 传递用户信息
    user_id: userInfo?.userId || 'guest',
    user_nickname: userInfo?.userNickname || userInfo?.userId || 'guest',
  };

  console.log('[Chat] 发送消息:', message);
  console.log('[Chat] 请求payload:', payload);

  let res: Response;
  try {
    // 使用 Vanna 的 SSE 端点
    res = await fetch('/api/vanna/v2/chat_sse', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify(payload),
    });

    console.log('[Chat] 响应状态:', res.status, res.statusText);
    console.log('[Chat] 响应头:', Object.fromEntries(res.headers.entries()));

    if (!res.ok) {
      const errorText = await res.text();
      console.error('[Chat] 请求失败:', res.status, errorText);
      callbacks.onError(new Error(`HTTP ${res.status}: ${errorText}`));
      return;
    }

    const reader = res.body?.getReader();
    if (!reader) {
      console.error('[Chat] 没有响应体');
      callbacks.onError(new Error('No response body'));
      return;
    }

    console.log('[Chat] 开始读取SSE流');

    const decoder = new TextDecoder();
    let fullResponse = '';
    let buffer = '';
    const seenTexts = new Set<string>(); // 用于去重
    let hasReceivedData = false; // 标记是否已收到任何数据

    const readStream = async () => {
      try {
        const { done, value } = await reader.read();
        
        if (done) {
          console.log('[Chat] 流读取完成，总响应长度:', fullResponse.length);
          callbacks.onComplete(fullResponse);
          return;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim()) continue;
          
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6);
            if (dataStr === '[DONE]') {
              console.log('[Chat] 收到完成信号');
              callbacks.onComplete(fullResponse);
              return;
            }
            
            console.log('[Chat] 收到SSE数据:', dataStr.substring(0, 100));
            hasReceivedData = true; // 标记已收到数据

            try {
              const json: SSEMessage = JSON.parse(dataStr);
              callbacks.onSSE(json);

              // Vanna 返回格式: {rich: {...}, simple: {...}}
              const richType = (json as any).rich?.type;
              const simple = (json as any).simple;
              const richData = (json as any).rich?.data;
              
              // 跳过结构化数据类型（这些会通过 onSSE 处理）
              if (richType === 'dataframe' || richType === 'chart') {
                continue;
              }
              
              // 跳过纯状态更新类型（不包含有用文本）
              if (richType === 'status_bar_update' || richType === 'task_tracker_update') {
                continue;
              }
              
              
              // 提取文本 - 优先使用 simple.text（这是最干净的文本）
              let text = '';
              if (simple?.text) {
                text = simple.text;
                console.log('[Chat] 从simple.text提取:', text.substring(0, 50));
                // 尝试从文本中提取 SQL
                if (text && text.includes('SELECT')) {
                  console.log('[Chat] 🔍 simple.text 包含 SELECT，尝试提取 SQL');
                }
              } else if (richData?.content) {
                text = richData.content;
                console.log('[Chat] 从richData.content提取:', text.substring(0, 50));
                // 尝试从文本中提取 SQL
                if (text && text.includes('SELECT')) {
                  console.log('[Chat] 🔍 richData.content 包含 SELECT，尝试提取 SQL');
                }
              } else if ((json as any).display_text) {
                text = (json as any).display_text;
                console.log('[Chat] 从display_text提取:', text.substring(0, 50));
              }
              
              // 检查是否有 tool_calls 在顶层
              if ((json as any).tool_calls) {
                console.log('[Chat] 🔍 发现顶层 tool_calls:', (json as any).tool_calls);
              }
              
              // 对于 status_card、notification 类型，直接跳过（它们包含重复文本）
              if (richType === 'status_card' || richType === 'notification' || richType === 'chat_input_update') {
                continue;
              }
              
              // 过滤明显无用的技术性文本
              if (text && text.trim()) {
                const shouldSkip = 
                  text.trim() === 'Tool completed successfully' ||
                  text.trim() === 'Processing your request...' ||
                  text.includes('Results saved to file:') ||
                  text.includes('FOR VISUALIZE_DATA USE FILENAME') ||
                  text.includes('FOR LARGE RESULTS YOU DO NOT NEED TO SUMMARIZE') ||
                  text.includes('Query executed successfully') ||
                  text.includes('Query executed successfully.');
                
                // 去重：使用文本的前50个字符作为key
                const textKey = text.trim().substring(0, 50);
                
                if (!shouldSkip && text.trim().length > 0 && !seenTexts.has(textKey)) {
                  seenTexts.add(textKey);
                  fullResponse += text + '\n\n';
                  callbacks.onText(text);
                }
              }
            } catch (e) {
              // 非JSON数据，尝试作为纯文本处理
              const trimmed = dataStr.trim();
              if (trimmed && trimmed.length > 0 && !trimmed.startsWith('data:') && trimmed !== '[DONE]') {
                // 可能是纯文本消息
                fullResponse += trimmed + ' ';
                callbacks.onText(trimmed);
              }
            }
          }
        }

        // 递归调用以继续读取流
        readStream();
      } catch (error) {
        // 如果是网络错误（如 ERR_INCOMPLETE_CHUNKED_ENCODING），尝试优雅处理
        const errorMsg = error instanceof Error ? error.message : String(error);
        console.warn('[Chat] SSE流读取错误:', errorMsg, '已收到数据:', hasReceivedData, '响应长度:', fullResponse.length);
        
        // 如果已经收到数据（通过 onSSE 或 onText），即使流中断也当作完成处理
        if (hasReceivedData || fullResponse.trim().length > 0) {
          console.log('[Chat] SSE流中断，但已收到部分数据，使用已收到的数据完成请求');
          // 给一个短暂的延迟，确保所有 onSSE 回调都已处理
          setTimeout(() => {
            callbacks.onComplete(fullResponse);
          }, 100);
          return;
        }
        
        // 如果没有收到任何数据，才调用 onError
        callbacks.onError(error instanceof Error ? error : new Error(String(error)));
      }
    };

    readStream();
  } catch (error) {
    console.error('[Chat] 请求异常:', error);
    const errorMsg = error instanceof Error ? error.message : String(error);
    // 对于网络错误，提供更友好的错误信息
    if (errorMsg.includes('network') || errorMsg.includes('chunked') || errorMsg.includes('incomplete')) {
      callbacks.onError(new Error('网络连接中断，请检查网络后重试'));
    } else {
      callbacks.onError(error instanceof Error ? error : new Error(String(error)));
    }
    return;
  }
}

export function extractSQLFromText(text: string): string | null {
  if (!text) return null;

  // 先过滤掉JSON数据
  let cleanedText = text;
  // 移除JSON对象（以 { 开头到 } 结尾）
  cleanedText = cleanedText.replace(/\{[^{}]*"metadata"[^{}]*\}/g, '');
  cleanedText = cleanedText.replace(/\{[^{}]*"actions"[^{}]*\}/g, '');
  cleanedText = cleanedText.replace(/"[^"]*":\s*\{[^{}]*\}/g, '');
  
  const sqlPatterns = [
    /```sql\s*([\s\S]*?)```/i,
    /```\s*(SELECT[\s\S]*?);?\s*```/i,
    /(SELECT[\s\S]{20,}?);/i,
  ];

  for (const pattern of sqlPatterns) {
    const match = cleanedText.match(pattern);
    if (match && match[1]) {
      let sql = match[1].trim();
      sql = sql.replace(/^```sql\s*/i, '').replace(/```\s*$/i, '').trim();
      // 过滤掉JSON数据，只保留纯SQL
      sql = sql.replace(/["'][^"']*["']:\s*\{[^{}]*\}/g, '');
      sql = sql.replace(/\{.*?\}/g, '');
      sql = sql.replace(/\[.*?\]/g, '');
      sql = sql.split('"}')[0].split('",')[0].split('"}')[0];
      sql = sql.trim();
      
      // 检查是否看起来像SQL（至少包含SELECT和FROM）
      // 过滤掉SHOW、DESCRIBE、PRAGMA等非查询SQL
      const sqlUpper = sql.toUpperCase().trim();
      const isQuerySQL = sqlUpper.startsWith('SELECT') && 
          sqlUpper.includes('FROM') && 
          sql.length > 20 &&
          !sql.includes('"actions"') &&
          !sql.includes('"metadata"') &&
          !sql.includes('"collapsible"') &&
          !sqlUpper.startsWith('SHOW') &&
          !sqlUpper.startsWith('DESCRIBE') &&
          !sqlUpper.startsWith('PRAGMA') &&
          !sqlUpper.startsWith('EXPLAIN');
      
      if (isQuerySQL) {
        return sql;
      }
    }
  }
  return null;
}

// 从CSV文件hash加载查询结果
export async function fetchQueryResult(fileHash: string): Promise<Record<string, unknown>[] | null> {
  try {
    const res = await fetch(`${API_BASE}/chat/query-result/${fileHash}`);
    if (!res.ok) return null;
    const data = await res.json();
    return data.data || null;
  } catch {
    return null;
  }
}

// 获取最新的查询结果
export async function fetchLatestQueryResult(): Promise<Record<string, unknown>[] | null> {
  try {
    const res = await fetch(`${API_BASE}/chat/latest-query-result`);
    if (!res.ok) return null;
    const data = await res.json();
    return data.data || null;
  } catch {
    return null;
  }
}

// 从文件路径中提取hash
export function extractHashFromPath(filePath: string): string | null {
  const match = filePath.match(/([a-f0-9]+)\/query_results_/);
  return match ? match[1] : null;
}

// ==================== 用户反馈 API ====================

// 提交用户评价
export async function submitUserVote(conversationId: string, vote: string): Promise<{ success: boolean }> {
  const res = await fetch(`${API_BASE}/feedback/${conversationId}/vote`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ vote }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// 获取反馈信息
export async function fetchFeedback(conversationId: string): Promise<{ exists: boolean; feedback?: { user_vote?: string } }> {
  try {
    const res = await fetch(`${API_BASE}/feedback/${conversationId}`);
    if (!res.ok) return { exists: false };
    return res.json();
  } catch {
    return { exists: false };
  }
}

// ==================== 会话管理 API ====================

// 创建会话
export async function createConversation(
  conversationId: string, 
  userMessage: string,
  userId?: string,
  userNickname?: string,
): Promise<{ success: boolean; conversation_id: string }> {
  const res = await fetch(`${API_BASE}/chat/conversation/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      conversation_id: conversationId,
      user_id: userId || 'guest',
      user_nickname: userNickname || userId || 'guest',
      summary: userMessage.substring(0, 50),
      user_message: userMessage,
    }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// 获取会话的SQL
export async function getConversationSql(conversationId: string): Promise<{ success: boolean; sql: string | null; source: string }> {
  try {
    const res = await fetch(`${API_BASE}/chat/conversation/${conversationId}/get-sql`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  } catch {
    return { success: false, sql: null, source: 'error' };
  }
}

// 更新会话消息
export async function updateConversationMessage(
  conversationId: string,
  data: {
    content?: string;
    reasoning_steps?: unknown[];
    sql?: string;
    query_analysis?: unknown;
    semantic_tokens?: unknown[];
    selected_tables?: unknown[];
    relevant_knowledge?: unknown[];
    table_data?: Record<string, unknown>[];
    chart_data?: unknown;
  }
): Promise<{ success: boolean }> {
  try {
    const res = await fetch(`${API_BASE}/chat/conversation/${conversationId}/update-message`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  } catch {
    return { success: false };
  }
}

// 更新对话上下文
export async function updateConversationContext(
  conversationId: string,
  question: string,
  sql: string
): Promise<{ success: boolean }> {
  try {
    const res = await fetch(`${API_BASE}/chat/context`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversation_id: conversationId, question, sql }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  } catch {
    return { success: false };
  }
}

// ==================== Memory API ====================

export interface MemoryStats { 
  total_tool_memories: number; 
  successful_tool_memories: number;
  total_text_memories: number;
}
export interface ToolMemory { 
  id: string; 
  question: string; 
  tool_name: string; 
  args: Record<string, unknown>; 
  success: boolean;
  timestamp: string;
  metadata?: Record<string, unknown>;
}
export interface TextMemory { 
  id: string; 
  content: string; 
  timestamp: string; 
}
export interface RAGHighScoreCase { 
  id: string; 
  question: string; 
  sql: string; 
  score: number;
  expert_rating?: number;
  quality_score: number;
  usage_count?: number;
  source?: string;
  created_at: string;
}
export interface RAGStats { 
  total: number;
}

export async function fetchMemoryStats(): Promise<MemoryStats> {
  const res = await fetch(`${API_BASE}/memory/stats`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchRecentToolMemories(limit: number = 20): Promise<ToolMemory[]> {
  const res = await fetch(`${API_BASE}/memory/tools?limit=${limit}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return data.memories || [];
}

export async function fetchRecentTextMemories(limit: number = 20): Promise<TextMemory[]> {
  const res = await fetch(`${API_BASE}/memory/texts?limit=${limit}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return data.memories || [];
}

export async function clearMemories(toolName?: string): Promise<{ success: boolean; deleted_count: number }> {
  const res = await fetch(`${API_BASE}/memory/clear`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tool_name: toolName }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchRAGHighScoreCases(limit: number = 100, minScore: number = 4.0): Promise<RAGHighScoreCase[]> {
  try {
    const res = await fetch(`${API_BASE}/memory/rag-high-score?limit=${limit}&min_score=${minScore}`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.cases || [];
  } catch {
    return [];
  }
}

export async function fetchRAGStats(): Promise<RAGStats | null> {
  try {
    const res = await fetch(`${API_BASE}/memory/rag-stats`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

// ==================== 查询分析 API ====================
// 类型定义已移至 types/index.ts

export async function analyzeQuestion(question: string): Promise<QueryAnalysis | null> {
  try {
    const res = await fetch(`${API_BASE}/analysis/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.success ? data.data : null;
  } catch (e) {
    console.error('[API] 分析问题失败:', e);
    return null;
  }
}

// ==================== Knowledge API ====================

export interface Term {
  id: number;
  keyword: string;
  term_type: string;
  description: string;
  example?: string;
  priority?: number;
  created_at: string;
}

export interface FieldMapping {
  id: number;
  alias: string;
  standard_name: string;
  table_name?: string;
  description?: string;
  created_at: string;
}

export interface TimeRule {
  id: number;
  keyword: string;
  rule_type: string;
  value: string;
  description?: string;
  created_at: string;
}

export async function fetchKnowledgeStats(): Promise<{ terms: number; mappings: number; rules: number } | null> {
  try {
    const res = await fetch(`${API_BASE}/knowledge/stats`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchBusinessTerms(): Promise<Term[]> {
  const res = await fetch(`${API_BASE}/knowledge/terms`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return data.terms || data || [];
}

export async function addBusinessTerm(term: Omit<Term, 'id' | 'created_at'>): Promise<{ success: boolean }> {
  const res = await fetch(`${API_BASE}/knowledge/terms`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(term),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function deleteBusinessTerm(keyword: string): Promise<{ success: boolean }> {
  const res = await fetch(`${API_BASE}/knowledge/terms/${encodeURIComponent(keyword)}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchFieldMappings(): Promise<FieldMapping[]> {
  const res = await fetch(`${API_BASE}/knowledge/mappings`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return data.mappings || data || [];
}

export async function addFieldMapping(mapping: Omit<FieldMapping, 'id' | 'created_at'>): Promise<{ success: boolean }> {
  const res = await fetch(`${API_BASE}/knowledge/mappings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(mapping),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchTimeRules(): Promise<TimeRule[]> {
  const res = await fetch(`${API_BASE}/knowledge/time-rules`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return data.rules || data || [];
}

export async function deleteTimeRule(keyword: string): Promise<{ success: boolean }> {
  const res = await fetch(`${API_BASE}/knowledge/time-rules/${encodeURIComponent(keyword)}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ==================== SQL 编辑器 API ====================

export interface SQLCondition { field: string; operator: string; value: string; }
export interface StructuredSQL { 
  tables: string[]; 
  columns: string[]; 
  conditions: SQLCondition[]; 
  groupBy: string[];
  orderBy: { field: string; direction: string }[];
  limit?: number;
}

export async function parseSQL(sql: string): Promise<StructuredSQL | null> {
  try {
    const res = await fetch(`${API_BASE}/sql/parse`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sql }),
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function rebuildSQL(structured: StructuredSQL): Promise<string | null> {
  try {
    const res = await fetch(`${API_BASE}/sql/rebuild`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(structured),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.sql || null;
  } catch {
    return null;
  }
}

