import React from 'react';
import { 
  LineChartOutlined, 
  PieChartOutlined, 
  BarChartOutlined,
  TableOutlined,
  ThunderboltOutlined,
  RocketOutlined,
} from '@ant-design/icons';
import './WelcomeScreen.css';

interface WelcomeScreenProps {
  onExampleClick: (question: string) => void;
}

const exampleQuestions = [
  {
    icon: <LineChartOutlined />,
    question: '最近7天按日期统计访问量的变化趋势',
    category: '趋势分析',
  },
  {
    icon: <BarChartOutlined />,
    question: '显示各省份的访问量排名 Top 10',
    category: '排名对比',
  },
  {
    icon: <PieChartOutlined />,
    question: '各渠道来源的访问量占比分布',
    category: '占比分析',
  },
  {
    icon: <TableOutlined />,
    question: '查询访问量最高的 20 个页面',
    category: '数据查询',
  },
];

const capabilities = [
  { icon: <ThunderboltOutlined />, text: '自然语言转 SQL' },
  { icon: <BarChartOutlined />, text: '智能数据可视化' },
  { icon: <RocketOutlined />, text: '实时流式响应' },
];

export const WelcomeScreen: React.FC<WelcomeScreenProps> = ({ onExampleClick }) => {
  return (
    <div className="welcome-screen">
      <div className="welcome-hero">
        <div className="hero-icon">
          <span className="hero-emoji">🚀</span>
        </div>
        <h2 className="welcome-title">开始探索您的数据</h2>
        <p className="welcome-description">
          用自然语言提问，我会帮您分析数据、生成图表
        </p>
        
        <div className="capabilities">
          {capabilities.map((cap, idx) => (
            <span key={idx} className="capability-item">
              {cap.icon}
              <span>{cap.text}</span>
            </span>
          ))}
        </div>
      </div>

      <div className="example-section">
        <h3 className="example-title">✨ 试试这些问题</h3>
        <div className="example-grid">
          {exampleQuestions.map((item, idx) => (
            <button
              key={idx}
              className="example-card"
              onClick={() => onExampleClick(item.question)}
            >
              <div className="example-icon">{item.icon}</div>
              <div className="example-content">
                <span className="example-category">{item.category}</span>
                <span className="example-text">{item.question}</span>
              </div>
              <div className="example-arrow">→</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

