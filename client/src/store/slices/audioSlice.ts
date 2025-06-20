import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { AudioMetadataResponse, PlaybackProgressResponse, UpdateProgressRequest } from '../../schemas';
import apiClient from '../../services/api';

interface AudioState {
  // Playback state
  isPlaying: boolean;
  currentPosition: number;
  duration: number;
  volume: number;
  currentJobId: string | null;
  currentChapter: string | null;

  // Audio metadata
  metadata: AudioMetadataResponse | null;
  streamingUrl: string | null;

  // Progress tracking
  progress: PlaybackProgressResponse | null;
  recentProgress: PlaybackProgressResponse[];

  // UI state
  isLoading: boolean;
  error: string | null;

  // Audio element (not serializable)
  audioElement: HTMLAudioElement | null;
}

const initialState: AudioState = {
  isPlaying: false,
  currentPosition: 0,
  duration: 0,
  volume: 1.0,
  currentJobId: null,
  currentChapter: null,
  metadata: null,
  streamingUrl: null,
  progress: null,
  recentProgress: [],
  isLoading: false,
  error: null,
  audioElement: null,
};

// Async thunks
export const loadAudio = createAsyncThunk(
  'audio/loadAudio',
  async (jobId: string, { rejectWithValue }) => {
    try {
      console.log('loadAudio starting for jobId:', jobId);

      const [streamingData, metadata, progress] = await Promise.all([
        apiClient.getAudioStream(jobId),
        apiClient.getAudioMetadata(jobId),
        apiClient.getProgress(jobId).catch(() => null), // Progress might not exist
      ]);

      console.log('loadAudio responses:', { streamingData, metadata, progress });
      console.log('streamingData.streaming_url:', streamingData.streaming_url);
      console.log('full streamingData:', streamingData);

      return {
        jobId,
        streamingUrl: streamingData.streaming_url,
        metadata,
        progress,
      };
    } catch (error: unknown) {
      console.error('loadAudio failed:', error);
      return rejectWithValue(
        (error as { response?: { data?: { message?: string } } }).response?.data?.message || 'Failed to load audio'
      );
    }
  }
);

export const updateProgress = createAsyncThunk(
  'audio/updateProgress',
  async (params: {
    jobId: string;
    positionSeconds: number;
    currentChapterId?: string;
  }, { rejectWithValue }) => {
    try {
      const progress = await apiClient.updateProgress(params.jobId, {
        position_seconds: params.positionSeconds,
        current_chapter_id: params.currentChapterId,
      } as UpdateProgressRequest);
      return progress;
    } catch (error: unknown) {
      return rejectWithValue(
        (error as { response?: { data?: { message?: string } } }).response?.data?.message || 'Failed to update progress'
      );
    }
  }
);

export const fetchRecentProgress = createAsyncThunk(
  'audio/fetchRecentProgress',
  async (_, { rejectWithValue }) => {
    try {
      const progress = await apiClient.getRecentProgress();
      return progress;
    } catch (error: unknown) {
      return rejectWithValue(
        (error as { response?: { data?: { message?: string } } }).response?.data?.message || 'Failed to fetch recent progress'
      );
    }
  }
);

export const resetProgress = createAsyncThunk(
  'audio/resetProgress',
  async (jobId: string, { rejectWithValue }) => {
    try {
      await apiClient.resetProgress(jobId);
      return jobId;
    } catch (error: unknown) {
      return rejectWithValue(
        (error as { response?: { data?: { message?: string } } }).response?.data?.message || 'Failed to reset progress'
      );
    }
  }
);

const audioSlice = createSlice({
  name: 'audio',
  initialState,
  reducers: {
    setAudioElement: (state, action: PayloadAction<HTMLAudioElement | null>) => {
      // Cast through unknown to satisfy Immer's WritableDraft type
      state.audioElement = action.payload as unknown as typeof state.audioElement;
    },

    setPlaying: (state, action: PayloadAction<boolean>) => {
      state.isPlaying = action.payload;
    },

    setCurrentPosition: (state, action: PayloadAction<number>) => {
      state.currentPosition = action.payload;
    },

    setDuration: (state, action: PayloadAction<number>) => {
      state.duration = action.payload;
    },

    setVolume: (state, action: PayloadAction<number>) => {
      const volume = Math.max(0, Math.min(1, action.payload));
      state.volume = volume;
    },

    setCurrentChapter: (state, action: PayloadAction<string | null>) => {
      state.currentChapter = action.payload;
    },

    seekTo: (state, action: PayloadAction<number>) => {
      const position = Math.max(0, Math.min(state.duration, action.payload));
      state.currentPosition = position;
    },

    clearAudio: (state) => {
      state.isPlaying = false;
      state.currentPosition = 0;
      state.duration = 0;
      state.currentJobId = null;
      state.currentChapter = null;
      state.metadata = null;
      state.streamingUrl = null;
      state.progress = null;
      state.audioElement = null;
    },

    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    // Load audio
    builder
      .addCase(loadAudio.pending, (state) => {
        console.log('loadAudio.pending');
        state.isLoading = true;
        state.error = null;
      })
      .addCase(loadAudio.fulfilled, (state, action) => {
        console.log('loadAudio.fulfilled', action.payload);
        const { jobId, streamingUrl, metadata, progress } = action.payload;

        state.isLoading = false;
        state.currentJobId = jobId;
        state.streamingUrl = streamingUrl;
        state.metadata = metadata;
        state.progress = progress;
        state.duration = metadata.duration || 0;

        // Set position from progress if available
        if (progress) {
          state.currentPosition = progress.position_seconds;
          state.currentChapter = progress.current_chapter_id || null;
        } else {
          state.currentPosition = 0;
          state.currentChapter = null;
        }
      })
      .addCase(loadAudio.rejected, (state, action) => {
        console.log('loadAudio.rejected', action.payload);
        state.isLoading = false;
        state.error = action.payload as string;
      });

    // Update progress
    builder
      .addCase(updateProgress.fulfilled, (state, action: PayloadAction<PlaybackProgressResponse>) => {
        state.progress = action.payload;
      });

    // Fetch recent progress
    builder
      .addCase(fetchRecentProgress.fulfilled, (state, action: PayloadAction<PlaybackProgressResponse[]>) => {
        state.recentProgress = action.payload;
      });

    // Reset progress
    builder
      .addCase(resetProgress.fulfilled, (state, action: PayloadAction<string>) => {
        const jobId = action.payload;
        if (state.currentJobId === jobId) {
          state.progress = null;
          state.currentPosition = 0;
          state.currentChapter = null;
        }

        // Remove from recent progress
        state.recentProgress = state.recentProgress.filter(p => p.job_id !== jobId);
      });
  },
});

export const {
  setAudioElement,
  setPlaying,
  setCurrentPosition,
  setDuration,
  setVolume,
  setCurrentChapter,
  seekTo,
  clearAudio,
  clearError,
} = audioSlice.actions;

export default audioSlice.reducer;
