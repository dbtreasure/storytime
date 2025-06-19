# Generated vs Manual Types Comparison

## Key Differences Found

### 1. **Response Wrapping**
**Current Manual Types:**
```typescript
export interface ApiResponse<T = any> {
  data: T;
  message?: string;
  success: boolean;
}
```

**Generated Types:**
- Direct response types without wrapper (matches FastAPI's actual response structure)
- Server returns responses directly, not wrapped in `ApiResponse<T>`

### 2. **Job Response Structure**
**Current Manual Types:**
```typescript
export interface Job {
  id: string;
  job_type: JobType;
  status: JobStatus;
  title?: string;
  text_length?: number;
  voice_config?: VoiceConfig;
  processing_config?: ProcessingConfig;
  result?: { audio_url?: string; duration?: number; chapters?: Array<...> };
  error_message?: string;
  created_at: string;
  updated_at: string;
  steps: JobStep[];
}
```

**Generated Types:**
```typescript
export type JobResponse = {
  id: string;
  user_id: string;  // ❌ Missing in manual types
  title: string;
  description?: string | null;  // ❌ Missing in manual types
  status: JobStatus;
  progress: number;  // ❌ Missing in manual types
  error_message?: string | null;
  config?: { [key: string]: unknown; } | null;  // ❌ Different structure
  result_data?: { [key: string]: unknown; } | null;  // ❌ Different name
  input_file_key?: string | null;  // ❌ Missing in manual types
  output_file_key?: string | null;  // ❌ Missing in manual types
  created_at: string;
  updated_at: string;
  started_at?: string | null;  // ❌ Missing in manual types
  completed_at?: string | null;  // ❌ Missing in manual types
  duration?: number | null;  // ❌ Missing in manual types
  steps?: Array<JobStepResponse>;  // ❌ Optional in generated vs required in manual
}
```

### 3. **Progress Types**
**Current Manual Types:**
```typescript
export interface PlaybackProgress {
  job_id: string;
  position: number;  // ❌ Different name
  chapter?: number;  // ❌ Different type
  updated_at: string;
}

export interface UpdateProgressRequest {
  position: number;  // ❌ Different name
  chapter?: number;  // ❌ Different structure
}
```

**Generated Types:**
```typescript
export type PlaybackProgressResponse = {
  id: string;  // ❌ Missing in manual types
  user_id: string;  // ❌ Missing in manual types
  job_id: string;
  position_seconds: number;  // ❌ Different name
  duration_seconds?: number | null;  // ❌ Missing in manual types
  percentage_complete: number;  // ❌ Missing in manual types
  current_chapter_id?: string | null;  // ❌ Different structure
  current_chapter_position: number;  // ❌ Missing in manual types
  is_completed: boolean;  // ❌ Missing in manual types
  last_played_at: string;  // ❌ Missing in manual types
  created_at: string;  // ❌ Missing in manual types
  updated_at: string;
}

export type UpdateProgressRequest = {
  position_seconds: number;  // ❌ Different name
  duration_seconds?: number | null;  // ❌ Missing in manual types
  current_chapter_id?: string | null;  // ❌ Different structure
  current_chapter_position?: number;  // ❌ Missing in manual types
}
```

### 4. **Auth Types**
**Current Manual Types:**
```typescript
export interface AuthResponse {
  user: User;
  access_token: string;
}
```

**Generated Types:**
```typescript
export type Token = {
  access_token: string;
  token_type: string;  // ❌ Missing in manual types
}
// ❌ No combined AuthResponse type
```

### 5. **Endpoint Types**
**Generated Types Include:**
- Complete request/response types for every endpoint
- Path parameters, query parameters, and body types
- Error response types (422 validation errors)
- URL templates for each endpoint

**Example:**
```typescript
export type CreateJobApiV1JobsPostData = {
  body: CreateJobRequest;
  path?: never;
  query?: never;
  url: '/api/v1/jobs';
};
```

## Summary of Issues

### Missing Fields in Manual Types:
1. `user_id` in Job responses
2. `description` in Job responses  
3. `progress` field in Job responses
4. Complete progress tracking fields
5. Timestamp fields (`started_at`, `completed_at`)
6. File key fields (`input_file_key`, `output_file_key`)

### Naming Inconsistencies:
1. `position` vs `position_seconds`
2. `chapter` vs `current_chapter_id`
3. `result` vs `result_data`
4. `processing_config` vs `config`

### Structure Differences:
1. Client expects `ApiResponse<T>` wrapper but server returns direct responses
2. Complex nested chapter structure in manual types vs simple object in generated
3. Missing comprehensive error handling types

## Recommendations:
1. **Phase out manual types** in favor of generated types
2. **Update API client** to handle direct responses (not wrapped)
3. **Migrate components** to use proper field names
4. **Add error handling** for validation errors
5. **Use generated endpoint types** for better type safety