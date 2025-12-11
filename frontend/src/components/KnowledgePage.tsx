import React, { useState, useEffect, useCallback } from 'react';
import { 
  BookOutlined,
  PlusOutlined,
  DeleteOutlined,
  ReloadOutlined,
  TagOutlined,
  FieldTimeOutlined,
  TableOutlined,
} from '@ant-design/icons';
import { 
  Button, 
  Table, 
  Tabs, 
  Card, 
  Form, 
  Input, 
  message, 
  Popconfirm, 
  Modal,
  Statistic,
  Row,
  Col,
  Select,
  Tag,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { 
  fetchKnowledgeStats,
  fetchBusinessTerms, 
  addBusinessTerm, 
  deleteBusinessTerm,
  fetchFieldMappings,
  addFieldMapping,
  fetchTimeRules,
  deleteTimeRule,
} from '../utils/api';
import SettingsPageLayout from './SettingsPageLayout';
import './KnowledgePage.css';

interface Term {
  id: number;
  keyword: string;
  term_type: string;
  description: string;
  example?: string;
  priority?: number;
  created_at: string;
}

interface FieldMapping {
  id: number;
  alias: string;
  standard_name: string;
  table_name?: string;
  description?: string;
  created_at: string;
}

interface TimeRule {
  id: number;
  keyword: string;
  rule_type: string;
  value: string;
  description?: string;
  created_at: string;
}

interface KnowledgePageProps {
  onBack: () => void;
}

export const KnowledgePage: React.FC<KnowledgePageProps> = ({ onBack }) => {
  const [terms, setTerms] = useState<Term[]>([]);
  const [mappings, setMappings] = useState<FieldMapping[]>([]);
  const [timeRules, setTimeRules] = useState<TimeRule[]>([]);
  const [_stats, setStats] = useState<any>(null); // 预留用于统计展示
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('terms');

  // 弹窗状态
  const [termModalVisible, setTermModalVisible] = useState(false);
  const [mappingModalVisible, setMappingModalVisible] = useState(false);
  const [termForm] = Form.useForm();
  const [mappingForm] = Form.useForm();

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsData, termsData, mappingsData, rulesData] = await Promise.all([
        fetchKnowledgeStats().catch(() => null),
        fetchBusinessTerms().catch(() => []),
        fetchFieldMappings().catch(() => []),
        fetchTimeRules().catch(() => []),
      ]);
      setStats(statsData);
      setTerms(termsData);
      setMappings(mappingsData);
      setTimeRules(rulesData);
    } catch (error) {
      console.error('Failed to load knowledge data:', error);
      message.error('加载数据失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleAddTerm = async (values: any) => {
    try {
      await addBusinessTerm(values);
      message.success('添加成功');
      setTermModalVisible(false);
      termForm.resetFields();
      loadData();
    } catch (error) {
      message.error('添加失败');
    }
  };

  const handleDeleteTerm = async (keyword: string) => {
    try {
      await deleteBusinessTerm(keyword);
      message.success('删除成功');
      loadData();
    } catch (error) {
      message.error('删除失败');
    }
  };

  const handleAddMapping = async (values: any) => {
    try {
      await addFieldMapping(values);
      message.success('添加成功');
      setMappingModalVisible(false);
      mappingForm.resetFields();
      loadData();
    } catch (error) {
      message.error('添加失败');
    }
  };

  const handleDeleteTimeRule = async (keyword: string) => {
    try {
      await deleteTimeRule(keyword);
      message.success('删除成功');
      loadData();
    } catch (error) {
      message.error('删除失败');
    }
  };

  const termColumns: ColumnsType<Term> = [
    {
      title: '关键词',
      dataIndex: 'keyword',
      key: 'keyword',
      width: 150,
      render: (text) => <Tag color="blue">{text}</Tag>,
    },
    {
      title: '类型',
      dataIndex: 'term_type',
      key: 'term_type',
      width: 100,
      render: (type) => {
        const colors: Record<string, string> = {
          metric: 'green',
          dimension: 'purple',
          filter: 'orange',
          entity: 'cyan',
        };
        return <Tag color={colors[type] || 'default'}>{type}</Tag>;
      },
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '示例',
      dataIndex: 'example',
      key: 'example',
      width: 150,
      ellipsis: true,
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_, record) => (
        <Popconfirm
          title="确定删除？"
          onConfirm={() => handleDeleteTerm(record.keyword)}
        >
          <Button type="text" danger size="small" icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ];

  const mappingColumns: ColumnsType<FieldMapping> = [
    {
      title: '别名',
      dataIndex: 'alias',
      key: 'alias',
      width: 150,
      render: (text) => <Tag color="orange">{text}</Tag>,
    },
    {
      title: '标准字段名',
      dataIndex: 'standard_name',
      key: 'standard_name',
      width: 150,
      render: (text) => <code style={{ color: '#52c41a' }}>{text}</code>,
    },
    {
      title: '所属表',
      dataIndex: 'table_name',
      key: 'table_name',
      width: 150,
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
  ];

  const timeRuleColumns: ColumnsType<TimeRule> = [
    {
      title: '关键词',
      dataIndex: 'keyword',
      key: 'keyword',
      width: 150,
      render: (text) => <Tag color="purple">{text}</Tag>,
    },
    {
      title: '规则类型',
      dataIndex: 'rule_type',
      key: 'rule_type',
      width: 120,
    },
    {
      title: '值',
      dataIndex: 'value',
      key: 'value',
      width: 200,
      render: (text) => <code>{text}</code>,
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_, record) => (
        <Popconfirm
          title="确定删除？"
          onConfirm={() => handleDeleteTimeRule(record.keyword)}
        >
          <Button type="text" danger size="small" icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ];

  const tabItems = [
    {
      key: 'terms',
      label: (
        <span>
          <TagOutlined />
          业务术语 ({terms.length})
        </span>
      ),
      children: (
        <div>
          <div style={{ marginBottom: 16 }}>
            <Button 
              type="primary" 
              icon={<PlusOutlined />}
              onClick={() => setTermModalVisible(true)}
            >
              添加术语
            </Button>
          </div>
          <Table
            columns={termColumns}
            dataSource={terms}
            rowKey="id"
            loading={loading}
            pagination={{ pageSize: 10, showSizeChanger: true, pageSizeOptions: ['10', '20', '50'] }}
            size="middle"
          />
        </div>
      ),
    },
    {
      key: 'mappings',
      label: (
        <span>
          <TableOutlined />
          字段映射 ({mappings.length})
        </span>
      ),
      children: (
        <div>
          <div style={{ marginBottom: 16 }}>
            <Button 
              type="primary" 
              icon={<PlusOutlined />}
              onClick={() => setMappingModalVisible(true)}
            >
              添加映射
            </Button>
          </div>
          <Table
            columns={mappingColumns}
            dataSource={mappings}
            rowKey="id"
            loading={loading}
            pagination={{ pageSize: 10, showSizeChanger: true, pageSizeOptions: ['10', '20', '50'] }}
            size="middle"
          />
        </div>
      ),
    },
    {
      key: 'timeRules',
      label: (
        <span>
          <FieldTimeOutlined />
          时间规则 ({timeRules.length})
        </span>
      ),
      children: (
        <Table
          columns={timeRuleColumns}
          dataSource={timeRules}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10, showSizeChanger: true, pageSizeOptions: ['10', '20', '50'] }}
          size="middle"
        />
      ),
    },
  ];

  return (
    <SettingsPageLayout
      title="业务知识库"
      icon={<BookOutlined />}
      onBack={onBack}
      actions={
        <Button icon={<ReloadOutlined />} onClick={loadData} loading={loading}>
          刷新
        </Button>
      }
    >
      {/* 统计卡片 */}
      <Row gutter={16} className="stats-row" style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card>
            <Statistic
              title="业务术语"
              value={terms.length}
              prefix={<TagOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="字段映射"
              value={mappings.length}
              prefix={<TableOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="时间规则"
              value={timeRules.length}
              prefix={<FieldTimeOutlined />}
              valueStyle={{ color: '#722ed1' }}
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

      {/* 添加术语弹窗 */}
      <Modal
        title="添加业务术语"
        open={termModalVisible}
        onCancel={() => setTermModalVisible(false)}
        onOk={() => termForm.submit()}
      >
        <Form form={termForm} layout="vertical" onFinish={handleAddTerm}>
          <Form.Item
            name="keyword"
            label="关键词"
            rules={[{ required: true, message: '请输入关键词' }]}
          >
            <Input placeholder="如：日活、GMV、转化率" />
          </Form.Item>
          <Form.Item
            name="term_type"
            label="类型"
            rules={[{ required: true, message: '请选择类型' }]}
          >
            <Select placeholder="选择类型">
              <Select.Option value="metric">指标 (metric)</Select.Option>
              <Select.Option value="dimension">维度 (dimension)</Select.Option>
              <Select.Option value="filter">过滤条件 (filter)</Select.Option>
              <Select.Option value="entity">实体 (entity)</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item
            name="description"
            label="描述"
            rules={[{ required: true, message: '请输入描述' }]}
          >
            <Input.TextArea rows={3} placeholder="详细描述该术语的含义和用途" />
          </Form.Item>
          <Form.Item name="example" label="示例">
            <Input placeholder="使用示例" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 添加字段映射弹窗 */}
      <Modal
        title="添加字段映射"
        open={mappingModalVisible}
        onCancel={() => setMappingModalVisible(false)}
        onOk={() => mappingForm.submit()}
      >
        <Form form={mappingForm} layout="vertical" onFinish={handleAddMapping}>
          <Form.Item
            name="alias"
            label="别名"
            rules={[{ required: true, message: '请输入别名' }]}
          >
            <Input placeholder="用户常用的字段名称" />
          </Form.Item>
          <Form.Item
            name="standard_name"
            label="标准字段名"
            rules={[{ required: true, message: '请输入标准字段名' }]}
          >
            <Input placeholder="数据库中的实际字段名" />
          </Form.Item>
          <Form.Item name="table_name" label="所属表">
            <Input placeholder="字段所属的表名" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="描述该映射" />
          </Form.Item>
        </Form>
      </Modal>
    </SettingsPageLayout>
  );
};

export default KnowledgePage;
