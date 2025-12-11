import React, { useState } from 'react';
import { Button, Tooltip, message } from 'antd';
import { CopyOutlined, CheckOutlined, CodeOutlined } from '@ant-design/icons';
import './SqlBlock.css';

interface SqlBlockProps {
  sql: string;
}

export const SqlBlock: React.FC<SqlBlockProps> = ({ sql }) => {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(sql).then(() => {
      setCopied(true);
      message.success('SQL 已复制到剪贴板');
      setTimeout(() => setCopied(false), 2000);
    }).catch(() => {
      message.error('复制失败');
    });
  };

  const formatSql = (sql: string) => {
    // 简单的 SQL 格式化
    return sql
      .replace(/\bSELECT\b/gi, 'SELECT')
      .replace(/\bFROM\b/gi, '\nFROM')
      .replace(/\bWHERE\b/gi, '\nWHERE')
      .replace(/\bGROUP BY\b/gi, '\nGROUP BY')
      .replace(/\bORDER BY\b/gi, '\nORDER BY')
      .replace(/\bLIMIT\b/gi, '\nLIMIT')
      .replace(/\bJOIN\b/gi, '\nJOIN')
      .replace(/\bLEFT JOIN\b/gi, '\nLEFT JOIN')
      .replace(/\bRIGHT JOIN\b/gi, '\nRIGHT JOIN')
      .replace(/\bINNER JOIN\b/gi, '\nINNER JOIN')
      .replace(/\bAND\b/gi, '\n  AND')
      .replace(/\bOR\b/gi, '\n  OR');
  };

  const displaySql = expanded ? formatSql(sql) : sql;
  const isLong = sql.length > 100;

  return (
    <div className="sql-block">
      <div className="sql-header">
        <span className="sql-title">
          <CodeOutlined /> SQL 查询
        </span>
        <div className="sql-actions">
          {isLong && (
            <Tooltip title={expanded ? '收起' : '展开'}>
              <Button
                type="text"
                size="small"
                onClick={() => setExpanded(!expanded)}
              >
                {expanded ? '收起' : '展开'}
              </Button>
            </Tooltip>
          )}
          <Tooltip title="复制 SQL">
            <Button
              type="text"
              size="small"
              icon={copied ? <CheckOutlined /> : <CopyOutlined />}
              onClick={handleCopy}
              className={copied ? 'copied' : ''}
            />
          </Tooltip>
        </div>
      </div>
      <pre className={`sql-code ${expanded ? 'expanded' : ''}`}>
        <code>{displaySql}</code>
      </pre>
    </div>
  );
};

