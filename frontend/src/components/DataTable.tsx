import React, { useMemo } from 'react';
import { Table, Button, Tooltip, message } from 'antd';
import { DownloadOutlined, CopyOutlined, ExpandOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import './DataTable.css';

interface DataTableProps {
  data: Record<string, unknown>[];
  maxRows?: number;
}

export const DataTable: React.FC<DataTableProps> = ({ data, maxRows = 10 }) => {
  const columns: ColumnsType<Record<string, unknown>> = useMemo(() => {
    if (!data || data.length === 0) return [];
    
    const keys = Object.keys(data[0]);
    return keys.map((key) => ({
      title: key,
      dataIndex: key,
      key,
      ellipsis: true,
      render: (value: unknown) => {
        if (value === null || value === undefined) return '-';
        if (typeof value === 'number') {
          return value.toLocaleString();
        }
        return String(value);
      },
    }));
  }, [data]);

  const displayData = useMemo(() => {
    return data.slice(0, maxRows).map((row, index) => ({
      ...row,
      key: index,
    }));
  }, [data, maxRows]);

  const handleCopy = () => {
    const headers = Object.keys(data[0]).join('\t');
    const rows = data.map(row => Object.values(row).join('\t')).join('\n');
    const text = `${headers}\n${rows}`;
    
    navigator.clipboard.writeText(text).then(() => {
      message.success('数据已复制到剪贴板');
    }).catch(() => {
      message.error('复制失败');
    });
  };

  const handleExport = () => {
    const headers = Object.keys(data[0]).join(',');
    const rows = data.map(row => 
      Object.values(row).map(v => 
        typeof v === 'string' && v.includes(',') ? `"${v}"` : v
      ).join(',')
    ).join('\n');
    const csv = `${headers}\n${rows}`;
    
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `data_export_${Date.now()}.csv`;
    link.click();
    URL.revokeObjectURL(url);
    
    message.success('数据已导出');
  };

  if (!data || data.length === 0) return null;

  return (
    <div className="data-table-container">
      <div className="table-header">
        <span className="table-title">
          📊 查询结果 
          <span className="row-count">（共 {data.length} 条）</span>
        </span>
        <div className="table-actions">
          <Tooltip title="复制数据">
            <Button 
              type="text" 
              size="small" 
              icon={<CopyOutlined />} 
              onClick={handleCopy}
            />
          </Tooltip>
          <Tooltip title="导出 CSV">
            <Button 
              type="text" 
              size="small" 
              icon={<DownloadOutlined />} 
              onClick={handleExport}
            />
          </Tooltip>
        </div>
      </div>
      
      <Table
        columns={columns}
        dataSource={displayData}
        pagination={false}
        size="small"
        scroll={{ x: 'max-content' }}
        className="data-table"
      />
      
      {data.length > maxRows && (
        <div className="table-footer">
          <span className="more-rows">
            还有 {data.length - maxRows} 条数据未显示
          </span>
          <Button 
            type="link" 
            size="small" 
            icon={<ExpandOutlined />}
          >
            查看全部
          </Button>
        </div>
      )}
    </div>
  );
};

