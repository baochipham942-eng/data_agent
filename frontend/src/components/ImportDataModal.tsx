import React, { useState, useCallback } from 'react';
import {
  Modal,
  Upload,
  Steps,
  Table,
  Input,
  Radio,
  Button,
  Space,
  message,
  Tag,
  Spin,
} from 'antd';
import {
  InboxOutlined,
  FileExcelOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  LoadingOutlined,
} from '@ant-design/icons';
import type { UploadProps, RadioChangeEvent } from 'antd';
import './ImportDataModal.css';

const { Dragger } = Upload;

interface ColumnPreview {
  name: string;
  dtype: string;
  nullable: boolean;
  sample_values: any[];
}

interface ParseResult {
  filename: string;
  columns: ColumnPreview[];
  row_count: number;
  preview_data: Record<string, any>[];
  inferred_types: Record<string, string>;
}

interface ImportDataModalProps {
  visible: boolean;
  onCancel: () => void;
  onSuccess: () => void;
}

type ImportMode = 'create' | 'replace' | 'append';

const ImportDataModal: React.FC<ImportDataModalProps> = ({
  visible,
  onCancel,
  onSuccess,
}) => {
  const [currentStep, setCurrentStep] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const [parseResult, setParseResult] = useState<ParseResult | null>(null);
  const [tableName, setTableName] = useState('');
  const [importMode, setImportMode] = useState<ImportMode>('replace');
  const [parsing, setParsing] = useState(false);
  const [importing, setImporting] = useState(false);

  const resetState = useCallback(() => {
    setCurrentStep(0);
    setFile(null);
    setParseResult(null);
    setTableName('');
    setImportMode('replace');
    setParsing(false);
    setImporting(false);
  }, []);

  const handleCancel = () => {
    resetState();
    onCancel();
  };

  const handleFileSelect = async (selectedFile: File) => {
    setFile(selectedFile);
    setParsing(true);
    
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      
      const res = await fetch('/api/database/upload', {
        method: 'POST',
        body: formData,
      });
      
      const data = await res.json();
      
      if (data.success) {
        setParseResult(data.data);
        // 默认表名使用文件名（去除扩展名）
        const defaultName = selectedFile.name.replace(/\.(csv|xlsx|xls)$/i, '');
        setTableName(defaultName.replace(/[^\w]/g, '_'));
        setCurrentStep(1);
      } else {
        message.error(data.detail || '文件解析失败');
        setFile(null);
      }
    } catch (error) {
      message.error('文件解析失败');
      setFile(null);
    } finally {
      setParsing(false);
    }
  };

  const uploadProps: UploadProps = {
    name: 'file',
    multiple: false,
    accept: '.csv,.xlsx,.xls',
    showUploadList: false,
    beforeUpload: (file) => {
      // 检查文件大小（50MB）
      if (file.size > 50 * 1024 * 1024) {
        message.error('文件过大，最大支持 50MB');
        return false;
      }
      handleFileSelect(file);
      return false;
    },
  };

  const handleImport = async () => {
    if (!file || !tableName.trim()) {
      message.warning('请填写表名');
      return;
    }
    
    setImporting(true);
    
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('table_name', tableName.trim());
      formData.append('mode', importMode);
      
      const res = await fetch('/api/database/import', {
        method: 'POST',
        body: formData,
      });
      
      const data = await res.json();
      
      if (data.success) {
        message.success(data.data.message);
        resetState();
        onSuccess();
      } else {
        message.error(data.detail || '导入失败');
      }
    } catch (error) {
      message.error('导入失败');
    } finally {
      setImporting(false);
    }
  };

  const getFileIcon = (filename: string) => {
    if (filename.endsWith('.csv')) {
      return <FileTextOutlined style={{ fontSize: 32, color: '#52c41a' }} />;
    }
    return <FileExcelOutlined style={{ fontSize: 32, color: '#1890ff' }} />;
  };

  // 预览表格列配置
  const getPreviewColumns = () => {
    if (!parseResult) return [];
    return parseResult.columns.map(col => ({
      title: (
        <div className="column-header">
          <span className="column-name">{col.name}</span>
          <Tag className="column-type">{col.dtype}</Tag>
        </div>
      ),
      dataIndex: col.name,
      key: col.name,
      width: 150,
      ellipsis: true,
      render: (value: any) => {
        if (value === null || value === undefined) {
          return <span className="null-value">NULL</span>;
        }
        return String(value);
      },
    }));
  };

  const renderStep0 = () => (
    <div className="step-content">
      <Dragger {...uploadProps} disabled={parsing}>
        {parsing ? (
          <div className="upload-parsing">
            <Spin indicator={<LoadingOutlined style={{ fontSize: 32 }} spin />} />
            <p>解析文件中...</p>
          </div>
        ) : (
          <>
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">点击或拖拽文件到此处上传</p>
            <p className="ant-upload-hint">
              支持 .csv, .xlsx, .xls 格式，最大 50MB
            </p>
          </>
        )}
      </Dragger>
    </div>
  );

  const renderStep1 = () => (
    <div className="step-content">
      {/* 文件信息 */}
      {file && (
        <div className="file-info">
          {getFileIcon(file.name)}
          <div className="file-details">
            <div className="file-name">{file.name}</div>
            <div className="file-meta">
              {parseResult && (
                <>
                  <span>{parseResult.row_count.toLocaleString()} 行</span>
                  <span className="separator">·</span>
                  <span>{parseResult.columns.length} 列</span>
                </>
              )}
            </div>
          </div>
          <Button size="small" onClick={() => {
            setFile(null);
            setParseResult(null);
            setCurrentStep(0);
          }}>
            重新选择
          </Button>
        </div>
      )}

      {/* 表名设置 */}
      <div className="form-section">
        <label>目标表名</label>
        <Input
          placeholder="输入表名"
          value={tableName}
          onChange={(e) => setTableName(e.target.value)}
          style={{ width: '100%' }}
        />
      </div>

      {/* 导入模式 */}
      <div className="form-section">
        <label>导入模式</label>
        <Radio.Group
          value={importMode}
          onChange={(e: RadioChangeEvent) => setImportMode(e.target.value)}
        >
          <Space direction="vertical">
            <Radio value="create">
              <span className="radio-label">新建表</span>
              <span className="radio-desc">如果表已存在会报错</span>
            </Radio>
            <Radio value="replace">
              <span className="radio-label">覆盖表</span>
              <span className="radio-desc">删除现有表后重建</span>
            </Radio>
            <Radio value="append">
              <span className="radio-label">追加数据</span>
              <span className="radio-desc">添加到现有表末尾</span>
            </Radio>
          </Space>
        </Radio.Group>
      </div>

      {/* 数据预览 */}
      {parseResult && (
        <div className="form-section">
          <label>数据预览 (前 10 行)</label>
          <div className="preview-table-wrapper">
            <Table
              dataSource={parseResult.preview_data}
              columns={getPreviewColumns()}
              rowKey={(_, index) => String(index)}
              scroll={{ x: 'max-content' }}
              pagination={false}
              size="small"
            />
          </div>
        </div>
      )}

      {/* 列类型信息 */}
      {parseResult && (
        <div className="form-section">
          <label>字段类型推断</label>
          <div className="column-types">
            {parseResult.columns.map((col, idx) => (
              <div key={idx} className="column-type-item">
                <span className="col-name">{col.name}</span>
                <Tag color={col.dtype === 'TEXT' ? 'blue' : col.dtype === 'INTEGER' ? 'green' : 'orange'}>
                  {col.dtype}
                </Tag>
                {col.nullable && <Tag color="default">可空</Tag>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  const steps = [
    { title: '选择文件', icon: currentStep > 0 ? <CheckCircleOutlined /> : undefined },
    { title: '配置导入', icon: currentStep > 1 ? <CheckCircleOutlined /> : undefined },
  ];

  return (
    <Modal
      title="导入数据"
      open={visible}
      onCancel={handleCancel}
      width={800}
      className="import-modal"
      footer={
        <Space>
          <Button onClick={handleCancel}>取消</Button>
          {currentStep === 1 && (
            <Button
              type="primary"
              onClick={handleImport}
              loading={importing}
              disabled={!tableName.trim()}
            >
              确认导入
            </Button>
          )}
        </Space>
      }
    >
      <Steps current={currentStep} items={steps} className="import-steps" />
      
      {currentStep === 0 && renderStep0()}
      {currentStep === 1 && renderStep1()}
    </Modal>
  );
};

export default ImportDataModal;

