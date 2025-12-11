import React, { useEffect, useState, useMemo } from 'react';
import { 
  Table, 
  Card, 
  Input, 
  Select, 
  Button, 
  Tag, 
  Space, 
  Statistic, 
  Row, 
  Col,
  Modal,
  Rate,
  message,
  Tooltip,
  Badge,
  Progress,
  Typography,
  Drawer,
  Divider,
} from 'antd';
import { 
  SearchOutlined, 
  FilterOutlined, 
  ExportOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  UserOutlined,
  MessageOutlined,
  StarOutlined,
  EyeOutlined,
  ArrowLeftOutlined,
  DatabaseOutlined,
  BarChartOutlined,
  DeleteOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { ReasoningStep, ChartData } from '../types';
import { ThoughtChain } from './ThoughtChain';
import { SqlBlock } from './SqlBlock';
import { DataTable } from './DataTable';
import { DataChart } from './DataChart';
import { AutoChart } from './AutoChart';
import { extractSQLFromText } from '../utils/api';
import './EvaluatePage.css';

const { Search } = Input;
const { Text, Paragraph } = Typography;

interface ConversationLog {
  id: string;
  user_id: string;
  started_at: string;
  ended_at: string | null;
  source: string;
  has_error: boolean;
  summary: string | null;
  rating?: number;
  message_count?: number;
}

interface ConversationDetail {
  id: string;
  messages: Array<{
    role: string;
    content: string;
    created_at: string;
    tools?: string[];
    sql?: string;
    table_data?: Record<string, unknown>[];
    chart_data?: ChartData;
    reasoning_steps?: ReasoningStep[];
  }>;
  summary: string;
}

interface EvaluatePageProps {
  onBack: () => void;
}

export const EvaluatePage: React.FC<EvaluatePageProps> = ({ onBack }) => {
  const [logs, setLogs] = useState<ConversationLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchText, setSearchText] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [selectedConversation, setSelectedConversation] = useState<ConversationDetail | null>(null);
  const [detailDrawerOpen, setDetailDrawerOpen] = useState(false);
  const [currentRatingId, setCurrentRatingId] = useState<string | null>(null);
  const [currentRating, setCurrentRating] = useState<number>(0);
  const [ratings, setRatings] = useState<Record<string, number>>({});

  // 加载会话列表
  const loadLogs = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/chat/conversations');
      if (res.ok) {
        const data = await res.json();
        // 转换数据格式
        const formattedLogs: ConversationLog[] = (data.conversations || []).map((c: any) => ({
          id: c.id,
          user_id: c.user_id || 'guest',
          started_at: c.time || c.started_at || '',
          ended_at: c.ended_at || null,
          source: c.source || 'chat',
          has_error: c.has_error || false,
          summary: c.summary || null,
          message_count: c.message_count,
        }));
        setLogs(formattedLogs);
      }
    } catch (error) {
      console.error('Failed to load logs:', error);
      message.error('加载会话记录失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
    // 从localStorage加载评分
    const savedRatings = localStorage.getItem('conversation_ratings');
    if (savedRatings) {
      setRatings(JSON.parse(savedRatings));
    }
  }, []);

  // 加载会话详情
  const loadConversationDetail = async (id: string) => {
    try {
      const res = await fetch(`/api/chat/conversation/${id}`);
      if (res.ok) {
        const data = await res.json();
        // 处理消息数据，映射字段名（snake_case -> camelCase）并提取额外信息
        const processedMessages = (data.messages || []).map((msg: any) => {
          // 获取表格数据
          const tableData = msg.table_data || msg.tableData;
          
          // 获取图表数据
          const rawChartData = msg.chart_data || msg.chartData;
          const chartData = rawChartData && typeof rawChartData === 'object' && 'type' in rawChartData 
            ? rawChartData as ChartData 
            : undefined;
          
          // 清理消息内容中的技术数据
          let cleanContent = msg.content || '';
          if (cleanContent && cleanContent.includes('data:')) {
            const contentLines = cleanContent.split('\n').filter((line: string) => {
              const trimmed = line.trim();
              return trimmed && 
                !trimmed.startsWith('data:') &&
                !trimmed.startsWith('{') &&
                !trimmed.startsWith('[') &&
                !trimmed.includes('{"rich":') &&
                !trimmed.includes('"type":"') &&
                !trimmed.includes('"actions":');
            });
            cleanContent = contentLines.join('\n').trim();
          }
          
          // 获取SQL
          let sql = msg.sql;
          // 清理SQL中的JSON数据
          if (sql) {
            sql = sql.split('"}')[0].split('",')[0].split('\n')[0].trim();
            if (sql.includes('"actions"') || sql.includes('"metadata"')) {
              sql = extractSQLFromText(sql) || undefined;
            }
          }
          if (!sql && msg.role === 'assistant' && cleanContent) {
            sql = extractSQLFromText(cleanContent) || undefined;
          }
          
          // 获取思考过程
          let reasoning = msg.reasoning_steps || msg.reasoning;
          if (!reasoning && msg.role === 'assistant') {
            // 为历史消息创建已完成的步骤展示
            reasoning = [
              { number: 1, text: '理解用户需求', status: 'done' as const, detail: '已理解用户意图' },
              { number: 2, text: '生成 SQL 查询', status: sql ? ('done' as const) : ('pending' as const), detail: sql ? '已生成SQL查询' : '未生成SQL' },
              { number: 3, text: '执行查询获取数据', status: tableData ? ('done' as const) : ('pending' as const), detail: tableData ? `获取到 ${tableData.length} 条数据` : '未获取数据' },
              { number: 4, text: '生成分析结果', status: 'done' as const, detail: cleanContent || '分析完成' },
            ];
          } else if (reasoning && msg.role === 'assistant') {
            // 如果后端返回了reasoning，确保所有步骤的status都是done，并填充detail
            const stepTexts = ['理解用户需求', '生成 SQL 查询', '执行查询获取数据', '生成分析结果'];
            reasoning = reasoning.slice(0, 4).map((step: any, idx: number) => {
              const updatedStep = { ...step };
              updatedStep.status = 'done'; // 历史消息的步骤都应该是done
              
              // 确保步骤number正确（1, 2, 3, 4）
              updatedStep.number = idx + 1;
              
              // 确保步骤text正确
              updatedStep.text = stepTexts[idx] || step.text;
              
              // 对于步骤4（分析结果），始终使用完整的cleanContent，确保内容完整
              if (idx === 3) {
                updatedStep.detail = cleanContent || updatedStep.detail || '分析完成';
              } else if (!updatedStep.detail || updatedStep.detail === '分析完成' || (updatedStep.detail && updatedStep.detail.length < 3)) {
                // 其他步骤如果没有detail，填充默认值
                if (idx === 0) updatedStep.detail = '已理解用户意图';
                else if (idx === 1) updatedStep.detail = sql ? '已生成SQL查询' : '已处理';
                else if (idx === 2) updatedStep.detail = tableData ? `获取到 ${tableData.length} 条数据` : '数据获取完成';
              }
              
              // 如果detail看起来像是被错误地设置为text，清空它
              if (updatedStep.detail && updatedStep.detail.length > 200 && idx !== 3) {
                if (idx === 0) updatedStep.detail = '已理解用户意图';
                else if (idx === 1) updatedStep.detail = sql ? '已生成SQL查询' : '已处理';
                else if (idx === 2) updatedStep.detail = tableData ? `获取到 ${tableData.length} 条数据` : '数据获取完成';
              }
              
              return updatedStep;
            });
            
            // 确保只有4个步骤
            if (reasoning.length !== 4) {
              reasoning = [
                { number: 1, text: '理解用户需求', status: 'done' as const, detail: '已理解用户意图' },
                { number: 2, text: '生成 SQL 查询', status: 'done' as const, detail: sql ? '已生成SQL查询' : '已处理' },
                { number: 3, text: '执行查询获取数据', status: 'done' as const, detail: tableData ? `获取到 ${tableData.length} 条数据` : '数据获取完成' },
                { number: 4, text: '生成分析结果', status: 'done' as const, detail: cleanContent || '分析完成' },
              ];
            }
          }
          
          return {
            role: msg.role,
            content: cleanContent,
            created_at: msg.created_at || msg.createdAt || '',
            tools: msg.tools || [],
            sql,
            table_data: tableData,
            chart_data: chartData,
            reasoning_steps: reasoning,
          };
        });
        
        setSelectedConversation({
          id,
          messages: processedMessages,
          summary: logs.find(l => l.id === id)?.summary || '',
        });
        // 设置当前评分
        setCurrentRatingId(id);
        setCurrentRating(ratings[id] || 0);
        setDetailDrawerOpen(true);
      }
    } catch (error) {
      console.error('Failed to load conversation detail:', error);
      message.error('加载会话详情失败');
    }
  };

  // 删除会话
  const handleDeleteConversation = async (id: string) => {
    Modal.confirm({
      title: '确认删除',
      icon: <ExclamationCircleOutlined />,
      content: '确定要删除这条会话记录吗？此操作不可恢复。',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          const res = await fetch(`/api/chat/conversation/${id}`, {
            method: 'DELETE',
          });
          if (res.ok) {
            message.success('删除成功');
            // 从列表中移除
            setLogs(prev => prev.filter(l => l.id !== id));
            // 同时删除评分
            const newRatings = { ...ratings };
            delete newRatings[id];
            setRatings(newRatings);
            localStorage.setItem('conversation_ratings', JSON.stringify(newRatings));
          } else {
            message.error('删除失败');
          }
        } catch (error) {
          console.error('Failed to delete conversation:', error);
          message.error('删除失败');
        }
      },
    });
  };


  // 导出数据
  const handleExport = () => {
    const exportData = filteredLogs.map(log => ({
      ...log,
      rating: ratings[log.id] || '未评分',
    }));
    const csv = [
      ['ID', '用户', '开始时间', '状态', '摘要', '评分'].join(','),
      ...exportData.map(d => [
        d.id,
        d.user_id,
        d.started_at,
        d.has_error ? '错误' : '正常',
        `"${(d.summary || '').replace(/"/g, '""')}"`,
        d.rating,
      ].join(','))
    ].join('\n');
    
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `conversation_logs_${Date.now()}.csv`;
    link.click();
    URL.revokeObjectURL(url);
    message.success('导出成功');
  };

  // 过滤数据
  const filteredLogs = useMemo(() => {
    return logs.filter(log => {
      const matchSearch = !searchText || 
        log.id.toLowerCase().includes(searchText.toLowerCase()) ||
        log.user_id.toLowerCase().includes(searchText.toLowerCase()) ||
        (log.summary || '').toLowerCase().includes(searchText.toLowerCase());
      
      const matchStatus = statusFilter === 'all' ||
        (statusFilter === 'error' && log.has_error) ||
        (statusFilter === 'normal' && !log.has_error) ||
        (statusFilter === 'rated' && ratings[log.id]) ||
        (statusFilter === 'unrated' && !ratings[log.id]);
      
      return matchSearch && matchStatus;
    });
  }, [logs, searchText, statusFilter, ratings]);

  // 统计数据
  const stats = useMemo(() => {
    const total = logs.length;
    const errors = logs.filter(l => l.has_error).length;
    const rated = Object.keys(ratings).filter(id => logs.some(l => l.id === id)).length;
    const avgRating = rated > 0 
      ? Object.values(ratings).reduce((a, b) => a + b, 0) / rated 
      : 0;
    return { total, errors, rated, avgRating };
  }, [logs, ratings]);

  // 表格列配置
  const columns: ColumnsType<ConversationLog> = [
    {
      title: '会话ID',
      dataIndex: 'id',
      key: 'id',
      width: 180,
      ellipsis: true,
      render: (id: string) => (
        <Tooltip title={id}>
          <Text code style={{ fontSize: 11 }}>{id.slice(0, 16)}...</Text>
        </Tooltip>
      ),
    },
    {
      title: '用户',
      dataIndex: 'user_id',
      key: 'user_id',
      width: 120,
      render: (user: string) => (
        <Space>
          <UserOutlined />
          <Text>{user}</Text>
        </Space>
      ),
    },
    {
      title: '时间',
      dataIndex: 'started_at',
      key: 'started_at',
      width: 140,
      render: (time: string) => (
        <Space>
          <ClockCircleOutlined />
          <Text type="secondary">{time}</Text>
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'has_error',
      key: 'status',
      width: 80,
      render: (hasError: boolean) => (
        hasError 
          ? <Tag icon={<CloseCircleOutlined />} color="error">错误</Tag>
          : <Tag icon={<CheckCircleOutlined />} color="success">正常</Tag>
      ),
    },
    {
      title: '摘要',
      dataIndex: 'summary',
      key: 'summary',
      ellipsis: true,
      render: (summary: string | null) => (
        <Paragraph ellipsis={{ rows: 2 }} style={{ margin: 0, fontSize: 13 }}>
          {summary || '（暂无摘要）'}
        </Paragraph>
      ),
    },
    {
      title: '评分',
      key: 'rating',
      width: 140,
      render: (_, record) => {
        const rating = ratings[record.id];
        return rating ? (
          <Rate disabled value={rating} style={{ fontSize: 14 }} />
        ) : (
          <Text type="secondary">未评分</Text>
        );
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_, record) => (
        <Space>
          <Tooltip title="查看详情">
            <Button 
              type="text" 
              size="small" 
              icon={<EyeOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                loadConversationDetail(record.id);
              }}
            />
          </Tooltip>
          <Tooltip title="删除">
            <Button 
              type="text" 
              size="small" 
              danger
              icon={<DeleteOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                handleDeleteConversation(record.id);
              }}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div className="evaluate-page">
      {/* 头部 */}
      <div className="evaluate-header">
        <div className="header-left">
          <Button 
            type="text" 
            icon={<ArrowLeftOutlined />} 
            onClick={onBack}
            className="back-btn"
          >
            返回对话
          </Button>
          <h1 className="page-title">
            <BarChartOutlined /> 会话历史评测
          </h1>
        </div>
        <div className="header-actions">
          <Button icon={<ExportOutlined />} onClick={handleExport}>
            导出数据
          </Button>
        </div>
      </div>

      {/* 统计卡片 */}
      <Row gutter={16} className="stats-row">
        <Col span={6}>
          <Card className="stat-card">
            <Statistic 
              title="总会话数" 
              value={stats.total} 
              prefix={<MessageOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card className="stat-card">
            <Statistic 
              title="错误会话" 
              value={stats.errors}
              valueStyle={{ color: stats.errors > 0 ? '#ff4d4f' : '#52c41a' }}
              prefix={<CloseCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card className="stat-card">
            <Statistic 
              title="已评分" 
              value={stats.rated}
              suffix={`/ ${stats.total}`}
              prefix={<StarOutlined />}
            />
            <Progress 
              percent={stats.total > 0 ? Math.round(stats.rated / stats.total * 100) : 0} 
              size="small" 
              showInfo={false}
              strokeColor="#58a6ff"
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card className="stat-card">
            <Statistic 
              title="平均评分" 
              value={stats.avgRating.toFixed(1)}
              suffix="/ 5"
              prefix={<StarOutlined style={{ color: '#fadb14' }} />}
            />
          </Card>
        </Col>
      </Row>

      {/* 搜索和筛选 */}
      <Card className="filter-card">
        <Space size="middle" wrap>
          <Search
            placeholder="搜索会话ID、用户或摘要..."
            allowClear
            style={{ width: 300 }}
            prefix={<SearchOutlined />}
            onChange={(e) => setSearchText(e.target.value)}
          />
          <Select
            value={statusFilter}
            onChange={setStatusFilter}
            style={{ width: 150 }}
            options={[
              { value: 'all', label: '全部状态' },
              { value: 'normal', label: '正常' },
              { value: 'error', label: '错误' },
              { value: 'rated', label: '已评分' },
              { value: 'unrated', label: '未评分' },
            ]}
            prefix={<FilterOutlined />}
          />
          <Badge count={filteredLogs.length} showZero>
            <Text type="secondary">共 {filteredLogs.length} 条记录</Text>
          </Badge>
        </Space>
      </Card>

      {/* 表格 */}
      <Card className="table-card">
        <Table
          columns={columns}
          dataSource={filteredLogs}
          rowKey="id"
          loading={loading}
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 条`,
          }}
          size="middle"
          onRow={(record) => ({
            onClick: () => loadConversationDetail(record.id),
            style: { cursor: 'pointer' },
          })}
          rowClassName="clickable-row"
        />
      </Card>


      {/* 详情抽屉 */}
      <Drawer
        title="会话详情"
        placement="right"
        width={800}
        open={detailDrawerOpen}
        onClose={() => {
          setDetailDrawerOpen(false);
          setCurrentRatingId(null);
        }}
        className="detail-drawer"
        footer={
          selectedConversation && (
            <div style={{ padding: '16px 0', borderTop: '1px solid var(--color-surface-border)' }}>
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <div>
                  <Text strong style={{ marginRight: 12 }}>评分：</Text>
                  <Rate 
                    value={currentRating} 
                    onChange={(value) => {
                      setCurrentRating(value);
                      if (currentRatingId) {
                        const newRatings = { ...ratings, [currentRatingId]: value };
                        setRatings(newRatings);
                        localStorage.setItem('conversation_ratings', JSON.stringify(newRatings));
                        message.success('评分已保存');
                      }
                    }}
                    style={{ fontSize: 24 }}
                  />
                  <Text type="secondary" style={{ marginLeft: 12, fontSize: 12 }}>
                    {currentRating === 0 && '点击星星评分'}
                    {currentRating === 1 && '很差 - 回答完全不相关'}
                    {currentRating === 2 && '较差 - 回答有重大问题'}
                    {currentRating === 3 && '一般 - 回答基本正确但不完善'}
                    {currentRating === 4 && '良好 - 回答准确且有帮助'}
                    {currentRating === 5 && '优秀 - 回答准确、完整且有洞察'}
                  </Text>
                </div>
              </Space>
            </div>
          )
        }
      >
        {selectedConversation && (
          <div className="conversation-detail">
            <div className="detail-summary">
              <Text strong>摘要：</Text>
              <Paragraph>{selectedConversation.summary || '（暂无摘要）'}</Paragraph>
            </div>
            <Divider>对话记录</Divider>
            <div className="detail-messages">
              {selectedConversation.messages.map((msg, idx) => (
                <div key={idx} className={`detail-message-item ${msg.role}`}>
                  <div className="msg-header">
                    <Tag color={msg.role === 'user' ? 'blue' : 'green'}>
                      {msg.role === 'user' ? '用户' : '助手'}
                    </Tag>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {msg.created_at}
                    </Text>
                  </div>
                  
                  {msg.role === 'user' ? (
                    <div className="msg-content">
                      <Paragraph style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                        {msg.content}
                      </Paragraph>
                    </div>
                  ) : (
                    <div className="msg-content">
                      {/* 思考过程 */}
                      {msg.reasoning_steps && msg.reasoning_steps.length > 0 && (
                        <ThoughtChain 
                          steps={msg.reasoning_steps.map(step => ({
                            ...step,
                            status: 'done' as const,
                          }))} 
                          isStreaming={false}
                        />
                      )}
                      
                      {/* SQL代码块 */}
                      {msg.sql && <SqlBlock sql={msg.sql} />}
                      
                      {/* 数据表格 */}
                      {msg.table_data && msg.table_data.length > 0 && (
                        <DataTable data={msg.table_data} />
                      )}
                      
                      {/* 图表 */}
                      {msg.table_data && msg.table_data.length > 0 && msg.table_data.length <= 50 ? (
                        <AutoChart 
                          data={msg.table_data}
                          title={msg.chart_data?.title || undefined}
                        />
                      ) : msg.chart_data && msg.chart_data.data && Array.isArray(msg.chart_data.data) && msg.chart_data.data.length > 0 ? (
                        <DataChart data={msg.chart_data} />
                      ) : null}
                      
                      {/* 消息内容 */}
                      {msg.content && (
                        <Paragraph 
                          ellipsis={{ rows: 10, expandable: true }}
                          style={{ marginTop: 12, whiteSpace: 'pre-wrap' }}
                        >
                          {msg.content}
                        </Paragraph>
                      )}
                      
                      {/* 工具标签 */}
                      {msg.tools && msg.tools.length > 0 && (
                        <div style={{ marginTop: 12 }}>
                          {msg.tools.map((tool, i) => (
                            <Tag key={i} icon={<DatabaseOutlined />} color="purple">
                              {tool}
                            </Tag>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  
                  {idx < selectedConversation.messages.length - 1 && <Divider style={{ margin: '16px 0' }} />}
                </div>
              ))}
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
};

