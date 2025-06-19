// API Response Types
export interface ApiResponse<T = any> {
  data: T;
  message?: string;
  success: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

// Job Types
export type JobType = 'text_to_audio' | 'book_processing' | 'chapter_multi_voice';
export type JobStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
export type StepStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';

export interface VoiceConfig {
  provider: string;
  voice_id?: string;
  voice_settings?: Record<string, string>;
}

export interface ProcessingConfig {
  max_concurrency?: number;
  [key: string]: any;
}

export interface JobStep {
  id: string;
  name: string;
  status: StepStatus;
  progress?: number;
  error_message?: string;
  started_at?: string;
  completed_at?: string;
  logs?: string[];
}

export interface Job {
  id: string;
  job_type: JobType;
  status: JobStatus;
  title?: string;
  text_length?: number;
  voice_config?: VoiceConfig;
  processing_config?: ProcessingConfig;
  result?: {
    audio_url?: string;
    duration?: number;
    chapters?: Array<{
      id: string;
      title: string;
      audio_url: string;
      duration: number;
    }>;
    [key: string]: any;
  };
  error_message?: string;
  created_at: string;
  updated_at: string;
  steps: JobStep[];
}

export interface JobRequest {
  job_type: JobType;
  content: string;
  title: string;
  voice_config?: VoiceConfig;
  processing_config?: ProcessingConfig;
}

// User Types
export interface User {
  id: string;
  email: string;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
}

export interface AuthResponse {
  user: User;
  access_token: string;
}

// Progress Types
export interface PlaybackProgress {
  job_id: string;
  position: number;
  chapter?: number;
  updated_at: string;
}

export interface UpdateProgressRequest {
  position: number;
  chapter?: number;
}

// Audio Types
export interface AudioMetadata {
  duration: number;
  chapters?: Array<{
    title: string;
    start_time: number;
    duration: number;
  }>;
}

export interface StreamingUrl {
  url: string;
  expires_at: string;
}