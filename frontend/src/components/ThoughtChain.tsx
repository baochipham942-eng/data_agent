import React, { useState, useEffect, useRef } from 'react';
import { 
  CheckCircleFilled, 
  LoadingOutlined, 
  ClockCircleOutlined,
  DownOutlined,
  UpOutlined,
} from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import type { ReasoningStep } from '../types';
import { SemanticTokens } from './SemanticTokens';
import './ThoughtChain.css';

interface ThoughtChainProps {
  steps: ReasoningStep[];
  isStreaming?: boolean;
}

export const ThoughtChain: React.FC<ThoughtChainProps> = ({ steps, isStreaming }) => {
  const [expanded, setExpanded] = useState(true);
  const contentRef = useRef<HTMLDivElement>(null);
  
  // 自动滚动到最新步骤
  useEffect(() => {
    if (isStreaming && contentRef.current) {
      const runningStep = contentRef.current.querySelector('.thought-step.running');
      runningStep?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [steps, isStreaming]);
  
  const getStepIcon = (status?: string) => {
    switch (status) {
      case 'done':
        return <CheckCircleFilled className="step-icon done" />;
      case 'running':
        return <LoadingOutlined className="step-icon running" spin />;
      default:
        return <ClockCircleOutlined className="step-icon pending" />;
    }
  };

  // 计算完成进度
  const completedCount = steps.filter(s => s.status === 'done').length;
  const progress = steps.length > 0 ? Math.round((completedCount / steps.length) * 100) : 0;
  
  // 获取当前运行中的步骤
  const currentStep = steps.find(s => s.status === 'running');

  if (!steps || steps.length === 0) return null;

  return (
    <div className={`thought-chain ${isStreaming ? 'streaming' : ''}`}>
      <div 
        className="thought-chain-header"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="header-left">
          <span className="thought-chain-title">🤖 正在为您分析问题</span>
          {isStreaming ? (
            <span className="streaming-badge">
              <span className="streaming-dot"></span>
              {currentStep?.text || '准备开始...'}
            </span>
          ) : (
            <span className="progress-badge">✓ 分析完成</span>
          )}
        </div>
        <button className="expand-btn">
          {expanded ? <UpOutlined /> : <DownOutlined />}
        </button>
      </div>
      
      {expanded && (
        <div className="thought-chain-content" ref={contentRef}>
          {/* 步骤进度条 */}
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
          
          {/* 步骤列表 */}
          <div className="thought-chain-steps">
            {steps.map((step, index) => {
              // 计算当前步骤的显示状态
              const stepIsRunning = step.status === 'running';
              const stepIsPending = step.status === 'pending';
              
              // 只显示已完成的步骤和当前运行中的步骤，隐藏后续的pending步骤
              if (isStreaming) {
                const currentRunningIndex = steps.findIndex(s => s.status === 'running');
                const lastDoneIndex = steps.map((s, i) => s.status === 'done' ? i : -1).filter(i => i >= 0).pop() ?? -1;
                const maxVisibleIndex = currentRunningIndex >= 0 ? currentRunningIndex : lastDoneIndex;
                
                if (stepIsPending && index > maxVisibleIndex) {
                  return null; // 隐藏后续的pending步骤
                }
              }
              
              return (
                <div 
                  key={index} 
                  className={`thought-step ${step.status || 'pending'}`}
                >
                  <div className="step-main">
                    {getStepIcon(step.status)}
                    <span className="step-number">步骤 {step.number}</span>
                    <span className="step-text">{step.text}</span>
                    {step.status === 'done' && (
                      <span className="step-check">✓</span>
                    )}
                  </div>
                  
                  {/* 显示详细思考内容 - 第6步用 markdown 渲染 */}
                  {step.detail && (
                    <div className={`step-detail ${step.number === 6 ? 'analysis-result' : ''}`}>
                      {step.number === 6 ? (
                        <div className="detail-content markdown-content">
                          <ReactMarkdown>{step.detail}</ReactMarkdown>
                        </div>
                      ) : (
                        <div className="detail-content">{step.detail}</div>
                      )}
                    </div>
                  )}
                  
                  {/* 显示语义分词（步骤1的 metadata） */}
                  {step.metadata?.semanticTokens && (step.metadata.semanticTokens as any[]).length > 0 && (
                    <div className="step-tokens">
                      <SemanticTokens
                        question={step.metadata.originalQuestion || step.metadata.rewrittenQuestion || step.detail || ''}
                        tokens={step.metadata.semanticTokens as any[]}
                      />
                    </div>
                  )}
                  
                  {/* 显示表选择（步骤2的 metadata） */}
                  {step.metadata?.selectedTables && (step.metadata.selectedTables as any[]).length > 0 && (
                    <div className="step-tables">
                      {(step.metadata.selectedTables as any[]).map((table: any, i: number) => (
                        <span key={i} className="table-tag" title={table.reason}>
                          📊 {table.name}
                        </span>
                      ))}
                    </div>
                  )}
                  
                  {/* 显示业务知识（步骤3的 metadata） */}
                  {step.metadata?.relevantKnowledge && (step.metadata.relevantKnowledge as any[]).length > 0 && (
                    <div className="step-knowledge">
                      {(step.metadata.relevantKnowledge as any[]).slice(0, 3).map((k: any, i: number) => (
                        <div key={i} className="knowledge-item">
                          <span className="knowledge-keyword">{k.keyword}</span>
                          <span className="knowledge-desc">{k.description}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  
                  {/* 运行中的步骤显示动态光标 */}
                  {stepIsRunning && isStreaming && (
                    <div className="step-thinking">
                      <span className="thinking-text">正在处理中，请稍候</span>
                      <span className="thinking-dots">
                        <span>.</span><span>.</span><span>.</span>
                      </span>
                    </div>
                  )}
                  
                  {/* 初始状态友好提示 */}
                  {stepIsPending && index === 0 && isStreaming && !steps.some(s => s.status === 'running' || s.status === 'done') && (
                    <div className="step-welcome">
                      <span className="welcome-icon">✨</span>
                      <span className="welcome-text">准备开始分析，马上为您呈现结果</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

