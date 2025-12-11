/**
 * 推理步骤工具函数
 * 
 * 用于过滤和整理推理步骤，只显示实际有内容的步骤
 */

import type { ReasoningStep } from '../types';

/**
 * 判断步骤是否有实际内容（应该显示）
 */
export function hasStepContent(step: ReasoningStep, allData: {
  sql?: string;
  tableData?: Record<string, any>[];
  content?: string;
}): boolean {
  const { stepType, detail, metadata } = step;
  
  // 如果步骤有详细的detail内容，应该显示
  if (detail && detail.trim() && detail !== '分析完成' && detail.length > 5) {
    return true;
  }
  
  // 根据步骤类型判断
  switch (stepType) {
    case 'rewrite':
      // 理解问题步骤：有语义分词或改写后问题才显示
      if (metadata?.semanticTokens && metadata.semanticTokens.length > 0) {
        return true;
      }
      if (metadata?.rewrittenQuestion && metadata.rewrittenQuestion.trim()) {
        return true;
      }
      return false;
    
    case 'tables':
      // 表选择步骤：有选择的表才显示
      if (metadata?.selectedTables && metadata.selectedTables.length > 0) {
        return true;
      }
      return false;
    
    case 'knowledge':
      // 业务知识步骤：有参考的知识才显示
      if (metadata?.relevantKnowledge && metadata.relevantKnowledge.length > 0) {
        return true;
      }
      return false;
    
    case 'sql':
      // SQL生成步骤：有SQL才显示
      if (allData.sql && allData.sql.trim()) {
        return true;
      }
      return false;
    
    case 'execute':
      // 执行查询步骤：有数据才显示
      if (allData.tableData && allData.tableData.length > 0) {
        return true;
      }
      return false;
    
    case 'analyze':
      // 分析结果步骤：有内容才显示
      if (allData.content && allData.content.trim()) {
        return true;
      }
      return false;
    
    default:
      // 默认：如果有detail就显示
      return !!(detail && detail.trim());
  }
}

/**
 * 过滤推理步骤，只保留有实际内容的步骤
 * 并重新编号
 */
export function filterAndRenumberSteps(
  steps: ReasoningStep[],
  allData: {
    sql?: string;
    tableData?: Record<string, any>[];
    content?: string;
  }
): ReasoningStep[] {
  if (!steps || steps.length === 0) {
    return [];
  }
  
  // 过滤掉没有内容的步骤
  const filteredSteps = steps.filter(step => hasStepContent(step, allData));
  
  // 重新编号
  return filteredSteps.map((step, index) => ({
    ...step,
    number: index + 1,
  }));
}

/**
 * 智能构建推理步骤
 * 根据实际数据动态生成步骤，而不是固定6步
 */
export function buildReasoningSteps(data: {
  rewrittenQuestion?: string;
  semanticTokens?: any[];
  selectedTables?: any[];
  relevantKnowledge?: any[];
  sql?: string;
  tableData?: Record<string, any>[];
  content?: string;
}): ReasoningStep[] {
  const steps: ReasoningStep[] = [];
  
  // 步骤1: 理解问题（如果有语义分词或改写）
  if (data.semanticTokens && data.semanticTokens.length > 0) {
    steps.push({
      number: steps.length + 1,
      text: '理解您的问题',
      status: 'done',
      stepType: 'rewrite',
      detail: data.rewrittenQuestion || '已理解您的意图',
      metadata: {
        rewrittenQuestion: data.rewrittenQuestion,
        semanticTokens: data.semanticTokens,
      },
    });
  }
  
  // 步骤2: 选择数据表（如果有选择的表）
  if (data.selectedTables && data.selectedTables.length > 0) {
    const tableNames = data.selectedTables.map(t => t.name).join('、');
    steps.push({
      number: steps.length + 1,
      text: '选择相关数据表',
      status: 'done',
      stepType: 'tables',
      detail: `已选择：${tableNames}`,
      metadata: {
        selectedTables: data.selectedTables,
      },
    });
  }
  
  // 步骤3: 参考业务知识（如果有相关知识）
  if (data.relevantKnowledge && data.relevantKnowledge.length > 0) {
    steps.push({
      number: steps.length + 1,
      text: '参考业务知识',
      status: 'done',
      stepType: 'knowledge',
      detail: `已参考 ${data.relevantKnowledge.length} 条业务知识`,
      metadata: {
        relevantKnowledge: data.relevantKnowledge,
      },
    });
  }
  
  // 步骤4: 生成SQL查询（如果有SQL）
  if (data.sql && data.sql.trim()) {
    steps.push({
      number: steps.length + 1,
      text: '生成查询语句',
      status: 'done',
      stepType: 'sql',
      detail: '查询语句已生成',
    });
  }
  
  // 步骤5: 执行查询获取数据（如果有数据）
  if (data.tableData && data.tableData.length > 0) {
    steps.push({
      number: steps.length + 1,
      text: '获取数据结果',
      status: 'done',
      stepType: 'execute',
      detail: `成功获取 ${data.tableData.length} 条数据`,
      metadata: {
        selectedTables: data.selectedTables,
      },
    });
  }
  
  // 步骤6: 生成分析结果（如果有内容）
  if (data.content && data.content.trim()) {
    steps.push({
      number: steps.length + 1,
      text: '生成分析报告',
      status: 'done',
      stepType: 'analyze',
      detail: data.content,
    });
  }
  
  return steps;
}




