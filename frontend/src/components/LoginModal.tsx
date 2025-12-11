import React, { useState } from 'react';
import { Modal, Input, Button, message, Avatar } from 'antd';
import { UserOutlined, SmileOutlined } from '@ant-design/icons';
import './LoginModal.css';

// 预设头像颜色
const AVATAR_COLORS = [
  '#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1',
  '#13c2c2', '#eb2f96', '#fa8c16', '#a0d911', '#2f54eb',
];

export interface UserInfo {
  id: string;  // 用户唯一标识（使用昵称作为 ID）
  nickname: string;
  avatarColor: string;
  createdAt: string;
}

const USER_STORAGE_KEY = 'vanna_user_info';

export function loadUserInfo(): UserInfo | null {
  try {
    const saved = localStorage.getItem(USER_STORAGE_KEY);
    if (saved) {
      const user = JSON.parse(saved);
      // 兼容旧数据：如果没有 id 字段，根据 nickname 生成
      if (!user.id && user.nickname) {
        user.id = user.nickname.toLowerCase().replace(/\s+/g, '_');
        // 保存更新后的数据
        saveUserInfo(user);
      }
      return user;
    }
  } catch {
    // ignore
  }
  return null;
}

export function saveUserInfo(user: UserInfo): void {
  localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
}

export function clearUserInfo(): void {
  localStorage.removeItem(USER_STORAGE_KEY);
}

interface LoginModalProps {
  visible: boolean;
  onLogin: (user: UserInfo) => void;
}

export const LoginModal: React.FC<LoginModalProps> = ({ visible, onLogin }) => {
  const [nickname, setNickname] = useState('');
  const [selectedColor, setSelectedColor] = useState(AVATAR_COLORS[0]);
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    const trimmedNickname = nickname.trim();
    
    if (!trimmedNickname) {
      message.warning('请输入昵称');
      return;
    }
    
    if (trimmedNickname.length > 20) {
      message.warning('昵称不能超过20个字符');
      return;
    }
    
    setLoading(true);
    
    // 模拟登录过程
    await new Promise(resolve => setTimeout(resolve, 500));
    
    const user: UserInfo = {
      id: trimmedNickname.toLowerCase().replace(/\s+/g, '_'),  // 使用昵称生成 ID
      nickname: trimmedNickname,
      avatarColor: selectedColor,
      createdAt: new Date().toISOString(),
    };
    
    saveUserInfo(user);
    onLogin(user);
    
    message.success(`欢迎，${trimmedNickname}！`);
    setLoading(false);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleLogin();
    }
  };

  return (
    <Modal
      open={visible}
      closable={false}
      footer={null}
      centered
      width={400}
      className="login-modal"
      maskClosable={false}
    >
      <div className="login-content">
        <div className="login-header">
          <div className="login-logo">
            <SmileOutlined />
          </div>
          <h2>欢迎使用 Data Agent</h2>
          <p>智能数据分析助手</p>
        </div>

        <div className="login-form">
          {/* 头像预览 */}
          <div className="avatar-preview">
            <Avatar
              size={80}
              style={{ backgroundColor: selectedColor }}
            >
              {nickname ? nickname.slice(0, 1).toUpperCase() : <UserOutlined />}
            </Avatar>
          </div>

          {/* 昵称输入 */}
          <Input
            size="large"
            placeholder="请输入您的昵称"
            prefix={<UserOutlined />}
            value={nickname}
            onChange={(e) => setNickname(e.target.value)}
            onKeyPress={handleKeyPress}
            maxLength={20}
            className="nickname-input"
          />

          {/* 颜色选择 */}
          <div className="color-picker">
            <span className="color-label">选择头像颜色：</span>
            <div className="color-options">
              {AVATAR_COLORS.map(color => (
                <div
                  key={color}
                  className={`color-option ${selectedColor === color ? 'selected' : ''}`}
                  style={{ backgroundColor: color }}
                  onClick={() => setSelectedColor(color)}
                />
              ))}
            </div>
          </div>

          {/* 登录按钮 */}
          <Button
            type="primary"
            size="large"
            block
            loading={loading}
            onClick={handleLogin}
            className="login-button"
          >
            开始使用
          </Button>
        </div>

        <div className="login-footer">
          <span>首次使用，设置您的昵称即可开始</span>
        </div>
      </div>
    </Modal>
  );
};

