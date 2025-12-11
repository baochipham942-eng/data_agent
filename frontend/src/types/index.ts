export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sql?: string;
  tableData?: Record<string, unknown>[];
  chartData?: ChartData;
  tools?: string[];
  reasoning?: ReasoningStep[];
  isStreaming?: boolean;
}

export interface ReasoningStep {
  number: number;
  text: string;
  status?: 'pending' | 'running' | 'done';
  detail?: string; // 详细思考内容
  startTime?: number;
}

export interface ChartData {
  type: 'line' | 'bar' | 'pie' | 'scatter';
  data: unknown[];
  xKey?: string;
  yKey?: string;
  title?: string;
}

export interface Conversation {
  id: string;
  summary: string;
  time: string;
  user_id?: string;
}

export interface SSEMessage {
  type?: string;
  text?: string;
  display_text?: string;
  rich?: {
    type: string;
    data: unknown;
  };
}

export interface ServerStatus {
  running: boolean;
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

