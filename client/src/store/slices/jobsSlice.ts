import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { JobResponse, CreateJobRequest } from '../../schemas';
import apiClient from '../../services/api';

interface JobsState {
  jobs: JobResponse[];
  currentJob: JobResponse | null;
  isLoading: boolean;
  isPolling: boolean;
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
  isPolling: false,
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
  async (params: {
    page?: number;
    limit?: number;
    status?: string;
    job_type?: string;
    isPolling?: boolean;
  } = {}, { rejectWithValue }) => {
    try {
      const response = await apiClient.getJobs(params);
      return { ...response, isPolling: params.isPolling || false };
    } catch (error: unknown) {
      return rejectWithValue(
        (error as { response?: { data?: { message?: string } } }).response?.data?.message || 'Failed to fetch jobs'
      );
    }
  }
);

export const fetchJob = createAsyncThunk(
  'jobs/fetchJob',
  async (params: { jobId: string; isPolling?: boolean }, { rejectWithValue }) => {
    try {
      const job = await apiClient.getJob(params.jobId);
      return { job, isPolling: params.isPolling || false };
    } catch (error: unknown) {
      return rejectWithValue(
        (error as { response?: { data?: { message?: string } } }).response?.data?.message || 'Failed to fetch job'
      );
    }
  }
);

export const createJob = createAsyncThunk(
  'jobs/createJob',
  async (jobData: CreateJobRequest, { rejectWithValue }) => {
    try {
      const job = await apiClient.createJob(jobData);
      return job;
    } catch (error: unknown) {
      return rejectWithValue(
        (error as { response?: { data?: { message?: string } } }).response?.data?.message || 'Failed to create job'
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
    } catch (error: unknown) {
      return rejectWithValue(
        (error as { response?: { data?: { message?: string } } }).response?.data?.message || 'Failed to cancel job'
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
    } catch (error: unknown) {
      return rejectWithValue(
        (error as { response?: { data?: { message?: string } } }).response?.data?.message || 'Failed to refresh job steps'
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
    setCurrentJob: (state, action: PayloadAction<JobResponse | null>) => {
      state.currentJob = action.payload;
    },
    setFilters: (state, action: PayloadAction<JobsState['filters']>) => {
      state.filters = action.payload;
    },
    updateJobInList: (state, action: PayloadAction<JobResponse>) => {
      const index = state.jobs.findIndex(job => job.id === action.payload.id);
      if (index !== -1) {
        state.jobs[index] = action.payload;
      }
    },
    updateJobStatus: (state, action: PayloadAction<{
      jobId: string;
      status: JobResponse['status'];
      steps?: JobResponse['steps'];
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
      .addCase(fetchJobs.pending, (state, action) => {
        const isPolling = action.meta.arg.isPolling;
        if (isPolling) {
          state.isPolling = true;
        } else {
          state.isLoading = true;
        }
        state.error = null;
      })
      .addCase(fetchJobs.fulfilled, (state, action) => {
        // const isPolling = action.payload.isPolling;
        state.isLoading = false;
        state.isPolling = false;
        
        const newJobs = action.payload.items;
        
        // Only update jobs if they actually changed
        if (JSON.stringify(state.jobs) !== JSON.stringify(newJobs)) {
          state.jobs = newJobs;
        }
        
        // Only update pagination if it changed
        const newPagination = {
          page: action.payload.page,
          limit: action.payload.limit,
          total: action.payload.total,
          pages: action.payload.pages,
        };
        
        if (JSON.stringify(state.pagination) !== JSON.stringify(newPagination)) {
          state.pagination = newPagination;
        }
      })
      .addCase(fetchJobs.rejected, (state, action) => {
        state.isLoading = false;
        state.isPolling = false;
        state.error = action.payload as string;
      });

    // Fetch single job
    builder
      .addCase(fetchJob.pending, (state, action) => {
        const isPolling = action.meta.arg.isPolling;
        if (isPolling) {
          state.isPolling = true;
        } else {
          state.isLoading = true;
        }
        state.error = null;
      })
      .addCase(fetchJob.fulfilled, (state, action) => {
        // const isPolling = action.payload.isPolling;
        state.isLoading = false;
        state.isPolling = false;
        
        const newJob = action.payload.job;
        
        // Only update currentJob if it actually changed
        if (!state.currentJob || 
            state.currentJob.status !== newJob.status ||
            state.currentJob.progress !== newJob.progress ||
            JSON.stringify(state.currentJob.steps) !== JSON.stringify(newJob.steps) ||
            state.currentJob.updated_at !== newJob.updated_at) {
          state.currentJob = newJob;
        }

        // Also update in jobs list if it exists and has changes
        const index = state.jobs.findIndex(job => job.id === newJob.id);
        if (index !== -1) {
          const existingJob = state.jobs[index];
          if (existingJob.status !== newJob.status ||
              existingJob.progress !== newJob.progress ||
              JSON.stringify(existingJob.steps) !== JSON.stringify(newJob.steps) ||
              existingJob.updated_at !== newJob.updated_at) {
            state.jobs[index] = newJob;
          }
        }
      })
      .addCase(fetchJob.rejected, (state, action) => {
        state.isLoading = false;
        state.isPolling = false;
        state.error = action.payload as string;
      });

    // Create job
    builder
      .addCase(createJob.pending, (state) => {
        state.isCreating = true;
        state.error = null;
      })
      .addCase(createJob.fulfilled, (state, action: PayloadAction<JobResponse>) => {
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
        steps: JobResponse['steps'];
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
