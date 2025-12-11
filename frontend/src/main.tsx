import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ConfigProvider, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: '#58a6ff',
          colorBgContainer: '#0f1419',
          colorBgElevated: '#1a222e',
          colorBorder: 'rgba(59, 130, 246, 0.15)',
          colorText: '#e6edf3',
          colorTextSecondary: '#8b949e',
          borderRadius: 10,
          fontFamily: "'Noto Sans SC', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        },
        components: {
          Button: {
            primaryColor: '#58a6ff',
          },
          Input: {
            colorBgContainer: '#151b23',
            colorBorder: 'rgba(59, 130, 246, 0.2)',
            activeBorderColor: '#58a6ff',
            hoverBorderColor: '#58a6ff',
          },
          Table: {
            colorBgContainer: '#0f1419',
            headerBg: '#151b23',
            rowHoverBg: '#1a222e',
          },
        },
      }}
    >
      <App />
    </ConfigProvider>
  </StrictMode>,
)
