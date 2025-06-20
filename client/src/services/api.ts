import axios, { AxiosInstance } from 'axios';
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface AuthResponse {
  user: UserResponse;
  access_token: string;
  token_type: string;
}
import {
  JobResponse,
  CreateJobRequest,
  PlaybackProgressResponse,
  UpdateProgressRequest,
  StreamingUrlResponse,
  AudioMetadataResponse,
  JobResponseSchema,
  StreamingUrlResponseSchema,
  AudioMetadataResponseSchema,
  JobListResponse,
} from '../schemas';

// Keep these simple types from generated (they work fine)
import {
  UserLogin,
  UserCreate,
  UserResponse,
  Token,
} from '../generated';

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
  async login(credentials: UserLogin): Promise<AuthResponse> {
    const response = await this.client.post<Token>(
      '/api/v1/auth/login',
      credentials
    );

    // Set the token for future requests
    this.setToken(response.data.access_token);

    const user = await this.getCurrentUser();

    return {
      user,
      access_token: response.data.access_token,
      token_type: response.data.token_type,
    };
  }

  async register(userData: UserCreate): Promise<AuthResponse> {
    await this.client.post<UserResponse>(
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

  async getCurrentUser(): Promise<UserResponse> {
    const response = await this.client.get<UserResponse>('/api/v1/auth/me');
    return response.data;
  }

  // Job endpoints
  async createJob(jobData: CreateJobRequest): Promise<JobResponse> {
    const response = await this.client.post<JobResponse>(
      '/api/v1/jobs',
      jobData
    );
    return response.data;
  }

  async getJobs(params?: {
    page?: number;
    limit?: number;
    status?: string;
    job_type?: string;
  }): Promise<PaginatedResponse<JobResponse>> {
    const response = await this.client.get<JobListResponse>(
      '/api/v1/jobs',
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

  async getJob(jobId: string): Promise<JobResponse> {
    const response = await this.client.get<JobResponse>(
      `/api/v1/jobs/${jobId}`
    );
    // Runtime validation with Zod
    return JobResponseSchema.parse(response.data);
  }

  async cancelJob(jobId: string): Promise<void> {
    await this.client.delete(`/api/v1/jobs/${jobId}`);
  }

  async getJobSteps(jobId: string): Promise<JobResponse['steps']> {
    const response = await this.client.get<JobResponse['steps']>(
      `/api/v1/jobs/${jobId}/steps`
    );
    return response.data;
  }

  // Audio endpoints
  async getAudioStream(jobId: string): Promise<StreamingUrlResponse> {
    const response = await this.client.get<StreamingUrlResponse>(
      `/api/v1/audio/${jobId}/stream`
    );
    console.log('getAudioStream raw response:', response.data);
    // Runtime validation with Zod
    const parsed = StreamingUrlResponseSchema.parse(response.data);
    console.log('getAudioStream parsed response:', parsed);
    return parsed;
  }

  async getAudioMetadata(jobId: string): Promise<AudioMetadataResponse> {
    const response = await this.client.get<AudioMetadataResponse>(
      `/api/v1/audio/${jobId}/metadata`
    );
    // Runtime validation with Zod
    return AudioMetadataResponseSchema.parse(response.data);
  }

  async getPlaylist(jobId: string): Promise<string> {
    const response = await this.client.get(`/api/v1/audio/${jobId}/playlist`);
    return response.data;
  }

  // Progress endpoints
  async getProgress(jobId: string): Promise<PlaybackProgressResponse | null> {
    const response = await this.client.get<PlaybackProgressResponse | null>(
      `/api/v1/progress/${jobId}`
    );
    return response.data;
  }

  async updateProgress(
    jobId: string,
    progress: UpdateProgressRequest
  ): Promise<PlaybackProgressResponse> {
    const response = await this.client.put<PlaybackProgressResponse>(
      `/api/v1/progress/${jobId}`,
      progress
    );
    return response.data;
  }

  async resetProgress(jobId: string): Promise<void> {
    await this.client.delete(`/api/v1/progress/${jobId}`);
  }

  async getRecentProgress(): Promise<PlaybackProgressResponse[]> {
    const response = await this.client.get<PlaybackProgressResponse[]>(
      '/api/v1/progress/user/recent'
    );
    return response.data;
  }

  // File upload helper
  async uploadFile(file: File, endpoint: string): Promise<unknown> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await this.client.post(endpoint, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }
}

export const apiClient = new ApiClient();
export default apiClient;
