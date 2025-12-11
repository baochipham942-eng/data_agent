/**
 * 语义分词可视化组件
 * 
 * 展示用户问题的语义拆解结果，类似喜马拉雅的"问数语义拆解"效果：
 * 
 * ┌──────────┬──────────┬──────────┬───────────────┬─────────────┐
 * │   本周   │ 小说频道  │   专辑   │ DAU趋势如何？ │    环比？    │
 * └────┬─────┴────┬─────┴────┬─────┴───────┬───────┴──────┬──────┘
 *      ↓          ↓          ↓             ↓              ↓
 *  时间语义规则  字段枚举   企业词汇    自动图表展示   同环比语义规则
 */

import React from 'react';
import { Tooltip, Tag } from 'antd';
import {
  ClockCircleOutlined,
  FieldTimeOutlined,
  BookOutlined,
  BarChartOutlined,
  SwapOutlined,
  DashboardOutlined,
  TableOutlined,
  AppstoreOutlined,
  SortAscendingOutlined,
} from '@ant-design/icons';
import './SemanticTokens.css';

export interface SemanticToken {
  text: string;
  type: 'time_rule' | 'comparison' | 'term' | 'field_mapping' | 'chart_hint' | 'metric' | 'dimension' | 'sort' | 'plain';
  type_label: string;
  start: number;
  end: number;
  knowledge?: {
    description: string;
    value?: string;
  };
}

interface SemanticTokensProps {
  question: string;
  tokens: SemanticToken[];
}

// 类型到颜色的映射
const TYPE_COLORS: Record<string, string> = {
  time_rule: '#ff7a45',      // 橙色
  comparison: '#9254de',     // 紫色
  term: '#fadb14',           // 黄色
  field_mapping: '#13c2c2',  // 青色
  chart_hint: '#52c41a',     // 绿色
  metric: '#1890ff',         // 蓝色
  dimension: '#eb2f96',      // 粉色（新增维度）
  sort: '#fa8c16',           // 橙红色（排序）
  plain: '#8c8c8c',          // 灰色
};

// 类型到图标的映射
const TYPE_ICONS: Record<string, React.ReactNode> = {
  time_rule: <ClockCircleOutlined />,
  comparison: <SwapOutlined />,
  term: <BookOutlined />,
  field_mapping: <TableOutlined />,
  chart_hint: <BarChartOutlined />,
  metric: <DashboardOutlined />,
  dimension: <AppstoreOutlined />,
  sort: <SortAscendingOutlined />,
  plain: <FieldTimeOutlined />,
};

export const SemanticTokens: React.FC<SemanticTokensProps> = ({ question, tokens }) => {
  if (!tokens || tokens.length === 0) {
    return null;
  }

  // 构建完整的分词视图，包含未匹配的文本
  const buildTokenizedView = () => {
    const result: Array<{
      text: string;
      token?: SemanticToken;
      isMatched: boolean;
    }> = [];
    
    let lastEnd = 0;
    
    // 按位置排序
    const sortedTokens = [...tokens].sort((a, b) => a.start - b.start);
    
    for (const token of sortedTokens) {
      // 添加未匹配的文本
      if (token.start > lastEnd) {
        const plainText = question.slice(lastEnd, token.start);
        if (plainText.trim()) {
          result.push({
            text: plainText,
            isMatched: false,
          });
        }
      }
      
      // 添加匹配的token
      result.push({
        text: token.text,
        token,
        isMatched: true,
      });
      
      lastEnd = token.end;
    }
    
    // 添加剩余的文本
    if (lastEnd < question.length) {
      const plainText = question.slice(lastEnd);
      if (plainText.trim()) {
        result.push({
          text: plainText,
          isMatched: false,
        });
      }
    }
    
    return result;
  };

  const tokenizedView = buildTokenizedView();

  return (
    <div className="semantic-tokens">
      <div className="tokens-label">语义拆解</div>
      
      {/* 问题文本分词展示 */}
      <div className="tokens-question">
        {tokenizedView.map((item, index) => (
          <div key={index} className={`token-item ${item.isMatched ? 'matched' : 'plain'}`}>
            {/* 上方：文本块 */}
            <div 
              className="token-text"
              style={{
                borderColor: item.token ? TYPE_COLORS[item.token.type] : '#444',
                backgroundColor: item.token 
                  ? `${TYPE_COLORS[item.token.type]}15` 
                  : 'transparent',
              }}
            >
              {item.isMatched && item.token ? (
                <Tooltip
                  title={
                    <div className="token-tooltip">
                      <div className="tooltip-header">
                        {TYPE_ICONS[item.token.type]}
                        <span>{item.token.type_label}</span>
                      </div>
                      {item.token.knowledge && (
                        <>
                          <div className="tooltip-desc">
                            {item.token.knowledge.description}
                          </div>
                          {item.token.knowledge.value && (
                            <div className="tooltip-value">
                              → {item.token.knowledge.value}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  }
                  placement="top"
                  overlayClassName="semantic-token-tooltip"
                >
                  <span className="token-content">{item.text}</span>
                </Tooltip>
              ) : (
                <span className="token-content plain-text">{item.text}</span>
              )}
            </div>
            
            {/* 下方：连接线和标签 */}
            {item.isMatched && item.token && (
              <div className="token-connector">
                <div 
                  className="connector-line"
                  style={{ borderColor: TYPE_COLORS[item.token.type] }}
                />
                <div 
                  className="connector-arrow"
                  style={{ borderTopColor: TYPE_COLORS[item.token.type] }}
                />
                <Tag 
                  className="token-type-tag"
                  style={{ 
                    backgroundColor: `${TYPE_COLORS[item.token.type]}20`,
                    borderColor: TYPE_COLORS[item.token.type],
                    color: TYPE_COLORS[item.token.type],
                  }}
                  icon={TYPE_ICONS[item.token.type]}
                >
                  {item.token.type_label}
                </Tag>
              </div>
            )}
          </div>
        ))}
      </div>
      
      {/* 统计信息 */}
      <div className="tokens-summary">
        {tokens.length > 0 && (
          <span className="summary-text">
            识别到 <strong>{tokens.length}</strong> 个语义块
          </span>
        )}
      </div>
    </div>
  );
};

export default SemanticTokens;

