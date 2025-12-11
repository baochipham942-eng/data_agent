import React from 'react';
import { Modal, message, Button, Space } from 'antd';
import { EditOutlined, CopyOutlined, CheckOutlined } from '@ant-design/icons';
import './SqlEditor.css';

interface SqlEditorProps {
  sql: string;
  visible: boolean;
  onClose: () => void;
  onSave: (newSql: string) => void;
}

/**
 * SQL 编辑器组件（简化版）
 * 完整的可视化编辑功能开发中...
 */
export const SqlEditor: React.FC<SqlEditorProps> = ({
  sql,
  visible,
  onClose,
  onSave,
}) => {
  const [copied, setCopied] = React.useState(false);
  const [editedSql, setEditedSql] = React.useState(sql);

  React.useEffect(() => {
    setEditedSql(sql);
  }, [sql]);

  const handleCopy = () => {
    navigator.clipboard.writeText(editedSql);
    setCopied(true);
    message.success('SQL 已复制');
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSave = () => {
    onSave(editedSql);
    message.success('SQL 已更新');
    onClose();
  };

  return (
    <Modal
      title={
        <Space>
          <EditOutlined />
          SQL 编辑器
        </Space>
      }
      open={visible}
      onCancel={onClose}
      width={700}
      footer={[
        <Button key="copy" icon={copied ? <CheckOutlined /> : <CopyOutlined />} onClick={handleCopy}>
          {copied ? '已复制' : '复制'}
        </Button>,
        <Button key="cancel" onClick={onClose}>
          取消
        </Button>,
        <Button key="save" type="primary" icon={<CheckOutlined />} onClick={handleSave}>
          应用
        </Button>,
      ]}
    >
      <div className="sql-editor-content">
        <textarea
          className="sql-textarea"
          value={editedSql}
          onChange={(e) => setEditedSql(e.target.value)}
          style={{
            width: '100%',
            minHeight: '200px',
            fontFamily: 'Monaco, Menlo, monospace',
            fontSize: '13px',
            padding: '12px',
            background: 'var(--color-bg-tertiary)',
            border: '1px solid var(--color-surface-border)',
            borderRadius: 'var(--radius-md)',
            color: 'var(--color-text-primary)',
            resize: 'vertical',
          }}
        />
        <div style={{ marginTop: 12, fontSize: 12, color: 'var(--color-text-muted)' }}>
          提示：可视化编辑功能开发中...
        </div>
      </div>
    </Modal>
  );
};

export default SqlEditor;
