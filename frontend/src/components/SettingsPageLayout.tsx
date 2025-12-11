import React from 'react';
import { ArrowLeftOutlined } from '@ant-design/icons';
import './SettingsPageLayout.css';

interface SettingsPageLayoutProps {
  title: string;
  icon?: React.ReactNode;
  onBack: () => void;
  actions?: React.ReactNode;
  children: React.ReactNode;
}

export const SettingsPageLayout: React.FC<SettingsPageLayoutProps> = ({
  title,
  icon,
  onBack,
  actions,
  children,
}) => {
  return (
    <div className="settings-page-layout">
      <header className="settings-page-header">
        <div className="header-left">
          <button className="back-btn" onClick={onBack}>
            <ArrowLeftOutlined />
            <span>返回</span>
          </button>
          <div className="page-title">
            {icon && <span className="title-icon">{icon}</span>}
            <h1>{title}</h1>
          </div>
        </div>
        {actions && <div className="header-actions">{actions}</div>}
      </header>
      <main className="settings-page-content">
        {children}
      </main>
    </div>
  );
};

export default SettingsPageLayout;









