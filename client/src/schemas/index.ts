import { z } from 'zod';

// Basic enums and constants
export const JobStatusSchema = z.enum(['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'CANCELLED']);
export const StepStatusSchema = z.enum(['PENDING', 'RUNNING', 'COMPLETED', 'FAILED']);
export const JobTypeSchema = z.enum(['text_to_audio', 'book_processing']);

// Voice configuration
export const VoiceConfigSchema = z.object({
  provider: z.string(),
  voice_id: z.string().nullable().optional(),
  voice_settings: z.record(z.string()).optional(),
});


// Chapter information
export const ChapterSchema = z.object({
  title: z.string(),
  order: z.number().int(),
  duration: z.number().nullable().optional(),
  file_key: z.string().nullable().optional(),
});

// Job configuration
export const JobConfigSchema = z.object({
  voice_config: VoiceConfigSchema.nullable().optional(),
  provider: z.string().nullable().optional(), // backwards compatibility
});

// Job result data
export const JobResultDataSchema = z.object({
  duration: z.number().nullable().optional(),
  duration_seconds: z.number().nullable().optional(), // alias
  file_size_bytes: z.number().int().nullable().optional(),
  chapters: z.array(ChapterSchema).nullable().optional(),
  child_job_ids: z.array(z.string()).nullable().optional(),
});

// Job step response
export const JobStepResponseSchema = z.object({
  id: z.string(),
  step_name: z.string(),
  step_order: z.number().int(),
  status: StepStatusSchema,
  progress: z.number(),
  error_message: z.string().nullable().optional(),
  step_metadata: z.record(z.unknown()).nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
  started_at: z.string().nullable().optional(),
  completed_at: z.string().nullable().optional(),
  duration: z.number().nullable().optional(),
});

// Job response (the main one!) - with recursive relationships
export const JobResponseSchema: z.ZodType<JobResponse> = z.lazy(() => z.object({
  id: z.string(),
  user_id: z.string(),
  parent_job_id: z.string().nullable().optional(),
  title: z.string(),
  description: z.string().nullable().optional(),
  status: JobStatusSchema,
  progress: z.number(),
  error_message: z.string().nullable().optional(),
  config: JobConfigSchema.nullable().optional(),
  result_data: JobResultDataSchema.nullable().optional(),
  input_file_key: z.string().nullable().optional(),
  output_file_key: z.string().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
  started_at: z.string().nullable().optional(),
  completed_at: z.string().nullable().optional(),
  duration: z.number().nullable().optional(),
  steps: z.array(JobStepResponseSchema).optional(),
  children: z.array(JobResponseSchema).optional(),
  parent: JobResponseSchema.nullable().optional(),
}));

// Audio streaming types
export const ResumeInfoResponseSchema = z.object({
  has_progress: z.boolean(),
  resume_position: z.number().default(0),
  percentage_complete: z.number().default(0),
  last_played_at: z.string().nullable().optional(),
  current_chapter_id: z.string().nullable().optional(),
  current_chapter_position: z.number().default(0),
});

export const StreamingUrlResponseSchema = z.object({
  streaming_url: z.string(),
  expires_at: z.string(),
  file_key: z.string(),
  content_type: z.string(),
  resume_info: ResumeInfoResponseSchema,
  source_job_id: z.string().nullable().optional(),
});

export const AudioMetadataResponseSchema = z.object({
  job_id: z.string(),
  title: z.string(),
  status: JobStatusSchema,
  format: z.string(),
  duration: z.number().nullable().optional(),
  file_size: z.number().nullable().optional(),
  created_at: z.string().nullable().optional(),
  completed_at: z.string().nullable().optional(),
  chapters: z.array(z.record(z.unknown())).optional(), // Generic for now
  resume_position: z.number().default(0),
  percentage_complete: z.number().default(0),
  last_played_at: z.string().nullable().optional(),
  current_chapter_id: z.string().nullable().optional(),
  current_chapter_position: z.number().default(0),
});

// Progress tracking
export const PlaybackProgressResponseSchema = z.object({
  id: z.string(),
  user_id: z.string(),
  job_id: z.string(),
  position_seconds: z.number(),
  duration_seconds: z.number().nullable().optional(),
  percentage_complete: z.number(),
  current_chapter_id: z.string().nullable().optional(),
  current_chapter_position: z.number(),
  is_completed: z.boolean(),
  last_played_at: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const UpdateProgressRequestSchema = z.object({
  position_seconds: z.number(),
  duration_seconds: z.number().nullable().optional(),
  current_chapter_id: z.string().nullable().optional(),
  current_chapter_position: z.number().default(0),
});

// Job creation
export const CreateJobRequestSchema = z.object({
  title: z.string(),
  description: z.string().nullable().optional(),
  content: z.string().nullable().optional(),
  file_key: z.string().nullable().optional(),
  url: z.string().url().nullable().optional(),
  voice_config: VoiceConfigSchema.nullable().optional(),
}).refine(
  (data) => {
    const sources = [data.content, data.file_key, data.url].filter(Boolean);
    return sources.length === 1;
  },
  {
    message: "Exactly one of content, file_key, or url must be provided",
    path: ["content"], // This will show the error on the content field
  }
);

// List responses
export const JobListResponseSchema = z.object({
  jobs: z.array(JobResponseSchema),
  total: z.number().int(),
  page: z.number().int(),
  page_size: z.number().int(),
  total_pages: z.number().int(),
});

// Export inferred types
export type JobStatus = z.infer<typeof JobStatusSchema>;
export type StepStatus = z.infer<typeof StepStatusSchema>;
export type JobType = z.infer<typeof JobTypeSchema>;
export type VoiceConfig = z.infer<typeof VoiceConfigSchema>;
export type Chapter = z.infer<typeof ChapterSchema>;
export type JobConfig = z.infer<typeof JobConfigSchema>;
export type JobResultData = z.infer<typeof JobResultDataSchema>;
export type JobStepResponse = z.infer<typeof JobStepResponseSchema>;
export type ResumeInfoResponse = z.infer<typeof ResumeInfoResponseSchema>;
export type StreamingUrlResponse = z.infer<typeof StreamingUrlResponseSchema>;
export type AudioMetadataResponse = z.infer<typeof AudioMetadataResponseSchema>;
export type PlaybackProgressResponse = z.infer<typeof PlaybackProgressResponseSchema>;
export type UpdateProgressRequest = z.infer<typeof UpdateProgressRequestSchema>;
export type CreateJobRequest = z.infer<typeof CreateJobRequestSchema>;
export type JobListResponse = z.infer<typeof JobListResponseSchema>;

// Recursive JobResponse type (defined explicitly for TypeScript)
export interface JobResponse {
  id: string;
  user_id: string;
  parent_job_id?: string | null;
  title: string;
  description?: string | null;
  status: JobStatus;
  progress: number;
  error_message?: string | null;
  config?: JobConfig | null;
  result_data?: JobResultData | null;
  input_file_key?: string | null;
  output_file_key?: string | null;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  duration?: number | null;
  steps?: JobStepResponse[];
  children?: JobResponse[];
  parent?: JobResponse | null;
}
