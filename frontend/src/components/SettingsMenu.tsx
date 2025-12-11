import React, { useState, useEffect } from 'react';
import { Modal, Input, Form, message, Button, Select, Space, Tag, Divider, Avatar } from 'antd';
import { 
  SettingOutlined, 
  ApiOutlined, 
  BarChartOutlined,
  DatabaseOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  BookOutlined,
  FileTextOutlined,
  LogoutOutlined,
  CloudUploadOutlined,
  BugOutlined,
} from '@ant-design/icons';
import { clearUserInfo, type UserInfo } from './LoginModal';
import './SettingsMenu.css';

interface SettingsMenuProps {
  onOpenEvaluate?: () => void;
  onOpenMemory?: () => void;
  onOpenKnowledge?: () => void;
  onOpenPrompt?: () => void;
  onOpenDatabase?: () => void;
  onOpenTesting?: () => void;
  currentUser?: UserInfo | null;
  onLogout?: () => void;
}

// 支持的模型配置
const MODEL_PRESETS = [
  {
    key: 'deepseek',
    name: 'DeepSeek',
    models: ['deepseek-chat', 'deepseek-coder', 'deepseek-reasoner'],
    defaultModel: 'deepseek-chat',
    defaultBaseUrl: 'https://api.deepseek.com',
    placeholder: 'sk-xxxxxxxxxxxxxxxxxxxxxxxx',
  },
  {
    key: 'openai',
    name: 'OpenAI',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo', 'o1', 'o1-mini', 'o1-pro'],
    defaultModel: 'gpt-4o',
    defaultBaseUrl: 'https://api.openai.com/v1',
    placeholder: 'sk-xxxxxxxxxxxxxxxxxxxxxxxx',
  },
  {
    key: 'anthropic',
    name: 'Claude (Anthropic)',
    models: ['claude-sonnet-4-20250514', 'claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', 'claude-3-opus-20240229'],
    defaultModel: 'claude-sonnet-4-20250514',
    defaultBaseUrl: 'https://api.anthropic.com',
    placeholder: 'sk-ant-xxxxxxxxxxxxxxxxxxxxxxxx',
  },
  {
    key: 'azure',
    name: 'Azure OpenAI',
    models: ['gpt-4o', 'gpt-4', 'gpt-35-turbo'],
    defaultModel: 'gpt-4o',
    defaultBaseUrl: 'https://your-resource.openai.azure.com',
    placeholder: 'xxxxxxxxxxxxxxxxxxxxxxxx',
  },
  {
    key: 'ollama',
    name: 'Ollama (本地)',
    models: ['llama3', 'llama2', 'mistral', 'codellama', 'qwen2.5'],
    defaultModel: 'llama3',
    defaultBaseUrl: 'http://localhost:11434/v1',
    placeholder: '本地模型无需 API Key',
  },
  {
    key: 'custom',
    name: '自定义',
    models: [],
    defaultModel: '',
    defaultBaseUrl: '',
    placeholder: 'API Key',
  },
];

interface ModelConfig {
  provider: string;
  model: string;
  apiKey: string;
  baseUrl: string;
}

const STORAGE_KEY = 'llm_model_config';

function loadConfig(): ModelConfig | null {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      return JSON.parse(saved);
    }
    // 兼容旧的 deepseek_token
    const oldToken = localStorage.getItem('deepseek_token');
    if (oldToken) {
      return {
        provider: 'deepseek',
        model: 'deepseek-chat',
        apiKey: oldToken,
        baseUrl: 'https://api.deepseek.com',
      };
    }
  } catch {
    // ignore
  }
  return null;
}

function saveConfig(config: ModelConfig) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
  // 同时保存旧格式以兼容
  if (config.provider === 'deepseek') {
    localStorage.setItem('deepseek_token', config.apiKey);
  }
}

// API Key 掩码显示（保留前4位和后4位，中间用****替换）
function maskApiKey(apiKey: string): string {
  if (!apiKey || apiKey.length <= 8) {
    return apiKey ? '****' : '';
  }
  const prefix = apiKey.substring(0, 4);
  const suffix = apiKey.substring(apiKey.length - 4);
  return `${prefix}****${suffix}`;
}

export const SettingsMenu: React.FC<SettingsMenuProps> = ({ 
  onOpenEvaluate, 
  onOpenMemory,
  onOpenKnowledge,
  onOpenPrompt,
  onOpenDatabase,
  onOpenTesting,
  currentUser,
  onLogout,
}) => {
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();
  const [selectedProvider, setSelectedProvider] = useState<string>('deepseek');
  const [currentConfig, setCurrentConfig] = useState<ModelConfig | null>(null);

  useEffect(() => {
    const config = loadConfig();
    setCurrentConfig(config);
    if (config) {
      setSelectedProvider(config.provider);
    }
  }, []);

  const handleOpenModal = () => {
    const config = loadConfig();
    if (config) {
      form.setFieldsValue({
        provider: config.provider,
        model: config.model,
        apiKey: config.apiKey,
        baseUrl: config.baseUrl,
      });
      setSelectedProvider(config.provider);
    } else {
      const defaultPreset = MODEL_PRESETS[0];
      form.setFieldsValue({
        provider: defaultPreset.key,
        model: defaultPreset.defaultModel,
        apiKey: '',
        baseUrl: defaultPreset.defaultBaseUrl,
      });
      setSelectedProvider(defaultPreset.key);
    }
    setModalOpen(true);
  };

  const handleProviderChange = (providerKey: string) => {
    setSelectedProvider(providerKey);
    const preset = MODEL_PRESETS.find(p => p.key === providerKey);
    if (preset) {
      form.setFieldsValue({
        model: preset.defaultModel,
        baseUrl: preset.defaultBaseUrl,
      });
    }
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      const config: ModelConfig = {
        provider: values.provider,
        model: values.model,
        apiKey: values.apiKey || '',
        baseUrl: values.baseUrl,
      };
      saveConfig(config);
      setCurrentConfig(config);
      message.success('模型配置已保存');
      setModalOpen(false);
    } catch {
      // 验证失败
    }
  };

  const handleEvaluate = () => {
    if (onOpenEvaluate) {
      onOpenEvaluate();
    } else {
      window.open('/logs', '_blank');
    }
  };

  const handleOpenMemory = () => {
    if (onOpenMemory) {
      onOpenMemory();
    }
  };

  const currentPreset = MODEL_PRESETS.find(p => p.key === selectedProvider);

  const handleLogout = () => {
    Modal.confirm({
      title: '确认退出',
      content: '退出后需要重新输入昵称',
      okText: '退出',
      cancelText: '取消',
      onOk: () => {
        clearUserInfo();
        if (onLogout) {
          onLogout();
        }
      },
    });
  };

  return (
    <>
      <div className="settings-menu">
        <div className="settings-trigger">
          {currentUser ? (
            <>
              <Avatar
                size={24}
                style={{ backgroundColor: currentUser.avatarColor }}
              >
                {currentUser.nickname.slice(0, 1).toUpperCase()}
              </Avatar>
              <span className="user-nickname">{currentUser.nickname}</span>
            </>
          ) : (
            <>
              <SettingOutlined />
              <span>设置</span>
            </>
          )}
        </div>
        <div className="settings-dropdown">
          {/* 用户信息区 */}
          {currentUser && (
            <>
              <div className="user-info-section">
                <Avatar
                  size={40}
                  style={{ backgroundColor: currentUser.avatarColor }}
                >
                  {currentUser.nickname.slice(0, 1).toUpperCase()}
                </Avatar>
                <div className="user-details">
                  <span className="user-name">{currentUser.nickname}</span>
                  <span className="user-since">
                    加入于 {new Date(currentUser.createdAt).toLocaleDateString('zh-CN')}
                  </span>
                </div>
              </div>
              <div className="settings-divider" />
            </>
          )}
          
          <div className="settings-item" onClick={handleOpenMemory}>
            <DatabaseOutlined />
            <span>学习记忆</span>
          </div>
          <div className="settings-item" onClick={onOpenKnowledge}>
            <BookOutlined />
            <span>业务知识库</span>
          </div>
          <div className="settings-item" onClick={onOpenDatabase}>
            <CloudUploadOutlined />
            <span>数据库维护</span>
          </div>
          <div className="settings-item" onClick={onOpenPrompt}>
            <FileTextOutlined />
            <span>Prompt 配置</span>
          </div>
          <div className="settings-item" onClick={onOpenTesting}>
            <BugOutlined />
            <span>自动化测试</span>
          </div>
          <div className="settings-item" onClick={handleOpenModal}>
            <ApiOutlined />
            <span>模型及 Token</span>
            {currentConfig && (
              <Tag color="success" className="config-status-tag">
                <CheckCircleOutlined />
              </Tag>
            )}
          </div>
          <div className="settings-item" onClick={handleEvaluate}>
            <BarChartOutlined />
            <span>评测会话历史</span>
          </div>
          
          {/* 退出登录 */}
          {currentUser && (
            <>
              <div className="settings-divider" />
              <div className="settings-item logout-item" onClick={handleLogout}>
                <LogoutOutlined />
                <span>退出登录</span>
              </div>
            </>
          )}
        </div>
      </div>

      {/* 模型配置弹窗 */}
      <Modal
        title={
          <Space>
            <ApiOutlined />
            <span>模型及 Token 配置</span>
          </Space>
        }
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setModalOpen(false)}>
            取消
          </Button>,
          <Button key="save" type="primary" onClick={handleSave}>
            保存配置
          </Button>,
        ]}
        className="settings-modal model-config-modal"
        width={520}
      >
        {currentConfig && (
          <div className="current-config-banner">
            <CheckCircleOutlined className="banner-icon" />
            <div className="banner-content">
              <div className="banner-line">
                <span className="banner-label">提供商：</span>
                <strong>{MODEL_PRESETS.find(p => p.key === currentConfig.provider)?.name || currentConfig.provider}</strong>
                <span className="banner-divider">/</span>
                <span className="banner-label">模型：</span>
                <strong>{currentConfig.model}</strong>
              </div>
              {currentConfig.apiKey && (
                <div className="banner-line">
                  <span className="banner-label">API Key：</span>
                  <code className="masked-key">{maskApiKey(currentConfig.apiKey)}</code>
                </div>
              )}
            </div>
          </div>
        )}

        <Form form={form} layout="vertical" className="model-config-form">
          <Form.Item
            name="provider"
            label="模型提供商"
            rules={[{ required: true, message: '请选择模型提供商' }]}
          >
            <Select
              size="large"
              onChange={handleProviderChange}
              options={MODEL_PRESETS.map(preset => ({
                value: preset.key,
                label: (
                  <Space>
                    <span>{preset.name}</span>
                    {preset.key === 'ollama' && <Tag color="green">本地</Tag>}
                    {preset.key === 'custom' && <Tag color="purple">自定义</Tag>}
                  </Space>
                ),
              }))}
            />
          </Form.Item>

          <Form.Item
            name="model"
            label="模型名称"
            rules={[{ required: true, message: '请选择或输入模型名称' }]}
          >
            {currentPreset && currentPreset.models.length > 0 ? (
              <Select
                size="large"
                showSearch
                allowClear
                placeholder="选择或输入模型名称"
                options={currentPreset.models.map(m => ({ value: m, label: m }))}
                // 允许自定义输入
                mode={undefined}
                dropdownRender={(menu) => (
                  <>
                    {menu}
                    <Divider style={{ margin: '8px 0' }} />
                    <div style={{ padding: '4px 8px', color: '#888', fontSize: 12 }}>
                      可直接输入其他模型名称
                    </div>
                  </>
                )}
              />
            ) : (
              <Input size="large" placeholder="输入模型名称，如 gpt-4o" />
            )}
          </Form.Item>

          <Form.Item
            name="apiKey"
            label="API Key"
            rules={[
              { 
                required: selectedProvider !== 'ollama', 
                message: '请输入 API Key' 
              }
            ]}
          >
            <Input.Password 
              size="large"
              placeholder={currentPreset?.placeholder || 'API Key'}
              disabled={selectedProvider === 'ollama'}
            />
          </Form.Item>

          <Form.Item
            name="baseUrl"
            label="API Base URL"
            rules={[{ required: true, message: '请输入 API Base URL' }]}
            extra={
              <span className="form-extra-hint">
                {selectedProvider === 'azure' && '格式：https://your-resource.openai.azure.com'}
                {selectedProvider === 'ollama' && '本地 Ollama 默认地址'}
                {selectedProvider === 'custom' && '自定义 API 服务地址'}
              </span>
            }
          >
            <Input 
              size="large"
              placeholder="https://api.example.com/v1"
            />
          </Form.Item>

          <div className="config-hint">
            <ExclamationCircleOutlined />
            <span>
              配置将保存在浏览器本地存储中。更改后需要刷新页面才能生效。
            </span>
          </div>
        </Form>
      </Modal>
    </>
  );
};
