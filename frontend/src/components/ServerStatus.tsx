import React, { useEffect, useState, useRef } from 'react';
import { Tooltip, message, Popconfirm } from 'antd';
import { 
  CheckCircleFilled, 
  CloseCircleFilled, 
  LoadingOutlined,
} from '@ant-design/icons';
import { checkServerStatus, startServer, stopServer } from '../utils/api';
import './ServerStatus.css';

export const ServerStatus: React.FC = () => {
  const [status, setStatus] = useState<'running' | 'stopped' | 'starting' | 'checking'>('checking');
  const intervalRef = useRef<number | null>(null);

  const checkStatus = async () => {
    try {
      const result = await checkServerStatus();
      setStatus(result.running ? 'running' : 'stopped');
    } catch {
      setStatus('stopped');
    }
  };

  useEffect(() => {
    checkStatus();
    intervalRef.current = window.setInterval(checkStatus, 5000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  const handleToggle = async () => {
    if (status === 'running') {
      // 停止服务
      try {
        setStatus('starting');
        const result = await stopServer();
        if (result.success) {
          message.success('服务已停止');
          setStatus('stopped');
        } else {
          message.error(result.message || '停止失败');
          checkStatus();
        }
      } catch (error) {
        message.error('停止服务失败');
        checkStatus();
      }
    } else if (status === 'stopped') {
      // 启动服务
      try {
        setStatus('starting');
        const result = await startServer();
        if (result.success) {
          message.success('正在启动服务...');
          // 等待几秒后检查状态
          setTimeout(checkStatus, 3000);
        } else {
          message.error(result.message || '启动失败');
          checkStatus();
        }
      } catch (error) {
        message.error('启动服务失败');
        checkStatus();
      }
    }
  };

  const getStatusIcon = () => {
    switch (status) {
      case 'running':
        return <CheckCircleFilled className="status-icon running" />;
      case 'stopped':
        return <CloseCircleFilled className="status-icon stopped" />;
      case 'starting':
      case 'checking':
        return <LoadingOutlined className="status-icon loading" spin />;
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'running':
        return '服务运行中';
      case 'stopped':
        return '点击启动服务';
      case 'starting':
        return '正在启动...';
      case 'checking':
        return '检查中...';
    }
  };

  const statusClass = `server-status ${status}`;

  if (status === 'running') {
    return (
      <Popconfirm
        title="确定要停止服务吗？"
        onConfirm={handleToggle}
        okText="停止"
        cancelText="取消"
        placement="top"
      >
        <Tooltip title="点击停止服务">
          <button className={statusClass}>
            {getStatusIcon()}
            <span className="status-text">{getStatusText()}</span>
          </button>
        </Tooltip>
      </Popconfirm>
    );
  }

  return (
    <Tooltip title={status === 'stopped' ? '点击启动服务' : ''}>
      <button 
        className={statusClass} 
        onClick={handleToggle}
        disabled={status === 'starting' || status === 'checking'}
      >
        {getStatusIcon()}
        <span className="status-text">{getStatusText()}</span>
      </button>
    </Tooltip>
  );
};

