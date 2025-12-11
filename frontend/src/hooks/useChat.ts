import { useState, useCallback, useRef } from 'react';
import type { Message, Conversation, SSEMessage, ReasoningStep } from '../types';
import { 
  sendChatMessage, 
  fetchConversation, 
  extractSQLFromText,
  analyzeQuestion,
} from '../utils/api';
import { v4 as uuidv4 } from 'uuid';

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const conversationIdRef = useRef<string | null>(null);

  const addUserMessage = useCallback((content: string) => {
    const message: Message = {
      id: uuidv4(),
      role: 'user',
      content,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, message]);
    return message;
  }, []);

  const addAssistantMessage = useCallback((partial: Partial<Message>) => {
    const message: Message = {
      id: partial.id || uuidv4(),
      role: 'assistant',
      content: partial.content || '',
      timestamp: new Date(),
      isStreaming: true,
      ...partial,
    };
    setMessages(prev => [...prev, message]);
    return message;
  }, []);

  const updateAssistantMessage = useCallback((id: string, updates: Partial<Message>) => {
    setMessages(prev =>
      prev.map(msg =>
        msg.id === id ? { ...msg, ...updates } : msg
      )
    );
  }, []);

  const sendMessage = useCallback(async (content: string, userInfo?: { userId?: string; userNickname?: string }) => {
    if (!content.trim() || isLoading) return;

    setIsLoading(true);
    addUserMessage(content);

    const assistantMsgId = uuidv4();
    
    if (!currentConversationId) {
      conversationIdRef.current = null;
    } else {
      conversationIdRef.current = currentConversationId;
    }
    
    // 初始化推理步骤 - 使用更友好的文案
    const reasoning: ReasoningStep[] = [
      { number: 1, text: '理解您的问题', status: 'pending' },
      { number: 2, text: '生成查询语句', status: 'pending' },
      { number: 3, text: '获取数据结果', status: 'pending' },
      { number: 4, text: '生成分析报告', status: 'pending' },
    ];
    
    addAssistantMessage({ 
      id: assistantMsgId, 
      content: '', 
      isStreaming: true,
      reasoning: [...reasoning],
    });

    const history = messages.map(msg => ({
      role: msg.role,
      content: msg.content,
    }));

    let fullText = '';
    let sql: string | undefined;
    let tableData: Record<string, unknown>[] | undefined;
    let chartData: Message['chartData'] | undefined;

    try {
      // 并行调用分析API（不阻塞）
      analyzeQuestion(content).then(result => {
        if (result) {
          reasoning[0].status = 'done';
          reasoning[0].detail = result.rewritten_question || content;
          if (result.semantic_tokens) {
            reasoning[0].metadata = { 
              semanticTokens: result.semantic_tokens,
              originalQuestion: result.original_question || content,
              rewrittenQuestion: result.rewritten_question,
            };
          }
          updateAssistantMessage(assistantMsgId, { reasoning: [...reasoning] });
        }
      }).catch(() => {
        reasoning[0].status = 'done';
        reasoning[0].detail = content;
        updateAssistantMessage(assistantMsgId, { reasoning: [...reasoning] });
      });

      await sendChatMessage(
        content,
        currentConversationId,
        history,
        {
          onText: (text) => {
            fullText += text + ' ';
            if (reasoning[3]) {
              reasoning[3].status = 'running';
              reasoning[3].detail = fullText.trim();
            }
            updateAssistantMessage(assistantMsgId, {
              content: fullText.trim(),
              reasoning: [...reasoning],
            });
          },
          onSSE: async (data: SSEMessage) => {
            const sseData = data as Record<string, unknown>;
            
            // 更新 conversation_id
            if (sseData.conversation_id) {
              const newConvId = sseData.conversation_id as string;
              if (!currentConversationId) {
                setCurrentConversationId(newConvId);
              }
              conversationIdRef.current = newConvId;
            }

            // 处理 rich 数据
            if (sseData.rich) {
              const rich = sseData.rich as { type: string; data?: Record<string, unknown> };
              const richData = rich.data || {};
              const richType = rich.type;

              // 提取表格数据
              if (richType === 'dataframe' && richData?.data && Array.isArray(richData.data)) {
                tableData = richData.data as Record<string, unknown>[];
                reasoning[2].status = 'done';
                reasoning[2].detail = `获取到 ${tableData.length} 条数据`;
                
                // 从 metadata 提取 SQL
                if (!sql && richData.metadata && typeof richData.metadata === 'object') {
                  const meta = richData.metadata as Record<string, unknown>;
                  if (meta.sql && typeof meta.sql === 'string') {
                    sql = meta.sql;
                  }
                }
              }
              
              // 提取图表数据
              if (richType === 'chart' && richData) {
                chartData = richData as unknown as Message['chartData'];
              }

              // 从 tool_calls 提取 SQL
              if ((sseData as any).tool_calls && Array.isArray((sseData as any).tool_calls)) {
                for (const toolCall of (sseData as any).tool_calls) {
                  if (toolCall.function?.name === 'run_sql' && toolCall.function?.arguments) {
                    try {
                      const args = typeof toolCall.function.arguments === 'string'
                        ? JSON.parse(toolCall.function.arguments)
                        : toolCall.function.arguments;
                      if (args.sql) {
                        sql = args.sql.trim();
                        reasoning[1].status = 'done';
                        reasoning[1].detail = '已生成SQL查询';
                        break;
                      }
                    } catch (e) {
                      // 忽略解析错误
                    }
                  }
                }
              }

              updateAssistantMessage(assistantMsgId, {
                sql: sql || undefined,
                tableData,
                chartData,
                reasoning: [...reasoning],
              });
            }
          },
          onComplete: async (response?: string) => {
            let finalContent = fullText.trim() || response?.trim() || '';
            
            // 提取 SQL
            if (!sql && finalContent) {
              sql = extractSQLFromText(finalContent) || undefined;
            }
            
            // 从后端获取 SQL
            const convIdForSql = conversationIdRef.current || currentConversationId;
            if (!sql && convIdForSql) {
              try {
                const { getConversationSql } = await import('../utils/api');
                const sqlResult = await getConversationSql(convIdForSql);
                if (sqlResult.success && sqlResult.sql) {
                  sql = sqlResult.sql;
                }
              } catch (err) {
                console.warn('获取SQL失败:', err);
              }
            }

            // 完成所有步骤
            reasoning.forEach((step, idx) => {
              step.status = 'done';
              if (idx === 1 && !step.detail) step.detail = sql ? '已生成SQL查询' : '已处理';
              if (idx === 2 && !step.detail) step.detail = tableData ? `获取到 ${tableData.length} 条数据` : '数据获取完成';
              if (idx === 3 && !step.detail) step.detail = finalContent || '分析完成';
            });

            updateAssistantMessage(assistantMsgId, {
              content: finalContent,
              sql: sql || undefined,
              tableData,
              chartData,
              reasoning,
              isStreaming: false,
            });
            
            setIsLoading(false);
          },
          onError: (error) => {
            console.error('Stream error:', error);
            updateAssistantMessage(assistantMsgId, {
              content: '抱歉，发生了错误，请重试。',
              isStreaming: false,
            });
            setIsLoading(false);
          },
        },
        userInfo,
      );
    } catch (error) {
      console.error('Send message error:', error);
      updateAssistantMessage(assistantMsgId, {
        content: '发送消息失败，请检查网络连接后重试。',
        isStreaming: false,
      });
      setIsLoading(false);
    }
  }, [messages, isLoading, currentConversationId, addUserMessage, addAssistantMessage, updateAssistantMessage]);

  const loadConversation = useCallback(async (conv: Conversation) => {
    try {
      const data = await fetchConversation(conv.id);
      setCurrentConversationId(conv.id);
      
      const loadedMessages: Message[] = data.messages.map((msg: any) => {
        let sql = msg.sql;
        if (!sql && msg.content) {
          sql = extractSQLFromText(msg.content) || undefined;
        }
        
        const tableData = msg.table_data || msg.tableData;
        const rawChartData = msg.chart_data || msg.chartData;
        const chartData = rawChartData && typeof rawChartData === 'object' && 'type' in rawChartData 
          ? rawChartData as Message['chartData'] 
          : undefined;
        
        let reasoning = msg.reasoning_steps || msg.reasoning;
        if (!reasoning && msg.role === 'assistant') {
          reasoning = [
            { number: 1, text: '理解问题', status: 'done' as const, detail: '已理解用户意图' },
            { number: 2, text: '生成 SQL 查询', status: sql ? ('done' as const) : ('pending' as const), detail: sql ? '已生成SQL查询' : '未生成SQL' },
            { number: 3, text: '执行查询获取数据', status: tableData ? ('done' as const) : ('pending' as const), detail: tableData ? `获取到 ${tableData.length} 条数据` : '未获取数据' },
            { number: 4, text: '生成分析结果', status: 'done' as const, detail: msg.content || '分析完成' },
          ];
        }
        
        return {
          id: uuidv4(),
          role: msg.role,
          content: msg.content || '',
          timestamp: new Date(msg.created_at || Date.now()),
          sql,
          tableData,
          chartData,
          reasoning,
          isStreaming: false,
        };
      });
      
      setMessages(loadedMessages);
    } catch (error) {
      console.error('Load conversation error:', error);
    }
  }, []);

  const startNewChat = useCallback(() => {
    setMessages([]);
    setCurrentConversationId(null);
  }, []);

  return {
    messages,
    isLoading,
    currentConversationId,
    sendMessage,
    loadConversation,
    startNewChat,
    stopGeneration: () => setIsLoading(false),
  };
}
