import React from 'react';
import { Button, Space, Tooltip } from 'antd';
import {
  LineChartOutlined,
  BarChartOutlined,
  SwapRightOutlined,
  AppstoreOutlined,
  RiseOutlined,
} from '@ant-design/icons';
import './QuickActions.css';

interface QuickActionsProps {
  /** 是否有表格数据 */
  hasTableData: boolean;
  /** 是否有SQL查询 */
  hasSql: boolean;
  /** 是否是最新的助手消息 */
  isLatest: boolean;
  /** 点击快捷操作的回调 */
  onActionClick: (action: string, question: string) => void;
  /** 是否正在加载 */
  isLoading?: boolean;
}

/**
 * 快捷操作组件
 * 
 * 在查询结果下方提供快捷操作按钮，方便用户进行后续分析：
 * - 环比分析：计算环比增长率
 * - 同比分析：计算同比增长率
 * - 对比分析：对比不同时间段或维度
 * - 按维度拆分：按指定维度（渠道、城市等）拆分数据
 * - 趋势预测：基于现有趋势进行预测
 */
export const QuickActions: React.FC<QuickActionsProps> = React.memo(({
  hasTableData,
  hasSql,
  isLatest,
  onActionClick,
  isLoading = false,
}) => {
  // 只在有查询结果且是最新消息时显示快捷操作
  if (!hasTableData || !hasSql || !isLatest || isLoading) {
    return null;
  }

  const actions = [
    {
      key: 'month_over_month',
      label: '环比分析',
      icon: <SwapRightOutlined />,
      question: '帮我做个环比分析',
      tooltip: '计算环比增长率',
    },
    {
      key: 'year_over_year',
      label: '同比分析',
      icon: <RiseOutlined />,
      question: '帮我做个同比分析',
      tooltip: '计算同比增长率',
    },
    {
      key: 'compare',
      label: '对比分析',
      icon: <BarChartOutlined />,
      question: '对比一下不同时间段的数据',
      tooltip: '对比不同时间段或维度',
    },
    {
      key: 'breakdown',
      label: '按维度拆分',
      icon: <AppstoreOutlined />,
      question: '按维度拆分一下数据',
      tooltip: '按渠道、城市等维度拆分',
    },
  ];

  return (
    <div className="quick-actions" style={{ 
      marginTop: 12, 
      padding: '12px 0',
      borderTop: '1px dashed #e0e0e0',
    }}>
      <div style={{ 
        fontSize: 12, 
        color: '#666', 
        marginBottom: 8,
        display: 'flex',
        alignItems: 'center',
        gap: 4,
      }}>
        <LineChartOutlined style={{ fontSize: 14 }} />
        <span>快捷分析：</span>
      </div>
      <Space wrap size="small">
        {actions.map((action) => (
          <Tooltip key={action.key} title={action.tooltip}>
            <Button
              type="dashed"
              size="small"
              icon={action.icon}
              onClick={() => onActionClick(action.key, action.question)}
              disabled={isLoading}
            >
              {action.label}
            </Button>
          </Tooltip>
        ))}
      </Space>
    </div>
  );
});

QuickActions.displayName = 'QuickActions';

