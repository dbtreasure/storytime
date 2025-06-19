import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { Job, JobRequest, PaginatedResponse } from '../../types/api';
import apiClient from '../../services/api';

interface JobsState {
  jobs: Job[];
  currentJob: Job | null;
  isLoading: boolean;
  isCreating: boolean;
  error: string | null;
  pagination: {
    page: number;
    limit: number;
    total: number;
    pages: number;
  };
  filters: {
    status?: string;
    job_type?: string;
  };
}

const initialState: JobsState = {
  jobs: [],
  currentJob: null,
  isLoading: false,
  isCreating: false,
  error: null,
  pagination: {
    page: 1,
    limit: 10,
    total: 0,
    pages: 0,
  },
  filters: {},
};

// Async thunks
export const fetchJobs = createAsyncThunk(
  'jobs/fetchJobs',
  async (params?: {
    page?: number;
    limit?: number;
    status?: string;
    job_type?: string;
  }, { rejectWithValue }) => {
    try {
      const response = await apiClient.getJobs(params);
      return response;
    } catch (error: any) {
      return rejectWithValue(
        error.response?.data?.message || 'Failed to fetch jobs'
      );
    }
  }
);

export const fetchJob = createAsyncThunk(
  'jobs/fetchJob',
  async (jobId: string, { rejectWithValue }) => {
    try {
      const job = await apiClient.getJob(jobId);
      return job;
    } catch (error: any) {
      return rejectWithValue(
        error.response?.data?.message || 'Failed to fetch job'
      );
    }
  }
);

export const createJob = createAsyncThunk(
  'jobs/createJob',
  async (jobData: JobRequest, { rejectWithValue }) => {
    try {
      const job = await apiClient.createJob(jobData);
      return job;
    } catch (error: any) {
      return rejectWithValue(
        error.response?.data?.message || 'Failed to create job'
      );
    }
  }
);

export const cancelJob = createAsyncThunk(
  'jobs/cancelJob',
  async (jobId: string, { rejectWithValue }) => {
    try {
      await apiClient.cancelJob(jobId);
      return jobId;
    } catch (error: any) {
      return rejectWithValue(
        error.response?.data?.message || 'Failed to cancel job'
      );
    }
  }
);

export const refreshJobSteps = createAsyncThunk(
  'jobs/refreshJobSteps',
  async (jobId: string, { rejectWithValue }) => {
    try {
      const steps = await apiClient.getJobSteps(jobId);
      return { jobId, steps };
    } catch (error: any) {
      return rejectWithValue(
        error.response?.data?.message || 'Failed to refresh job steps'
      );
    }
  }
);

const jobsSlice = createSlice({
  name: 'jobs',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
    setCurrentJob: (state, action: PayloadAction<Job | null>) => {
      state.currentJob = action.payload;
    },
    setFilters: (state, action: PayloadAction<JobsState['filters']>) => {
      state.filters = action.payload;
    },
    updateJobInList: (state, action: PayloadAction<Job>) => {
      const index = state.jobs.findIndex(job => job.id === action.payload.id);
      if (index !== -1) {
        state.jobs[index] = action.payload;
      }
    },
    updateJobStatus: (state, action: PayloadAction<{
      jobId: string;
      status: Job['status'];
      steps?: Job['steps'];
    }>) => {
      const { jobId, status, steps } = action.payload;
      
      // Update in jobs list
      const jobIndex = state.jobs.findIndex(job => job.id === jobId);
      if (jobIndex !== -1) {
        state.jobs[jobIndex].status = status;
        if (steps) {
          state.jobs[jobIndex].steps = steps;
        }
      }
      
      // Update current job
      if (state.currentJob?.id === jobId) {
        state.currentJob.status = status;
        if (steps) {
          state.currentJob.steps = steps;
        }
      }
    },
  },
  extraReducers: (builder) => {
    // Fetch jobs
    builder
      .addCase(fetchJobs.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchJobs.fulfilled, (state, action: PayloadAction<PaginatedResponse<Job>>) => {
        state.isLoading = false;
        state.jobs = action.payload.items;
        state.pagination = {
          page: action.payload.page,
          limit: action.payload.limit,
          total: action.payload.total,
          pages: action.payload.pages,
        };
      })
      .addCase(fetchJobs.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });

    // Fetch single job
    builder
      .addCase(fetchJob.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchJob.fulfilled, (state, action: PayloadAction<Job>) => {
        state.isLoading = false;
        state.currentJob = action.payload;
        
        // Also update in jobs list if it exists
        const index = state.jobs.findIndex(job => job.id === action.payload.id);
        if (index !== -1) {
          state.jobs[index] = action.payload;
        }
      })
      .addCase(fetchJob.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });

    // Create job
    builder
      .addCase(createJob.pending, (state) => {
        state.isCreating = true;
        state.error = null;
      })
      .addCase(createJob.fulfilled, (state, action: PayloadAction<Job>) => {
        state.isCreating = false;
        state.jobs.unshift(action.payload);
        state.currentJob = action.payload;
      })
      .addCase(createJob.rejected, (state, action) => {
        state.isCreating = false;
        state.error = action.payload as string;
      });

    // Cancel job
    builder
      .addCase(cancelJob.fulfilled, (state, action: PayloadAction<string>) => {
        const jobId = action.payload;
        
        // Update status in jobs list
        const jobIndex = state.jobs.findIndex(job => job.id === jobId);
        if (jobIndex !== -1) {
          state.jobs[jobIndex].status = 'CANCELLED';
        }
        
        // Update current job
        if (state.currentJob?.id === jobId) {
          state.currentJob.status = 'CANCELLED';
        }
      });

    // Refresh job steps
    builder
      .addCase(refreshJobSteps.fulfilled, (state, action: PayloadAction<{
        jobId: string;
        steps: Job['steps'];
      }>) => {
        const { jobId, steps } = action.payload;
        
        // Update in jobs list
        const jobIndex = state.jobs.findIndex(job => job.id === jobId);
        if (jobIndex !== -1) {
          state.jobs[jobIndex].steps = steps;
        }
        
        // Update current job
        if (state.currentJob?.id === jobId) {
          state.currentJob.steps = steps;
        }
      });
  },
});

export const {
  clearError,
  setCurrentJob,
  setFilters,
  updateJobInList,
  updateJobStatus,
} = jobsSlice.actions;

export default jobsSlice.reducer;