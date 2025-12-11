import React, { useEffect, useState, useCallback } from 'react';
import { 
  MessageOutlined, 
  PlusOutlined, 
  DeleteOutlined,
  HistoryOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { Button, Tooltip, Popconfirm, message } from 'antd';
import type { Conversation } from '../types';
import type { UserInfo } from './LoginModal';
import { fetchConversations, deleteConversation } from '../utils/api';
import { SettingsMenu } from './SettingsMenu';
import './Sidebar.css';

interface SidebarProps {
  onNewChat: () => void;
  onSelectConversation: (conv: Conversation) => void;
  currentConversationId: string | null;
  onOpenEvaluate?: () => void;
  onOpenMemory?: () => void;
  onOpenKnowledge?: () => void;
  onOpenPrompt?: () => void;
  onOpenDatabase?: () => void;
  onOpenTesting?: () => void;
  currentUser?: UserInfo | null;
  onLogout?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  onNewChat,
  onSelectConversation,
  currentConversationId,
  onOpenEvaluate,
  onOpenMemory,
  onOpenKnowledge,
  onOpenPrompt,
  onOpenDatabase,
  onOpenTesting,
  currentUser,
  onLogout,
}) => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(false);

  // 静默刷新：不显示loading状态
  const silentRefresh = useCallback(async () => {
    try {
      const data = await fetchConversations();
      setConversations(data);
    } catch (error) {
      console.error('Failed to refresh conversations:', error);
    }
  }, []);

  // 带loading状态的刷新（用于手动刷新）
  const loadConversations = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchConversations();
      setConversations(data);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  // 当currentConversationId变化时，静默刷新列表（新会话创建时）
  useEffect(() => {
    if (currentConversationId) {
      // 延迟一点刷新，确保后端已经保存了新会话
      const timer = setTimeout(() => {
        silentRefresh();
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [currentConversationId, silentRefresh]);

  const handleRefresh = () => {
    loadConversations();
    message.success('已刷新');
  };

  const handleDelete = async (convId: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    try {
      await deleteConversation(convId);
      setConversations(prev => prev.filter(c => c.id !== convId));
      message.success('对话已删除');
    } catch (error) {
      console.error('Failed to delete conversation:', error);
      message.error('删除失败');
    }
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="logo">
          <div className="logo-icon">
            <MessageOutlined />
          </div>
          <div className="logo-text">
            <span className="logo-title">Data Agent</span>
            <span className="logo-subtitle">智能数据分析助手</span>
          </div>
        </div>
        
        <Button 
          type="primary" 
          icon={<PlusOutlined />} 
          className="new-chat-btn"
          onClick={onNewChat}
        >
          新对话
        </Button>
      </div>

      <div className="sidebar-section">
        <div className="section-title">
          <HistoryOutlined />
          <span>历史对话</span>
          <Tooltip title="刷新列表">
            <button className="refresh-btn" onClick={handleRefresh}>
              <ReloadOutlined spin={loading} />
            </button>
          </Tooltip>
        </div>
        
        <div className="conversation-list">
          {loading ? (
            <div className="loading-placeholder">加载中...</div>
          ) : conversations.length === 0 ? (
            <div className="empty-placeholder">暂无历史对话</div>
          ) : (
            conversations.map((conv) => (
              <div
                key={conv.id}
                className={`conversation-item ${currentConversationId === conv.id ? 'active' : ''}`}
                onClick={() => onSelectConversation(conv)}
              >
                <div className="conversation-icon">
                  <MessageOutlined />
                </div>
                <div className="conversation-content">
                  <div className="conversation-title">{conv.summary}</div>
                  <div className="conversation-time">{conv.time}</div>
                </div>
                <Popconfirm
                  title="确定删除这个对话吗？"
                  onConfirm={(e) => handleDelete(conv.id, e as React.MouseEvent)}
                  okText="删除"
                  cancelText="取消"
                  placement="right"
                >
                  <Tooltip title="删除">
                    <button 
                      className="delete-btn"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <DeleteOutlined />
                    </button>
                  </Tooltip>
                </Popconfirm>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="sidebar-footer">
        <SettingsMenu 
          onOpenEvaluate={onOpenEvaluate}
          onOpenMemory={onOpenMemory}
          onOpenKnowledge={onOpenKnowledge}
          onOpenPrompt={onOpenPrompt}
          onOpenDatabase={onOpenDatabase}
          onOpenTesting={onOpenTesting}
          currentUser={currentUser}
          onLogout={onLogout}
        />
      </div>
    </aside>
  );
};

