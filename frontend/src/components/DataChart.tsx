import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import type { ChartData } from '../types';
import './DataChart.css';

interface DataChartProps {
  data: ChartData;
}

export const DataChart: React.FC<DataChartProps> = ({ data }) => {
  const option = useMemo(() => {
    if (!data || !data.data || data.data.length === 0) return null;

    const chartData = data.data as Record<string, unknown>[];
    const keys = Object.keys(chartData[0]);
    const xKey = data.xKey || keys[0];
    const yKey = data.yKey || keys[1];

    const xData = chartData.map(row => row[xKey]);
    const yData = chartData.map(row => {
      const val = row[yKey];
      return typeof val === 'string' ? parseFloat(val) || 0 : val;
    });

    const baseOption = {
      backgroundColor: 'transparent',
      title: {
        text: data.title || yKey,
        textStyle: {
          color: '#e6edf3',
          fontSize: 14,
          fontWeight: 500,
        },
        left: 'center',
        top: 10,
      },
      tooltip: {
        trigger: data.type === 'pie' ? 'item' : 'axis',
        backgroundColor: 'rgba(15, 20, 25, 0.95)',
        borderColor: 'rgba(88, 166, 255, 0.3)',
        borderWidth: 1,
        textStyle: {
          color: '#e6edf3',
        },
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        top: 60,
        containLabel: true,
      },
    };

    switch (data.type) {
      case 'pie':
        return {
          ...baseOption,
          series: [{
            type: 'pie',
            radius: ['40%', '70%'],
            center: ['50%', '55%'],
            data: chartData.map(row => ({
              name: String(row[xKey]),
              value: typeof row[yKey] === 'number' ? row[yKey] : parseFloat(String(row[yKey])) || 0,
            })),
            label: {
              color: '#8b949e',
              fontSize: 12,
            },
            emphasis: {
              itemStyle: {
                shadowBlur: 10,
                shadowOffsetX: 0,
                shadowColor: 'rgba(0, 0, 0, 0.5)',
              },
            },
          }],
          color: ['#58a6ff', '#3fb950', '#d29922', '#f85149', '#a371f7', '#8b949e'],
        };

      case 'line':
        return {
          ...baseOption,
          xAxis: {
            type: 'category',
            data: xData,
            axisLine: { lineStyle: { color: '#30363d' } },
            axisLabel: { color: '#8b949e', fontSize: 11 },
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
            symbolSize: 8,
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
              borderColor: '#fff',
              borderWidth: 2,
            },
          }],
        };

      case 'scatter':
        return {
          ...baseOption,
          xAxis: {
            type: 'category',
            data: xData,
            axisLine: { lineStyle: { color: '#30363d' } },
            axisLabel: { color: '#8b949e', fontSize: 11, rotate: 45 },
          },
          yAxis: {
            type: 'value',
            axisLine: { lineStyle: { color: '#30363d' } },
            axisLabel: { color: '#8b949e', fontSize: 11 },
            splitLine: { lineStyle: { color: '#21262d' } },
          },
          series: [{
            type: 'scatter',
            data: yData,
            symbolSize: 12,
            itemStyle: {
              color: '#58a6ff',
            },
          }],
        };

      case 'bar':
      default:
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
    }
  }, [data]);

  if (!option) return null;

  return (
    <div className="data-chart-container">
      <ReactECharts
        option={option}
        style={{ height: '300px', width: '100%' }}
        opts={{ renderer: 'canvas' }}
      />
    </div>
  );
};

