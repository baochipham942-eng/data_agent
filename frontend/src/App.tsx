import React, { useState, useEffect, useRef } from 'react';
import { Sidebar } from './components/Sidebar';
import { ChatInterface } from './components/ChatInterface';
import { EvaluatePage } from './components/EvaluatePage';
import { MemoryPage } from './components/MemoryPage';
import KnowledgePage from './components/KnowledgePage';
import PromptPage from './components/PromptPage';
import DatabasePage from './components/DatabasePage';
import TestingPage from './components/TestingPage';
import { LoginModal, loadUserInfo, type UserInfo } from './components/LoginModal';
import { useChat } from './hooks/useChat';
import './App.css';

type PageView = 'chat' | 'evaluate' | 'memory' | 'knowledge' | 'prompt' | 'database' | 'testing';

const App: React.FC = () => {
  const [currentPage, setCurrentPage] = useState<PageView>('chat');
  const [currentUser, setCurrentUser] = useState<UserInfo | null>(null);
  const [showLoginModal, setShowLoginModal] = useState(false);
  
  const {
    messages,
    isLoading,
    currentConversationId,
    sendMessage,
    loadConversation,
    startNewChat,
  } = useChat();
  
  // 【关键修复】监听会话ID变化，如果变为null且有消息，强制清空
  const prevConversationIdRef = useRef<string | null>(currentConversationId);
  useEffect(() => {
    // 如果会话ID从有值变为null，说明会话被删除了，强制重置
    if (prevConversationIdRef.current && !currentConversationId && messages.length > 0) {
      console.log('[App] 检测到会话ID从有值变为null，强制重置消息');
      startNewChat();
    }
    prevConversationIdRef.current = currentConversationId;
  }, [currentConversationId, messages.length, startNewChat]);

  // 检查登录状态
  useEffect(() => {
    const user = loadUserInfo();
    if (user) {
      setCurrentUser(user);
    } else {
      setShowLoginModal(true);
    }
  }, []);

  // 包装 sendMessage 以传递用户信息
  const handleSendMessage = (content: string) => {
    sendMessage(content, currentUser ? {
      userId: currentUser.id,
      userNickname: currentUser.nickname,
    } : undefined);
  };

  // 处理登录
  const handleLogin = (user: UserInfo) => {
    setCurrentUser(user);
    setShowLoginModal(false);
  };

  const handleOpenEvaluate = () => {
    setCurrentPage('evaluate');
  };

  const handleOpenMemory = () => {
    setCurrentPage('memory');
  };

  const handleOpenKnowledge = () => {
    setCurrentPage('knowledge');
  };

  const handleOpenPrompt = () => {
    setCurrentPage('prompt');
  };

  const handleOpenDatabase = () => {
    setCurrentPage('database');
  };

  const handleOpenTesting = () => {
    setCurrentPage('testing');
  };

  const handleBackToChat = () => {
    setCurrentPage('chat');
  };

  if (currentPage === 'evaluate') {
    return (
      <div className="app-container full-width">
        <EvaluatePage 
          onBack={handleBackToChat} 
          currentConversationId={currentConversationId}
          onNewChat={startNewChat}
        />
      </div>
    );
  }

  if (currentPage === 'memory') {
    return (
      <div className="app-container full-width">
        <MemoryPage onBack={handleBackToChat} />
      </div>
    );
  }

  if (currentPage === 'knowledge') {
    return (
      <div className="app-container full-width">
        <KnowledgePage onBack={handleBackToChat} />
      </div>
    );
  }

  if (currentPage === 'prompt') {
    return (
      <div className="app-container full-width">
        <PromptPage onBack={handleBackToChat} />
      </div>
    );
  }

  if (currentPage === 'database') {
    return (
      <div className="app-container full-width">
        <DatabasePage onBack={handleBackToChat} />
      </div>
    );
  }

  if (currentPage === 'testing') {
    return (
      <div className="app-container full-width">
        <TestingPage onBack={handleBackToChat} />
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* 登录弹窗 */}
      <LoginModal
        visible={showLoginModal}
        onLogin={handleLogin}
      />
      
      <Sidebar
        onNewChat={startNewChat}
        onSelectConversation={loadConversation}
        currentConversationId={currentConversationId}
        onOpenEvaluate={handleOpenEvaluate}
        onOpenMemory={handleOpenMemory}
        onOpenKnowledge={handleOpenKnowledge}
        onOpenPrompt={handleOpenPrompt}
        onOpenDatabase={handleOpenDatabase}
        onOpenTesting={handleOpenTesting}
        currentUser={currentUser}
        onLogout={() => setShowLoginModal(true)}
      />
      <ChatInterface
        key={currentConversationId || 'new-chat'}
        messages={messages}
        isLoading={isLoading}
        onSendMessage={handleSendMessage}
        onExampleClick={handleSendMessage}
        conversationId={currentConversationId}
      />
    </div>
  );
};

export default App;
