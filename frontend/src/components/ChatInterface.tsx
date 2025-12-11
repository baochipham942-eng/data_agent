import React, { useRef, useEffect } from 'react';
import { Bubble, Sender } from '@ant-design/x';
import { Avatar } from 'antd';
import { 
  UserOutlined, 
  RobotOutlined,
  LineChartOutlined,
  PieChartOutlined,
  TableOutlined,
} from '@ant-design/icons';
import type { Message } from '../types';
import { ThoughtChain } from './ThoughtChain';
import { DataTable } from './DataTable';
import { DataChart } from './DataChart';
import { AutoChart } from './AutoChart';
import { SqlBlock } from './SqlBlock';
import { WelcomeScreen } from './WelcomeScreen';
import { MessageActions } from './MessageActions';
import './ChatInterface.css';

interface ChatInterfaceProps {
  messages: Message[];
  isLoading: boolean;
  onSendMessage: (content: string) => void;
  onExampleClick: (question: string) => void;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({
  messages,
  isLoading,
  onSendMessage,
  onExampleClick,
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [inputValue, setInputValue] = React.useState('');

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    if (inputValue.trim() && !isLoading) {
      onSendMessage(inputValue.trim());
      setInputValue('');
    }
  };

  const renderMessageContent = (msg: Message) => {
    // 用户消息直接显示内容
    if (msg.role === 'user') {
      return (
        <div className="message-wrapper">
          <div className="message-text">{msg.content}</div>
        </div>
      );
    }
    
    // 助手消息展示完整内容
    return (
      <div className="message-wrapper">
        {/* 思维链展示 - 处理过程 */}
        {msg.reasoning && msg.reasoning.length > 0 && (
          <ThoughtChain 
            steps={msg.reasoning} 
            isStreaming={msg.isStreaming}
          />
        )}
        
        {/* SQL代码块 - 只在消息完成流式输出后显示，避免SQL频繁变化 */}
        {!msg.isStreaming && msg.sql && <SqlBlock sql={msg.sql} />}
        
        {/* 数据表格 - 只在消息完成流式输出后显示 */}
        {!msg.isStreaming && msg.tableData && msg.tableData.length > 0 && (
          <DataTable key={`table-${msg.id}`} data={msg.tableData} />
        )}
        
        {/* 图表 - 优先使用表格数据自动生成图表，确保只渲染一次 */}
        {!msg.isStreaming && msg.tableData && msg.tableData.length > 0 && msg.tableData.length <= 50 ? (
          <AutoChart 
            key={`auto-chart-${msg.id}`} 
            data={msg.tableData}
            title={msg.chartData?.title || undefined}
          />
        ) : !msg.isStreaming && msg.chartData && msg.chartData.data && Array.isArray(msg.chartData.data) && msg.chartData.data.length > 0 && (!msg.tableData || msg.tableData.length === 0) ? (
          <DataChart key={`chart-${msg.id}`} data={msg.chartData} />
        ) : null}
        
        {/* 消息操作按钮 */}
        {!msg.isStreaming && (
          <MessageActions 
            content={msg.content} 
            sql={msg.sql} 
            messageId={msg.id} 
          />
        )}
      </div>
    );
  };

  const renderAvatar = (role: 'user' | 'assistant') => {
    if (role === 'user') {
      return (
        <Avatar 
          icon={<UserOutlined />} 
          style={{ 
            background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
            color: 'white',
          }} 
        />
      );
    }
    return (
      <Avatar 
        icon={<RobotOutlined />} 
        style={{ 
          background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)',
          color: 'white',
        }} 
      />
    );
  };

  return (
    <div className="chat-interface">
      <div className="messages-container">
        {messages.length === 0 ? (
          <WelcomeScreen onExampleClick={onExampleClick} />
        ) : (
          <div className="messages-list">
            {messages.map((msg) => (
              <div 
                key={msg.id} 
                className={`message-row ${msg.role}`}
              >
                <Bubble
                  placement={msg.role === 'user' ? 'end' : 'start'}
                  content={renderMessageContent(msg)}
                  avatar={renderAvatar(msg.role)}
                  loading={msg.isStreaming && !msg.content}
                  className={`bubble-${msg.role}`}
                  styles={{
                    content: {
                      background: msg.role === 'user' 
                        ? 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)'
                        : 'var(--color-assistant-bubble)',
                      color: 'var(--color-text-primary)',
                      borderRadius: 'var(--radius-lg)',
                      padding: '16px 24px',
                      maxWidth: msg.role === 'user' ? '500px' : '850px',
                      minWidth: msg.role === 'assistant' ? '400px' : 'auto',
                      border: msg.role === 'user' 
                        ? 'none' 
                        : '1px solid rgba(255, 255, 255, 0.08)',
                    },
                  }}
                />
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      <div className="input-container">
        <div className="input-wrapper">
          <Sender
            value={inputValue}
            onChange={setInputValue}
            onSubmit={handleSend}
            loading={isLoading}
            placeholder="输入您的问题，例如：最近7天的访问趋势是什么？"
            className="chat-sender"
            style={{
              background: 'var(--color-bg-tertiary)',
              borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--color-surface-border)',
            }}
          />
          <div className="input-hints">
            <span className="hint-item">
              <LineChartOutlined /> 趋势分析
            </span>
            <span className="hint-item">
              <PieChartOutlined /> 占比统计
            </span>
            <span className="hint-item">
              <TableOutlined /> 数据查询
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

