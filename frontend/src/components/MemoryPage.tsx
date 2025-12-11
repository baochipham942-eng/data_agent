import React, { useEffect, useState, useCallback } from 'react';
import { 
  DatabaseOutlined,
  CodeOutlined,
  FileTextOutlined,
  ReloadOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  StarOutlined,
  ThunderboltOutlined,
  TrophyOutlined,
} from '@ant-design/icons';
import { Button, Table, Tabs, Statistic, Card, Row, Col, Tag, Popconfirm, message, Tooltip } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { 
  fetchMemoryStats, 
  fetchRecentToolMemories, 
  fetchRecentTextMemories,
  clearMemories,
  fetchRAGHighScoreCases,
  fetchRAGStats,
  type MemoryStats,
  type ToolMemory,
  type TextMemory,
  type RAGHighScoreCase,
  type RAGStats,
} from '../utils/api';
import SettingsPageLayout from './SettingsPageLayout';
import './MemoryPage.css';

interface MemoryPageProps {
  onBack: () => void;
}

export const MemoryPage: React.FC<MemoryPageProps> = ({ onBack }) => {
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [toolMemories, setToolMemories] = useState<ToolMemory[]>([]);
  const [textMemories, setTextMemories] = useState<TextMemory[]>([]);
  const [ragCases, setRagCases] = useState<RAGHighScoreCase[]>([]);
  const [ragStats, setRagStats] = useState<RAGStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('tool');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsData, toolData, textData, ragData, ragStatsData] = await Promise.all([
        fetchMemoryStats(),
        fetchRecentToolMemories(100),
        fetchRecentTextMemories(100),
        fetchRAGHighScoreCases(100, 4.0).catch(() => []),  // 如果RAG未初始化，返回空数组
        fetchRAGStats().catch(() => null),  // 如果RAG未初始化，返回null
      ]);
      setStats(statsData);
      setToolMemories(toolData);
      setTextMemories(textData);
      setRagCases(ragData);
      setRagStats(ragStatsData);
    } catch (error) {
      console.error('Failed to load memory data:', error);
      message.error('加载记忆数据失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleClearAll = async () => {
    try {
      const count = await clearMemories();
      message.success(`已清除 ${count} 条记忆`);
      loadData();
    } catch (error) {
      console.error('Failed to clear memories:', error);
      message.error('清除失败');
    }
  };

  const formatTimestamp = (timestamp: string) => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return timestamp;
    }
  };

  const toolColumns: ColumnsType<ToolMemory> = [
    {
      title: '时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 120,
      render: (timestamp: string) => (
        <span className="memory-time">
          <ClockCircleOutlined /> {formatTimestamp(timestamp)}
        </span>
      ),
    },
    {
      title: '工具',
      dataIndex: 'tool_name',
      key: 'tool_name',
      width: 120,
      render: (name: string) => (
        <Tag color="blue" icon={<CodeOutlined />}>{name}</Tag>
      ),
    },
    {
      title: '问题/SQL',
      dataIndex: 'question',
      key: 'question',
      ellipsis: true,
      render: (question: string, record: ToolMemory) => {
        const sql = record.args?.sql as string | undefined;
        return (
          <div className="memory-content">
            <div className="memory-question">{question}</div>
            {sql && (
              <Tooltip title={sql} placement="topLeft">
                <div className="memory-sql">
                  <code>{sql.length > 100 ? sql.substring(0, 100) + '...' : sql}</code>
                </div>
              </Tooltip>
            )}
          </div>
        );
      },
    },
    {
      title: '来源',
      key: 'source',
      width: 100,
      render: (_: unknown, record: ToolMemory) => {
        const source = record.metadata?.source;
        const score = record.metadata?.score;
        
        if (source === 'feedback_learning') {
          return (
            <Tooltip title={score ? `用户评分: ${score}` : '用户好评学习'}>
              <Tag color="gold" icon={<StarOutlined />}>
                好评 {score ? `(${score})` : ''}
              </Tag>
            </Tooltip>
          );
        }
        
        return (
          <Tooltip title="SQL执行成功自动学习">
            <Tag color="cyan" icon={<ThunderboltOutlined />}>
              自动
            </Tag>
          </Tooltip>
        );
      },
    },
    {
      title: '状态',
      dataIndex: 'success',
      key: 'success',
      width: 80,
      render: (success: boolean) => (
        success ? (
          <Tag color="success" icon={<CheckCircleOutlined />}>成功</Tag>
        ) : (
          <Tag color="error">失败</Tag>
        )
      ),
    },
  ];

  const textColumns: ColumnsType<TextMemory> = [
    {
      title: '时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 120,
      render: (timestamp: string) => (
        <span className="memory-time">
          <ClockCircleOutlined /> {formatTimestamp(timestamp)}
        </span>
      ),
    },
    {
      title: '内容',
      dataIndex: 'content',
      key: 'content',
      render: (content: string) => (
        <div className="text-memory-content">
          <pre>{content}</pre>
        </div>
      ),
    },
  ];

  const ragColumns: ColumnsType<RAGHighScoreCase> = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 120,
      render: (created_at: string) => (
        <span className="memory-time">
          <ClockCircleOutlined /> {formatTimestamp(created_at)}
        </span>
      ),
    },
    {
      title: '问题',
      dataIndex: 'question',
      key: 'question',
      ellipsis: true,
      render: (question: string) => (
        <div className="memory-content">
          <div className="memory-question">{question}</div>
        </div>
      ),
    },
    {
      title: 'SQL',
      dataIndex: 'sql',
      key: 'sql',
      ellipsis: true,
      render: (sql: string) => (
        <Tooltip title={sql} placement="topLeft">
          <div className="memory-sql">
            <code>{sql.length > 100 ? sql.substring(0, 100) + '...' : sql}</code>
          </div>
        </Tooltip>
      ),
    },
    {
      title: '评分',
      key: 'score',
      width: 150,
      render: (_: unknown, record: RAGHighScoreCase) => (
        <div>
          <div>
            <Tag color="gold" icon={<StarOutlined />}>
              综合: {record.score.toFixed(1)}
            </Tag>
          </div>
          {record.expert_rating && (
            <div style={{ marginTop: 4 }}>
              <Tag color="purple">专家: {record.expert_rating}</Tag>
            </div>
          )}
          {record.quality_score > 0 && (
            <div style={{ marginTop: 4 }}>
              <Tag color="cyan">质量: {record.quality_score.toFixed(2)}</Tag>
            </div>
          )}
        </div>
      ),
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 100,
      render: (source: string) => {
        if (source === 'expert') {
          return (
            <Tag color="purple" icon={<StarOutlined />}>
              专家
            </Tag>
          );
        } else if (source === 'feedback') {
          return (
            <Tag color="blue" icon={<ThunderboltOutlined />}>
              反馈
            </Tag>
          );
        } else {
          return (
            <Tag color="default">
              {source}
            </Tag>
          );
        }
      },
    },
    {
      title: '使用次数',
      dataIndex: 'usage_count',
      key: 'usage_count',
      width: 100,
      render: (count: number) => (
        <span>{count || 0}</span>
      ),
    },
  ];

  const tabItems = [
    {
      key: 'tool',
      label: (
        <span>
          <CodeOutlined />
          SQL 学习记录 ({toolMemories.length})
        </span>
      ),
      children: (
        <Table
          columns={toolColumns}
          dataSource={toolMemories}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 20, showSizeChanger: true }}
          size="middle"
          className="memory-table"
        />
      ),
    },
    {
      key: 'text',
      label: (
        <span>
          <FileTextOutlined />
          Schema 记忆 ({stats?.total_text_memories || textMemories.length})
        </span>
      ),
      children: (
        <Table
          columns={textColumns}
          dataSource={textMemories}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10, showSizeChanger: true }}
          size="middle"
          className="memory-table"
        />
      ),
    },
    {
      key: 'rag',
      label: (
        <span>
          <TrophyOutlined />
          RAG 高分案例 ({ragCases.length})
        </span>
      ),
      children: (
        <Table
          columns={ragColumns}
          dataSource={ragCases}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 20, showSizeChanger: true }}
          size="middle"
          className="memory-table"
        />
      ),
    },
  ];

  return (
    <SettingsPageLayout
      title="学习记忆"
      icon={<DatabaseOutlined />}
      onBack={onBack}
      actions={
        <>
          <Button 
            icon={<ReloadOutlined />} 
            onClick={loadData}
            loading={loading}
          >
            刷新
          </Button>
          <Popconfirm
            title="确定要清除所有记忆吗？"
            description="此操作不可恢复，Agent 将失去所有学习的 SQL 模式。"
            onConfirm={handleClearAll}
            okText="确定清除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button 
              icon={<DeleteOutlined />} 
              danger
            >
              清除全部
            </Button>
          </Popconfirm>
        </>
      }
    >
      {/* 统计卡片 */}
      <Row gutter={16} className="stats-row" style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="SQL 学习总数"
              value={stats?.total_tool_memories || 0}
              prefix={<CodeOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="成功学习"
              value={stats?.successful_tool_memories || 0}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Schema 记忆"
              value={stats?.total_text_memories || 0}
              prefix={<FileTextOutlined />}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="RAG 高分案例"
              value={ragStats?.total || ragCases.length || 0}
              prefix={<TrophyOutlined />}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 内容区域 */}
      <Card className="main-card">
        <Tabs 
          activeKey={activeTab} 
          onChange={setActiveTab}
          items={tabItems}
        />
      </Card>
    </SettingsPageLayout>
  );
};

