import React, { useState, useEffect } from 'react';
import {
  Table,
  Button,
  Card,
  Tag,
  Progress,
  Space,
  Modal,
  Checkbox,
  message,
  Popconfirm,
  Descriptions,
  Typography,
  Empty,
  Statistic,
  Row,
  Col,
} from 'antd';
import {
  PlayCircleOutlined,
  ReloadOutlined,
  DeleteOutlined,
  EyeOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  WarningOutlined,
  ArrowLeftOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import './TestingPage.css';

const { Title, Text } = Typography;

interface TestingPageProps {
  onBack?: () => void;
}

interface TestReport {
  id: string;
  test_scopes: string[];
  test_count: number;
  passed_count: number;
  failed_count: number;
  error_count: number;
  skipped_count: number;
  progress: number;
  status: 'running' | 'passed' | 'failed' | 'error';
  result?: any;
  started_at: string;
  completed_at?: string;
  duration?: number;
  created_at: string;
}

interface TestStats {
  total: number;
  passed: number;
  failed: number;
  running: number;
  error: number;
}

const TEST_SCOPES = [
  { label: '单元测试', value: 'unit' },
  { label: '集成测试', value: 'integration' },
  { label: '服务层测试', value: 'service' },
  { label: 'API 测试', value: 'api' },
  { label: '端到端测试', value: 'e2e' },
];

const TestingPage: React.FC<TestingPageProps> = ({ onBack }) => {
  const [reports, setReports] = useState<TestReport[]>([]);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<TestStats | null>(null);
  const [runModalVisible, setRunModalVisible] = useState(false);
  const [selectedScopes, setSelectedScopes] = useState<string[]>(['unit', 'integration', 'service']);
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [selectedReport, setSelectedReport] = useState<TestReport | null>(null);
  const [autoRefresh] = useState(true);

  // 获取测试报告列表
  const fetchReports = async () => {
    try {
      const response = await fetch('/api/testing/reports?limit=50');
      const data = await response.json();
      setReports(data);
    } catch (error) {
      message.error('获取测试报告列表失败');
      console.error(error);
    }
  };

  // 获取统计信息
  const fetchStats = async () => {
    try {
      const response = await fetch('/api/testing/stats');
      const data = await response.json();
      setStats(data);
    } catch (error) {
      console.error(error);
    }
  };

  useEffect(() => {
    fetchReports();
    fetchStats();
  }, []);

  // 自动刷新运行中的测试
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      const hasRunning = reports.some(r => r.status === 'running');
      if (hasRunning) {
        fetchReports();
        fetchStats();
      }
    }, 3000); // 每3秒刷新一次

    return () => clearInterval(interval);
  }, [reports, autoRefresh]);

  // 运行测试
  const handleRunTests = async () => {
    if (selectedScopes.length === 0) {
      message.warning('请至少选择一个测试范围');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/testing/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          test_scopes: selectedScopes,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        let errorMessage = '启动测试失败';
        try {
          const errorData = JSON.parse(errorText);
          errorMessage = errorData.detail || errorData.message || errorMessage;
        } catch {
          errorMessage = errorText || errorMessage;
        }
        message.error(`启动测试失败: ${errorMessage}`);
        return;
      }

      const data = await response.json();
      if (data.success) {
        message.success('测试已开始运行');
        setRunModalVisible(false);
        // 立即刷新列表
        setTimeout(() => {
          fetchReports();
          fetchStats();
        }, 500);
      } else {
        message.error(`启动测试失败: ${data.message || data.detail || '未知错误'}`);
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      message.error(`启动测试失败: ${errorMessage}`);
      console.error('测试运行错误:', error);
    } finally {
      setLoading(false);
    }
  };

  // 删除测试报告
  const handleDelete = async (reportId: string) => {
    try {
      const response = await fetch(`/api/testing/reports/${reportId}`, {
        method: 'DELETE',
      });

      const data = await response.json();
      if (data.success) {
        message.success('测试报告已删除');
        fetchReports();
        fetchStats();
      } else {
        message.error('删除失败');
      }
    } catch (error) {
      message.error('删除失败');
      console.error(error);
    }
  };

  // 查看详情
  const handleViewDetail = async (reportId: string) => {
    try {
      const response = await fetch(`/api/testing/reports/${reportId}`);
      const data = await response.json();
      setSelectedReport(data);
      setDetailModalVisible(true);
    } catch (error) {
      message.error('获取测试报告详情失败');
      console.error(error);
    }
  };

  // 获取状态标签
  const getStatusTag = (status: string) => {
    const statusConfig: Record<string, { color: string; icon: React.ReactNode; text: string }> = {
      running: { color: 'processing', icon: <ClockCircleOutlined />, text: '运行中' },
      passed: { color: 'success', icon: <CheckCircleOutlined />, text: '通过' },
      failed: { color: 'error', icon: <CloseCircleOutlined />, text: '失败' },
      error: { color: 'warning', icon: <WarningOutlined />, text: '错误' },
    };

    const config = statusConfig[status] || statusConfig.running;
    return (
      <Tag color={config.color} icon={config.icon}>
        {config.text}
      </Tag>
    );
  };

  // 格式化测试范围
  const formatScopes = (scopes: string[]) => {
    const scopeMap: Record<string, string> = {
      unit: '单元测试',
      integration: '集成测试',
      service: '服务层',
      api: 'API',
      e2e: '端到端',
    };
    return scopes.map(s => scopeMap[s] || s).join('、');
  };

  // 表格列定义
  const columns: ColumnsType<TestReport> = [
    {
      title: '测试报告 ID',
      dataIndex: 'id',
      key: 'id',
      width: 200,
      render: (id: string) => <Text code>{id.substring(0, 8)}...</Text>,
    },
    {
      title: '测试功能',
      dataIndex: 'test_scopes',
      key: 'test_scopes',
      render: (scopes: string[]) => formatScopes(scopes),
    },
    {
      title: '测试进度',
      dataIndex: 'progress',
      key: 'progress',
      width: 150,
      render: (progress: number, record: TestReport) => (
        <Progress
          percent={progress}
          status={record.status === 'running' ? 'active' : undefined}
          size="small"
        />
      ),
    },
    {
      title: '测试结果',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '测试统计',
      key: 'stats',
      width: 200,
      render: (_: any, record: TestReport) => (
        <Space size="small">
          <span>总计: {record.test_count}</span>
          <Tag color="success">通过: {record.passed_count}</Tag>
          {record.failed_count > 0 && <Tag color="error">失败: {record.failed_count}</Tag>}
          {record.error_count > 0 && <Tag color="warning">错误: {record.error_count}</Tag>}
        </Space>
      ),
    },
    {
      title: '测试时间',
      dataIndex: 'started_at',
      key: 'started_at',
      width: 180,
      render: (time: string, record: TestReport) => (
        <div>
          <div>开始: {new Date(time).toLocaleString('zh-CN')}</div>
          {record.completed_at && (
            <div>完成: {new Date(record.completed_at).toLocaleString('zh-CN')}</div>
          )}
          {record.duration && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              耗时: {record.duration.toFixed(2)}秒
            </Text>
          )}
        </div>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      fixed: 'right',
      render: (_: any, record: TestReport) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewDetail(record.id)}
          >
            查看
          </Button>
          <Popconfirm
            title="确定要删除这个测试报告吗？"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className="testing-page">
      <Card>
        <div className="testing-header">
          <div>
            {onBack && (
              <Button
                type="text"
                icon={<ArrowLeftOutlined />}
                onClick={onBack}
                style={{ marginRight: 8 }}
              >
                返回
              </Button>
            )}
            <Title level={2} style={{ margin: 0, display: 'inline-block' }}>
              自动化测试管理
            </Title>
          </div>
          <Space>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={() => setRunModalVisible(true)}
            >
              运行测试
            </Button>
            <Button icon={<ReloadOutlined />} onClick={() => {
              fetchReports();
              fetchStats();
            }}>
              刷新
            </Button>
          </Space>
        </div>

        {/* 统计信息 */}
        {stats && (
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={6}>
              <Statistic title="总报告数" value={stats.total} />
            </Col>
            <Col span={6}>
              <Statistic
                title="通过"
                value={stats.passed}
                valueStyle={{ color: '#3f8600' }}
                prefix={<CheckCircleOutlined />}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="失败"
                value={stats.failed}
                valueStyle={{ color: '#cf1322' }}
                prefix={<CloseCircleOutlined />}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="运行中"
                value={stats.running}
                valueStyle={{ color: '#1890ff' }}
                prefix={<ClockCircleOutlined />}
              />
            </Col>
          </Row>
        )}

        {/* 测试报告列表 */}
        <Table
          columns={columns}
          dataSource={reports}
          rowKey="id"
          loading={loading}
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条记录`,
          }}
          locale={{
            emptyText: <Empty description="暂无测试报告" />,
          }}
        />
      </Card>

      {/* 运行测试对话框 */}
      <Modal
        title="运行测试"
        open={runModalVisible}
        onOk={handleRunTests}
        onCancel={() => setRunModalVisible(false)}
        confirmLoading={loading}
        okText="开始运行"
        cancelText="取消"
      >
        <div style={{ marginBottom: 16 }}>
          <Text strong>选择测试范围：</Text>
        </div>
        <Checkbox.Group
          options={TEST_SCOPES}
          value={selectedScopes}
          onChange={(values) => setSelectedScopes(values as string[])}
          style={{ width: '100%' }}
        />
      </Modal>

      {/* 测试报告详情对话框 */}
      <Modal
        title="测试报告详情"
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setDetailModalVisible(false)}>
            关闭
          </Button>,
        ]}
        width={800}
      >
        {selectedReport && (
          <Descriptions bordered column={2}>
            <Descriptions.Item label="测试报告 ID" span={2}>
              <Text code>{selectedReport.id}</Text>
            </Descriptions.Item>
            <Descriptions.Item label="测试功能">
              {formatScopes(selectedReport.test_scopes)}
            </Descriptions.Item>
            <Descriptions.Item label="测试状态">
              {getStatusTag(selectedReport.status)}
            </Descriptions.Item>
            <Descriptions.Item label="测试总数">{selectedReport.test_count}</Descriptions.Item>
            <Descriptions.Item label="通过">{selectedReport.passed_count}</Descriptions.Item>
            <Descriptions.Item label="失败">{selectedReport.failed_count}</Descriptions.Item>
            <Descriptions.Item label="错误">{selectedReport.error_count}</Descriptions.Item>
            <Descriptions.Item label="跳过">{selectedReport.skipped_count}</Descriptions.Item>
            <Descriptions.Item label="进度">
              <Progress percent={selectedReport.progress} />
            </Descriptions.Item>
            <Descriptions.Item label="开始时间">
              {new Date(selectedReport.started_at).toLocaleString('zh-CN')}
            </Descriptions.Item>
            {selectedReport.completed_at && (
              <Descriptions.Item label="完成时间">
                {new Date(selectedReport.completed_at).toLocaleString('zh-CN')}
              </Descriptions.Item>
            )}
            {selectedReport.duration && (
              <Descriptions.Item label="耗时">
                {selectedReport.duration.toFixed(2)} 秒
              </Descriptions.Item>
            )}
            {selectedReport.result && (
              <Descriptions.Item label="测试输出" span={2}>
                <pre style={{ maxHeight: 400, overflow: 'auto', background: '#f5f5f5', padding: 12 }}>
                  {selectedReport.result.stdout || '无输出'}
                </pre>
              </Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Modal>
    </div>
  );
};

export default TestingPage;

