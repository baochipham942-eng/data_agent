import React, { useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { Segmented, Button } from 'antd';
import { 
  LineChartOutlined, 
  BarChartOutlined, 
  PieChartOutlined,
  ExpandOutlined,
  CompressOutlined,
} from '@ant-design/icons';
import './AutoChart.css';

interface AutoChartProps {
  data: Record<string, unknown>[];
  title?: string;
}

type ChartType = 'bar' | 'line' | 'pie';

export const AutoChart: React.FC<AutoChartProps> = ({ data, title }) => {
  const [chartType, setChartType] = useState<ChartType>('bar');
  const [expanded, setExpanded] = useState(false);

  const { xKey, yKey, xData, yData } = useMemo(() => {
    if (!data || data.length === 0) {
      return { xKey: '', yKey: '', xData: [], yData: [] };
    }

    const keys = Object.keys(data[0]);
    // 第一列作为X轴（维度），第二列作为Y轴（指标）
    const xKey = keys[0];
    const yKey = keys.length > 1 ? keys[1] : keys[0];

    const xData = data.map(row => String(row[xKey] ?? ''));
    const yData = data.map(row => {
      const val = row[yKey];
      if (typeof val === 'number') return val;
      if (typeof val === 'string') return parseFloat(val) || 0;
      return 0;
    });

    return { xKey, yKey, xData, yData };
  }, [data]);

  // 自动判断推荐的图表类型
  const recommendedType = useMemo(() => {
    if (!data || data.length === 0) return 'bar';
    
    // 如果数据量少于等于6条且是分类数据，推荐饼图
    if (data.length <= 6) return 'pie';
    
    // 如果X轴包含日期格式，推荐折线图
    if (xData.some(x => x.match(/\d{4}-\d{2}-\d{2}/) || x.match(/\d{2}[/-]\d{2}/))) {
      return 'line';
    }
    
    return 'bar';
  }, [data, xData]);

  // 初始化使用推荐类型
  React.useEffect(() => {
    setChartType(recommendedType);
  }, [recommendedType]);

  const option = useMemo(() => {
    if (!data || data.length === 0) return null;

    const baseOption = {
      backgroundColor: 'transparent',
      title: {
        text: title || yKey,
        textStyle: {
          color: '#e6edf3',
          fontSize: 14,
          fontWeight: 500,
        },
        left: 'center',
        top: 10,
      },
      tooltip: {
        trigger: chartType === 'pie' ? 'item' : 'axis',
        backgroundColor: 'rgba(15, 20, 25, 0.95)',
        borderColor: 'rgba(88, 166, 255, 0.3)',
        borderWidth: 1,
        textStyle: {
          color: '#e6edf3',
        },
        formatter: chartType === 'pie' 
          ? '{b}: {c} ({d}%)' 
          : undefined,
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '15%',
        top: 60,
        containLabel: true,
      },
    };

    if (chartType === 'pie') {
      return {
        ...baseOption,
        series: [{
          type: 'pie',
          radius: ['40%', '70%'],
          center: ['50%', '55%'],
          data: data.map(row => ({
            name: String(row[xKey] ?? ''),
            value: typeof row[yKey] === 'number' 
              ? row[yKey] 
              : parseFloat(String(row[yKey])) || 0,
          })),
          label: {
            color: '#8b949e',
            fontSize: 12,
            formatter: '{b}: {d}%',
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.5)',
            },
          },
        }],
        color: ['#58a6ff', '#3fb950', '#d29922', '#f85149', '#a371f7', '#8b949e', '#79c0ff', '#56d4dd'],
      };
    }

    if (chartType === 'line') {
      return {
        ...baseOption,
        xAxis: {
          type: 'category',
          data: xData,
          axisLine: { lineStyle: { color: '#30363d' } },
          axisLabel: { 
            color: '#8b949e', 
            fontSize: 11,
            rotate: xData.length > 8 ? 45 : 0,
          },
        },
        yAxis: {
          type: 'value',
          axisLine: { lineStyle: { color: '#30363d' } },
          axisLabel: { color: '#8b949e', fontSize: 11 },
          splitLine: { lineStyle: { color: '#21262d' } },
        },
        series: [{
          type: 'line',
          data: yData,
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: {
            width: 3,
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 1, y2: 0,
              colorStops: [
                { offset: 0, color: '#58a6ff' },
                { offset: 1, color: '#a855f7' },
              ],
            },
          },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(88, 166, 255, 0.3)' },
                { offset: 1, color: 'rgba(88, 166, 255, 0)' },
              ],
            },
          },
          itemStyle: {
            color: '#58a6ff',
            borderColor: '#0a0e14',
            borderWidth: 2,
          },
        }],
      };
    }

    // 默认柱状图
    return {
      ...baseOption,
      xAxis: {
        type: 'category',
        data: xData,
        axisLine: { lineStyle: { color: '#30363d' } },
        axisLabel: { 
          color: '#8b949e', 
          fontSize: 11,
          rotate: xData.length > 6 ? 45 : 0,
          interval: 0,
        },
      },
      yAxis: {
        type: 'value',
        axisLine: { lineStyle: { color: '#30363d' } },
        axisLabel: { color: '#8b949e', fontSize: 11 },
        splitLine: { lineStyle: { color: '#21262d' } },
      },
      series: [{
        type: 'bar',
        data: yData,
        barWidth: '60%',
        itemStyle: {
          borderRadius: [4, 4, 0, 0],
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: '#58a6ff' },
              { offset: 1, color: '#3b82f6' },
            ],
          },
        },
        emphasis: {
          itemStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: '#79c0ff' },
                { offset: 1, color: '#58a6ff' },
              ],
            },
          },
        },
      }],
    };
  }, [data, chartType, xKey, yKey, xData, yData, title]);

  if (!data || data.length === 0 || !option) return null;

  return (
    <div className={`auto-chart-container ${expanded ? 'expanded' : ''}`}>
      <div className="chart-toolbar">
        <Segmented
          size="small"
          value={chartType}
          onChange={(value) => setChartType(value as ChartType)}
          options={[
            { value: 'bar', icon: <BarChartOutlined /> },
            { value: 'line', icon: <LineChartOutlined /> },
            { value: 'pie', icon: <PieChartOutlined /> },
          ]}
        />
        <Button 
          type="text" 
          size="small" 
          icon={expanded ? <CompressOutlined /> : <ExpandOutlined />}
          onClick={() => setExpanded(!expanded)}
        />
      </div>
      <ReactECharts
        option={option}
        style={{ height: expanded ? '400px' : '280px', width: '100%' }}
        opts={{ renderer: 'canvas' }}
      />
    </div>
  );
};

