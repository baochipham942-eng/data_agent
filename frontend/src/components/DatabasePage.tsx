import React, { useState, useEffect, useCallback } from 'react';
import {
  Card,
  Row,
  Col,
  Statistic,
  Table,
  Button,
  Space,
  message,
  Spin,
  Modal,
  Input,
  Tag,
  Tooltip,
  Dropdown,
} from 'antd';
import {
  DatabaseOutlined,
  UploadOutlined,
  ReloadOutlined,
  DeleteOutlined,
  EyeOutlined,
  EditOutlined,
  DownloadOutlined,
  TableOutlined,
  MoreOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import ImportDataModal from './ImportDataModal';
import SettingsPageLayout from './SettingsPageLayout';
import './DatabasePage.css';

interface ColumnInfo {
  name: string;
  dtype: string;
  nullable: boolean;
}

interface TableInfo {
  name: string;
  row_count: number;
  column_count: number;
  size_bytes: number;
  columns: ColumnInfo[];
}

interface DatabaseInfo {
  table_count: number;
  size_bytes: number;
  size_mb: number;
  last_modified: number | null;
  db_path: string;
}

interface DatabasePageProps {
  onBack?: () => void;
}

const DatabasePage: React.FC<DatabasePageProps> = ({ onBack }) => {
  const [loading, setLoading] = useState(true);
  const [dbInfo, setDbInfo] = useState<DatabaseInfo | null>(null);
  const [tables, setTables] = useState<TableInfo[]>([]);
  const [importModalVisible, setImportModalVisible] = useState(false);
  const [previewModalVisible, setPreviewModalVisible] = useState(false);
  const [previewTable, setPreviewTable] = useState<string | null>(null);
  const [previewData, setPreviewData] = useState<any[]>([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [renameModalVisible, setRenameModalVisible] = useState(false);
  const [renameTable, setRenameTable] = useState<string | null>(null);
  const [newTableName, setNewTableName] = useState('');
  const [refreshingSchema, setRefreshingSchema] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [infoRes, tablesRes] = await Promise.all([
        fetch('/api/database/info'),
        fetch('/api/database/tables'),
      ]);
      
      const infoData = await infoRes.json();
      const tablesData = await tablesRes.json();
      
      if (infoData.success) {
        setDbInfo(infoData.data);
      }
      if (tablesData.success) {
        setTables(tablesData.data);
      }
    } catch (error) {
      message.error('加载数据库信息失败');
      console.error(error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handlePreview = async (tableName: string) => {
    setPreviewTable(tableName);
    setPreviewModalVisible(true);
    setPreviewLoading(true);
    
    try {
      const res = await fetch(`/api/database/tables/${encodeURIComponent(tableName)}/preview?limit=100`);
      const data = await res.json();
      if (data.success) {
        setPreviewData(data.data);
      } else {
        message.error('加载预览数据失败');
      }
    } catch (error) {
      message.error('加载预览数据失败');
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleDelete = async (tableName: string) => {
    try {
      const res = await fetch(`/api/database/tables/${encodeURIComponent(tableName)}`, {
        method: 'DELETE',
      });
      const data = await res.json();
      if (data.success) {
        message.success(`已删除表: ${tableName}`);
        loadData();
      } else {
        message.error(data.message || '删除失败');
      }
    } catch (error) {
      message.error('删除失败');
    }
  };

  const handleRename = async () => {
    if (!renameTable || !newTableName.trim()) {
      message.warning('请输入新表名');
      return;
    }
    
    try {
      const res = await fetch(`/api/database/tables/${encodeURIComponent(renameTable)}/rename`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_name: newTableName.trim() }),
      });
      const data = await res.json();
      if (data.success) {
        message.success(`已重命名: ${renameTable} → ${newTableName}`);
        setRenameModalVisible(false);
        setRenameTable(null);
        setNewTableName('');
        loadData();
      } else {
        message.error(data.message || '重命名失败');
      }
    } catch (error) {
      message.error('重命名失败');
    }
  };

  const handleExport = (tableName: string) => {
    window.open(`/api/database/export/${encodeURIComponent(tableName)}`, '_blank');
  };

  const handleRefreshSchema = async () => {
    setRefreshingSchema(true);
    try {
      const res = await fetch('/api/database/refresh-schema', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        message.success(`Schema 刷新完成，更新了 ${data.tables_refreshed} 个表`);
      } else {
        message.error('刷新失败');
      }
    } catch (error) {
      message.error('刷新失败');
    } finally {
      setRefreshingSchema(false);
    }
  };

  const handleImportSuccess = () => {
    setImportModalVisible(false);
    loadData();
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (timestamp: number | null) => {
    if (!timestamp) return '-';
    return new Date(timestamp * 1000).toLocaleString('zh-CN');
  };

  // 生成预览表格的列配置
  const getPreviewColumns = () => {
    if (previewData.length === 0) return [];
    return Object.keys(previewData[0]).map(key => ({
      title: key,
      dataIndex: key,
      key: key,
      ellipsis: true,
      width: 150,
      render: (value: any) => {
        if (value === null || value === undefined) {
          return <span className="null-value">NULL</span>;
        }
        return String(value);
      },
    }));
  };

  const tableColumns = [
    {
      title: '表名',
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => (
        <Space>
          <TableOutlined />
          <span className="table-name">{name}</span>
        </Space>
      ),
    },
    {
      title: '行数',
      dataIndex: 'row_count',
      key: 'row_count',
      width: 100,
      render: (count: number) => count.toLocaleString(),
    },
    {
      title: '字段数',
      dataIndex: 'column_count',
      key: 'column_count',
      width: 80,
    },
    {
      title: '大小',
      dataIndex: 'size_bytes',
      key: 'size_bytes',
      width: 100,
      render: (bytes: number) => formatBytes(bytes),
    },
    {
      title: '字段',
      dataIndex: 'columns',
      key: 'columns',
      width: 300,
      render: (columns: ColumnInfo[]) => (
        <div className="column-tags">
          {columns.slice(0, 5).map((col, idx) => (
            <Tooltip key={idx} title={`${col.name}: ${col.dtype}`}>
              <Tag className="column-tag">{col.name}</Tag>
            </Tooltip>
          ))}
          {columns.length > 5 && (
            <Tag className="column-tag more">+{columns.length - 5}</Tag>
          )}
        </div>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 180,
      render: (_: any, record: TableInfo) => (
        <Space size="small">
          <Tooltip title="预览数据">
            <Button
              type="text"
              size="small"
              icon={<EyeOutlined />}
              onClick={() => handlePreview(record.name)}
            />
          </Tooltip>
          <Tooltip title="导出 CSV">
            <Button
              type="text"
              size="small"
              icon={<DownloadOutlined />}
              onClick={() => handleExport(record.name)}
            />
          </Tooltip>
          <Dropdown
            menu={{
              items: [
                {
                  key: 'rename',
                  icon: <EditOutlined />,
                  label: '重命名',
                  onClick: () => {
                    setRenameTable(record.name);
                    setNewTableName(record.name);
                    setRenameModalVisible(true);
                  },
                },
                {
                  key: 'delete',
                  icon: <DeleteOutlined />,
                  label: '删除',
                  danger: true,
                  onClick: () => {
                    Modal.confirm({
                      title: '确认删除',
                      icon: <ExclamationCircleOutlined />,
                      content: `确定要删除表 "${record.name}" 吗？此操作不可恢复！`,
                      okText: '删除',
                      okType: 'danger',
                      cancelText: '取消',
                      onOk: () => handleDelete(record.name),
                    });
                  },
                },
              ],
            }}
            trigger={['click']}
          >
            <Button type="text" size="small" icon={<MoreOutlined />} />
          </Dropdown>
        </Space>
      ),
    },
  ];

  if (loading) {
    return (
      <SettingsPageLayout
        title="数据库维护"
        icon={<DatabaseOutlined />}
        onBack={onBack || (() => {})}
      >
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}>
          <Spin size="large" tip="加载中..." />
        </div>
      </SettingsPageLayout>
    );
  }

  return (
    <SettingsPageLayout
      title="数据库维护"
      icon={<DatabaseOutlined />}
      onBack={onBack || (() => {})}
      actions={
        <Space>
          <Button
            icon={<ReloadOutlined spin={refreshingSchema} />}
            onClick={handleRefreshSchema}
            loading={refreshingSchema}
          >
            刷新 Schema
          </Button>
          <Button
            type="primary"
            icon={<UploadOutlined />}
            onClick={() => setImportModalVisible(true)}
          >
            导入数据
          </Button>
        </Space>
      }
    >
      {/* 数据概览 */}
      <Row gutter={[16, 16]} className="stats-row">
        <Col xs={24} sm={8}>
          <Card className="stat-card">
            <Statistic
              title="数据表数量"
              value={dbInfo?.table_count || 0}
              prefix={<TableOutlined />}
              suffix="个"
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card className="stat-card">
            <Statistic
              title="数据库大小"
              value={dbInfo?.size_mb || 0}
              prefix={<DatabaseOutlined />}
              suffix="MB"
              precision={2}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card className="stat-card">
            <Statistic
              title="最后更新"
              value={formatDate(dbInfo?.last_modified || null)}
              valueStyle={{ fontSize: '16px' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 表列表 */}
      <Card className="tables-card" title="数据表列表">
        <Table
          dataSource={tables}
          columns={tableColumns}
          rowKey="name"
          pagination={{ pageSize: 10 }}
          size="middle"
          locale={{ emptyText: '暂无数据表' }}
        />
      </Card>

      {/* 导入数据弹窗 */}
      <ImportDataModal
        visible={importModalVisible}
        onCancel={() => setImportModalVisible(false)}
        onSuccess={handleImportSuccess}
      />

      {/* 预览数据弹窗 */}
      <Modal
        title={`预览数据: ${previewTable}`}
        open={previewModalVisible}
        onCancel={() => {
          setPreviewModalVisible(false);
          setPreviewTable(null);
          setPreviewData([]);
        }}
        width={1000}
        footer={null}
        className="preview-modal"
      >
        {previewLoading ? (
          <div className="preview-loading">
            <Spin tip="加载中..." />
          </div>
        ) : (
          <Table
            dataSource={previewData}
            columns={getPreviewColumns()}
            rowKey={(_, index) => String(index)}
            scroll={{ x: 'max-content' }}
            pagination={{ pageSize: 20 }}
            size="small"
          />
        )}
      </Modal>

      {/* 重命名弹窗 */}
      <Modal
        title="重命名表"
        open={renameModalVisible}
        onCancel={() => {
          setRenameModalVisible(false);
          setRenameTable(null);
          setNewTableName('');
        }}
        onOk={handleRename}
        okText="确认"
        cancelText="取消"
      >
        <div className="rename-form">
          <p>原表名: <strong>{renameTable}</strong></p>
          <Input
            placeholder="输入新表名"
            value={newTableName}
            onChange={(e) => setNewTableName(e.target.value)}
            onPressEnter={handleRename}
          />
        </div>
      </Modal>
    </SettingsPageLayout>
  );
};

export default DatabasePage;

