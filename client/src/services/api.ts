import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';
import {
  ApiResponse,
  PaginatedResponse,
  Job,
  JobRequest,
  User,
  LoginRequest,
  RegisterRequest,
  AuthResponse,
  PlaybackProgress,
  UpdateProgressRequest,
  AudioMetadata,
  StreamingUrl
} from '../types/api';

class ApiClient {
  private client: AxiosInstance;
  private baseURL: string;

  constructor() {
    this.baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    
    this.client = axios.create({
      baseURL: this.baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor to add auth token
    this.client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor to handle auth errors
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('access_token');
          localStorage.removeItem('user');
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  setToken(token: string) {
    localStorage.setItem('access_token', token);
  }

  // Authentication endpoints
  async login(credentials: LoginRequest): Promise<AuthResponse> {
    const response = await this.client.post<{access_token: string, token_type: string}>(
      '/api/v1/auth/login',
      credentials
    );
    
    // Set the token for future requests
    this.setToken(response.data.access_token);
    
    // Get user info after login
    const user = await this.getCurrentUser();
    
    return {
      user,
      access_token: response.data.access_token
    };
  }

  async register(userData: RegisterRequest): Promise<AuthResponse> {
    const response = await this.client.post<User>(
      '/api/v1/auth/register',
      userData
    );
    
    // Register doesn't return a token, so login after registration
    const authResponse = await this.login({
      email: userData.email,
      password: userData.password
    });
    
    return authResponse;
  }

  async getCurrentUser(): Promise<User> {
    const response = await this.client.get<User>('/api/v1/auth/me');
    return response.data;
  }

  // Job endpoints
  async createJob(jobData: JobRequest): Promise<Job> {
    const response = await this.client.post<Job>(
      '/api/v1/jobs/',
      jobData
    );
    return response.data;
  }

  async getJobs(params?: {
    page?: number;
    limit?: number;
    status?: string;
    job_type?: string;
  }): Promise<PaginatedResponse<Job>> {
    const response = await this.client.get<{
      jobs: Job[];
      total: number;
      page: number;
      page_size: number;
      total_pages: number;
    }>(
      '/api/v1/jobs/',
      { params }
    );
    
    // Transform backend response to match client interface
    return {
      items: response.data.jobs,
      total: response.data.total,
      page: response.data.page,
      limit: response.data.page_size,
      pages: response.data.total_pages,
    };
  }

  async getJob(jobId: string): Promise<Job> {
    const response = await this.client.get<ApiResponse<Job>>(
      `/api/v1/jobs/${jobId}`
    );
    return response.data.data;
  }

  async cancelJob(jobId: string): Promise<void> {
    await this.client.delete(`/api/v1/jobs/${jobId}`);
  }

  async getJobSteps(jobId: string): Promise<Job['steps']> {
    const response = await this.client.get<ApiResponse<Job['steps']>>(
      `/api/v1/jobs/${jobId}/steps`
    );
    return response.data.data;
  }

  // Audio endpoints
  async getAudioStream(jobId: string): Promise<StreamingUrl> {
    const response = await this.client.get<ApiResponse<StreamingUrl>>(
      `/api/v1/audio/${jobId}/stream`
    );
    return response.data.data;
  }

  async getAudioMetadata(jobId: string): Promise<AudioMetadata> {
    const response = await this.client.get<ApiResponse<AudioMetadata>>(
      `/api/v1/audio/${jobId}/metadata`
    );
    return response.data.data;
  }

  async getPlaylist(jobId: string): Promise<string> {
    const response = await this.client.get(`/api/v1/audio/${jobId}/playlist`);
    return response.data;
  }

  // Progress endpoints
  async getProgress(jobId: string): Promise<PlaybackProgress> {
    const response = await this.client.get<ApiResponse<PlaybackProgress>>(
      `/api/v1/progress/${jobId}`
    );
    return response.data.data;
  }

  async updateProgress(
    jobId: string,
    progress: UpdateProgressRequest
  ): Promise<PlaybackProgress> {
    const response = await this.client.put<ApiResponse<PlaybackProgress>>(
      `/api/v1/progress/${jobId}`,
      progress
    );
    return response.data.data;
  }

  async resetProgress(jobId: string): Promise<void> {
    await this.client.delete(`/api/v1/progress/${jobId}`);
  }

  async getRecentProgress(): Promise<PlaybackProgress[]> {
    const response = await this.client.get<ApiResponse<PlaybackProgress[]>>(
      '/api/v1/progress/user/recent'
    );
    return response.data.data;
  }

  // File upload helper
  async uploadFile(file: File, endpoint: string): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await this.client.post(endpoint, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data.data;
  }
}

export const apiClient = new ApiClient();
export default apiClient;