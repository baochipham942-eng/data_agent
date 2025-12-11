import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Tag,
  Button,
  Modal,
  Form,
  Input,
  message,
  Statistic,
  Row,
  Col,
  Spin,
  Popconfirm,
  Space,
  Tooltip,
  Collapse,
} from 'antd';
import {
  FileTextOutlined,
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import SettingsPageLayout from './SettingsPageLayout';
import './PromptPage.css';

const API_BASE = '/api';

// 所有prompt类型定义
const PROMPT_TYPES = [
  { name: 'system_prompt', label: 'System Prompt', category: 'system', description: '系统主提示词' },
  { name: 'judge_prompt', label: 'Judge Prompt', category: 'judge', description: 'LLM评测提示词' },
  { name: 'sql_fix_prompt', label: 'SQL修复', category: 'sql', description: 'SQL自动修复提示词' },
  { name: 'sql_modify_prompt', label: 'SQL修改', category: 'sql', description: 'SQL修改提示词' },
  { name: 'table_select_prompt', label: '表选择', category: 'sql', description: '智能表选择提示词' },
  { name: 'rewrite_prompt', label: '问题改写', category: 'conversation', description: '问题改写提示词' },
  { name: 'intent_classify_prompt', label: '意图分类', category: 'conversation', description: '意图分类提示词' },
  { name: 'summary_prompt', label: '摘要生成', category: 'utility', description: '会话摘要生成提示词' },
  { name: 'contact_expert_email', label: '联系专家邮件', category: 'email', description: '联系专家邮件模板' },
];

interface PromptVersion {
  id: number;
  name: string;
  version: string;
  content: string;
  description?: string;
  is_active: boolean;
  category: string;
  created_at: string;
  updated_at: string;
}

interface PromptStats {
  total_versions: number;
  prompt_count: number;
  active_count: number;
  total_conversations: number;
}

interface PromptPageProps {
  onBack?: () => void;
}

const PromptPage: React.FC<PromptPageProps> = ({ onBack }) => {
  const [prompts, setPrompts] = useState<PromptVersion[]>([]);
  const [stats, setStats] = useState<PromptStats | null>(null);
  const [loading, setLoading] = useState(true);
  
  // 弹窗状态
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editingVersion, setEditingVersion] = useState<string | null>(null); // 编辑的版本号
  const [form] = Form.useForm();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [promptsRes, statsRes] = await Promise.all([
        fetch(`${API_BASE}/prompt/list`).then(r => r.json()),
        fetch(`${API_BASE}/prompt/stats`).then(r => r.json()),
      ]);
      
      if (promptsRes.success) setPrompts(promptsRes.data);
      if (statsRes.success) setStats(statsRes.data);
    } catch (err) {
      console.error('加载数据失败:', err);
    } finally {
      setLoading(false);
    }
  };

  // 获取某个版本的所有prompt内容
  const getVersionPrompts = (version: string): Record<string, PromptVersion> => {
    const result: Record<string, PromptVersion> = {};
    prompts.forEach(p => {
      if (p.version === version) {
        result[p.name] = p;
      }
    });
    return result;
  };

  // 获取所有版本号（激活的版本排在前面）
  const getAllVersions = (): string[] => {
    const versions = new Set<string>();
    prompts.forEach(p => versions.add(p.version));
    const versionList = Array.from(versions);
    
    // 按激活状态和更新时间排序：激活的在前，然后按更新时间倒序
    return versionList.sort((a, b) => {
      const aActive = isVersionActive(a);
      const bActive = isVersionActive(b);
      
      // 激活的排在前面
      if (aActive && !bActive) return -1;
      if (!aActive && bActive) return 1;
      
      // 如果激活状态相同，按更新时间倒序
      const aPrompts = getVersionPrompts(a);
      const bPrompts = getVersionPrompts(b);
      const aLatest = Object.values(aPrompts).sort(
        (x, y) => new Date(y.updated_at).getTime() - new Date(x.updated_at).getTime()
      )[0];
      const bLatest = Object.values(bPrompts).sort(
        (x, y) => new Date(y.updated_at).getTime() - new Date(x.updated_at).getTime()
      )[0];
      
      if (aLatest && bLatest) {
        return new Date(bLatest.updated_at).getTime() - new Date(aLatest.updated_at).getTime();
      }
      
      return 0;
    });
  };

  const handleCreate = () => {
    setEditingVersion(null);
    form.resetFields();
    // 初始化所有prompt类型的默认值（从当前激活版本复制）
    const initialValues: Record<string, string> = {
      version: '', // 清空版本号，让用户输入
    };
    PROMPT_TYPES.forEach(type => {
      // 优先从激活版本获取，如果没有则从最新版本获取
      const active = prompts.find(p => p.name === type.name && p.is_active);
      if (active) {
        initialValues[type.name] = active.content || '';
      } else {
        // 如果没有激活版本，从最新版本获取
        const latest = prompts
          .filter(p => p.name === type.name)
          .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())[0];
        initialValues[type.name] = latest?.content || '';
      }
    });
    form.setFieldsValue(initialValues);
    setEditModalVisible(true);
  };

  const handleEdit = (version: string) => {
    setEditingVersion(version);
    const versionPrompts = getVersionPrompts(version);
    const formValues: Record<string, string> = {};
    PROMPT_TYPES.forEach(type => {
      formValues[type.name] = versionPrompts[type.name]?.content || '';
    });
    form.setFieldsValue(formValues);
    setEditModalVisible(true);
  };

  const handleSave = async (values: Record<string, string>) => {
    try {
      const version = editingVersion || values.version || `v${Date.now()}`;
      
      if (!editingVersion && !values.version) {
        message.error('请输入版本号');
        return;
      }
      
      // 为每个prompt类型创建或更新版本
      const promises = PROMPT_TYPES.map(async (type) => {
        const content = values[type.name];
        if (!content || content.trim() === '') {
          return; // 跳过空内容
        }

        const existing = prompts.find(
          p => p.name === type.name && p.version === version
        );

        if (existing) {
          // 更新
          const res = await fetch(
            `${API_BASE}/prompt/${type.name}/${version}`,
            {
              method: 'PUT',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                content: content,
                description: type.description,
              }),
            }
          ).then(r => r.json());
          
          if (!res.success) {
            throw new Error(res.detail || `更新${type.label}失败`);
          }
        } else {
          // 创建
          const res = await fetch(`${API_BASE}/prompt/create`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              name: type.name,
              version: version,
              content: content,
              description: type.description,
              category: type.category,
            }),
          }).then(r => r.json());
          
          if (!res.success) {
            throw new Error(res.detail || `创建${type.label}失败`);
          }
        }
      });

      await Promise.all(promises);
      
      message.success('保存成功');
      setEditModalVisible(false);
      loadData();
    } catch (err: any) {
      message.error(err.message || '保存失败');
    }
  };

  const handleActivate = async (version: string) => {
    try {
      // 激活该版本的所有prompt类型
      const versionPrompts = getVersionPrompts(version);
      const promises = Object.keys(versionPrompts).map(async (name) => {
        const res = await fetch(`${API_BASE}/prompt/activate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: name,
            version: version,
          }),
        }).then(r => r.json());
        
        if (!res.success) {
          throw new Error(res.detail || `激活${name}失败`);
        }
      });

      await Promise.all(promises);
      message.success(`已激活版本 ${version}`);
      loadData();
    } catch (err: any) {
      message.error(err.message || '激活失败');
    }
  };

  const handleDelete = async (version: string) => {
    try {
      // 删除该版本的所有prompt类型
      const versionPrompts = getVersionPrompts(version);
      const promises = Object.keys(versionPrompts).map(async (name) => {
        const res = await fetch(
          `${API_BASE}/prompt/${name}/${version}`,
          { method: 'DELETE' }
        ).then(r => r.json());
        
        if (!res.success && res.detail && !res.detail.includes('不存在')) {
          throw new Error(res.detail);
        }
      });

      await Promise.all(promises);
      message.success('删除成功');
      loadData();
    } catch (err: any) {
      message.error(err.message || '删除失败');
    }
  };

  // 检查版本是否激活（至少有一个类型激活就显示为已激活）
  const isVersionActive = (version: string): boolean => {
    const versionPrompts = getVersionPrompts(version);
    return Object.values(versionPrompts).some(p => p.is_active);
  };
  
  // 检查版本的所有类型是否都激活
  const isVersionFullyActive = (version: string): boolean => {
    const versionPrompts = getVersionPrompts(version);
    return Object.values(versionPrompts).length > 0 && 
           Object.values(versionPrompts).every(p => p.is_active);
  };

  const columns = [
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
      width: 150,
      render: (text: string) => {
        const fullyActive = isVersionFullyActive(text);
        const partiallyActive = isVersionActive(text) && !fullyActive;
        
        return (
          <Space>
            <Tag color={fullyActive ? 'green' : partiallyActive ? 'orange' : 'default'}>
              {text}
              {fullyActive && (
                <span style={{ marginLeft: 4, fontSize: '12px' }}>（已激活）</span>
              )}
              {partiallyActive && (
                <span style={{ marginLeft: 4, fontSize: '12px' }}>（部分激活）</span>
              )}
            </Tag>
            {fullyActive && (
              <Tooltip title="当前激活版本（全部类型已激活）">
                <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 16 }} />
              </Tooltip>
            )}
            {partiallyActive && (
              <Tooltip title="部分类型已激活">
                <CheckCircleOutlined style={{ color: '#fa8c16', fontSize: 16 }} />
              </Tooltip>
            )}
          </Space>
        );
      },
    },
    {
      title: '包含的Prompt类型',
      key: 'types',
      render: (_: any, record: any) => {
        const versionPrompts = getVersionPrompts(record.version);
        return (
          <Space wrap>
            {PROMPT_TYPES.map(type => {
              const prompt = versionPrompts[type.name];
              if (!prompt) return null;
              return (
                <Tag key={type.name} color={prompt.is_active ? 'green' : 'default'}>
                  {type.label}
                </Tag>
              );
            })}
          </Space>
        );
      },
    },
    {
      title: '更新时间',
      key: 'updated_at',
      width: 160,
      render: (_: any, record: any) => {
        const versionPrompts = getVersionPrompts(record.version);
        const latest = Object.values(versionPrompts).sort(
          (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
        )[0];
        return latest ? new Date(latest.updated_at).toLocaleString('zh-CN') : '-';
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 250,
      render: (_: any, record: any) => {
        const fullyActive = isVersionFullyActive(record.version);
        const partiallyActive = isVersionActive(record.version) && !fullyActive;
        
        return (
          <Space size="small">
            {!fullyActive && (
              <Button
                type="primary"
                size="small"
                onClick={() => handleActivate(record.version)}
              >
                {partiallyActive ? '继续激活' : '激活'}
              </Button>
            )}
            <Button
              type="text"
              size="small"
              icon={<EditOutlined />}
              onClick={() => handleEdit(record.version)}
            >
              编辑
            </Button>
            {!fullyActive && (
              <Popconfirm
                title="确定删除吗？"
                onConfirm={() => handleDelete(record.version)}
              >
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                />
              </Popconfirm>
            )}
          </Space>
        );
      },
    },
  ];

  const versions = getAllVersions();
  const tableData = versions.map(v => ({ version: v }));

  return (
    <SettingsPageLayout
      title="Prompt 配置"
      icon={<FileTextOutlined />}
      onBack={onBack || (() => {})}
      actions={
        <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
          新建版本
        </Button>
      }
    >
      {/* 统计卡片 */}
      <Row gutter={16} className="stats-row">
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="Prompt 类型"
              value={PROMPT_TYPES.length}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="版本总数"
              value={versions.length}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="激活版本"
              value={versions.filter(v => isVersionActive(v)).length}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="关联会话"
              value={stats?.total_conversations || 0}
            />
          </Card>
        </Col>
      </Row>

      {/* 主内容区 */}
      <Card className="main-card">
        {loading ? (
          <div className="loading-container">
            <Spin />
          </div>
        ) : (
          <Table
            dataSource={tableData}
            columns={columns}
            rowKey="version"
            size="small"
            pagination={false}
          />
        )}
      </Card>

      {/* 编辑弹窗 */}
      <Modal
        title={editingVersion ? `编辑版本 ${editingVersion}` : '新建 Prompt 版本'}
        open={editModalVisible}
        onCancel={() => setEditModalVisible(false)}
        onOk={() => form.submit()}
        width={1000}
        style={{ top: 20 }}
        bodyStyle={{ maxHeight: '80vh', overflowY: 'auto' }}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSave}
        >
          {!editingVersion && (
            <Form.Item
              name="version"
              label="版本号"
              rules={[{ required: true, message: '请输入版本号' }]}
            >
              <Input placeholder="如 v1.0, v2.0" />
            </Form.Item>
          )}

          <Collapse
            defaultActiveKey={PROMPT_TYPES.map(t => t.name)}
            items={PROMPT_TYPES.map(type => {
              const categoryColors: Record<string, string> = {
                'system': 'blue',
                'judge': 'purple',
                'sql': 'cyan',
                'conversation': 'orange',
                'utility': 'green',
                'email': 'red',
              };
              return {
                key: type.name,
                label: (
                  <Space>
                    <Tag color={categoryColors[type.category] || 'default'}>
                      {type.category}
                    </Tag>
                    <strong style={{ fontSize: '14px' }}>{type.label}</strong>
                    <span style={{ color: '#8c8c8c', fontSize: '12px', marginLeft: 8 }}>
                      {type.description}
                    </span>
                  </Space>
                ),
                children: (
                  <Form.Item
                    name={type.name}
                    label={null}
                    rules={[{ required: false }]}
                    style={{ marginBottom: 0 }}
                  >
                    <Input.TextArea
                      rows={12}
                      placeholder={`请输入 ${type.label} 的内容...\n\n提示：可以使用 {变量名} 作为占位符，例如 {schema_context}、{question} 等。`}
                      className="prompt-textarea"
                      style={{ fontFamily: 'monospace', fontSize: '13px' }}
                    />
                  </Form.Item>
                ),
              };
            })}
          />
        </Form>
      </Modal>
    </SettingsPageLayout>
  );
};

export default PromptPage;
