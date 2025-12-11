import React, { useState, useEffect } from 'react';
import { Tooltip, message } from 'antd';
import { 
  LikeOutlined, 
  LikeFilled,
  DislikeOutlined, 
  DislikeFilled,
  CopyOutlined,
  CheckOutlined,
  MailOutlined,
} from '@ant-design/icons';
import { submitUserVote, fetchFeedback } from '../utils/api';
import './MessageActions.css';

interface MessageActionsProps {
  content: string;
  sql?: string;
  messageId: string;
  conversationId?: string;  // 会话ID，用于提交评价
  userQuestion?: string;    // 用户问题，用于联系专家
}

export const MessageActions: React.FC<MessageActionsProps> = ({ 
  content, 
  sql, 
  conversationId,
  userQuestion,
}) => {
  const [liked, setLiked] = useState(false);
  const [disliked, setDisliked] = useState(false);
  const [copied, setCopied] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // 加载已有的用户评价
  useEffect(() => {
    if (conversationId) {
      fetchFeedback(conversationId).then(result => {
        if (result.exists && result.feedback?.user_vote) {
          setLiked(result.feedback.user_vote === 'like');
          setDisliked(result.feedback.user_vote === 'dislike');
        }
      }).catch(() => {
        // 忽略加载错误
      });
    }
  }, [conversationId]);

  const handleLike = async () => {
    if (!conversationId) {
      message.warning('无法提交评价');
      return;
    }
    
    setSubmitting(true);
    try {
      const newVote = liked ? 'none' : 'like';
      await submitUserVote(conversationId, newVote);
      
      if (liked) {
        setLiked(false);
        message.info('已取消点赞');
      } else {
        setLiked(true);
        setDisliked(false);
        message.success('感谢您的反馈！');
      }
    } catch (error) {
      console.error('Submit vote error:', error);
      message.error('提交失败，请重试');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDislike = async () => {
    if (!conversationId) {
      message.warning('无法提交评价');
      return;
    }
    
    setSubmitting(true);
    try {
      const newVote = disliked ? 'none' : 'dislike';
      await submitUserVote(conversationId, newVote);
      
      if (disliked) {
        setDisliked(false);
        message.info('已取消点踩');
      } else {
        setDisliked(true);
        setLiked(false);
        message.success('感谢您的反馈，我们会持续改进！');
      }
    } catch (error) {
      console.error('Submit vote error:', error);
      message.error('提交失败，请重试');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCopy = async () => {
    try {
      let textToCopy = content;
      if (sql) {
        textToCopy += '\n\nSQL查询:\n' + sql;
      }
      await navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      message.success('已复制到剪贴板');
      setTimeout(() => setCopied(false), 2000);
    } catch {
      message.error('复制失败');
    }
  };

  const handleCopySessionId = async () => {
    if (conversationId) {
      await navigator.clipboard.writeText(conversationId);
      message.success('会话ID已复制');
    }
  };

  const handleContactExpert = () => {
    const recipient = 'leolin@wicrenet.com';
    const subject = encodeURIComponent(`[Data Agent 咨询] 数据分析问题反馈`);
    
    // 构建邮件正文
    const currentTime = new Date().toLocaleString('zh-CN');
    let body = `您好，专家团队：\n\n`;
    body += `我在使用 Data Agent 时遇到了问题，希望获得专业指导。\n\n`;
    body += `━━━━━━━━━━━━━━━━━━━━━━\n`;
    body += `📋 问题详情\n`;
    body += `━━━━━━━━━━━━━━━━━━━━━━\n\n`;
    body += `🔹 会话ID：${conversationId || '未知'}\n\n`;
    body += `🔹 用户问题：${userQuestion || '（未提供）'}\n\n`;
    if (sql) {
      body += `🔹 生成的SQL：\n${sql}\n\n`;
    }
    body += `🔹 AI回复摘要：\n${content?.slice(0, 200) || '（无）'}${content && content.length > 200 ? '...' : ''}\n\n`;
    body += `━━━━━━━━━━━━━━━━━━━━━━\n`;
    body += `📝 我的问题描述\n`;
    body += `━━━━━━━━━━━━━━━━━━━━━━\n\n`;
    body += `（请在此描述您遇到的具体问题或需要的帮助）\n\n\n\n`;
    body += `━━━━━━━━━━━━━━━━━━━━━━\n`;
    body += `⏰ 反馈时间：${currentTime}\n`;
    body += `━━━━━━━━━━━━━━━━━━━━━━\n`;
    
    const mailtoUrl = `mailto:${recipient}?subject=${subject}&body=${encodeURIComponent(body)}`;
    window.open(mailtoUrl, '_self');
  };

  return (
    <div className="message-actions">
      <div className="actions-left">
        <Tooltip title={liked ? '取消点赞' : '有帮助'}>
          <button 
            className={`action-btn ${liked ? 'active like' : ''}`}
            onClick={handleLike}
            disabled={submitting}
          >
            {liked ? <LikeFilled /> : <LikeOutlined />}
          </button>
        </Tooltip>
        
        <Tooltip title={disliked ? '取消点踩' : '没有帮助'}>
          <button 
            className={`action-btn ${disliked ? 'active dislike' : ''}`}
            onClick={handleDislike}
            disabled={submitting}
          >
            {disliked ? <DislikeFilled /> : <DislikeOutlined />}
          </button>
        </Tooltip>
        
        <Tooltip title="复制内容">
          <button 
            className={`action-btn ${copied ? 'active copy' : ''}`}
            onClick={handleCopy}
          >
            {copied ? <CheckOutlined /> : <CopyOutlined />}
          </button>
        </Tooltip>
        
        <Tooltip title="联系专家获取帮助">
          <button 
            className="action-btn contact-expert"
            onClick={handleContactExpert}
          >
            <MailOutlined />
          </button>
        </Tooltip>
      </div>
      
      {conversationId && (
        <Tooltip title="点击复制完整会话ID">
          <button 
            className="session-id-btn"
            onClick={handleCopySessionId}
          >
            会话ID: {conversationId.slice(0, 8)}...
          </button>
        </Tooltip>
      )}
    </div>
  );
};

