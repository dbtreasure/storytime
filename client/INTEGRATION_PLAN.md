# OpenAPI Client Integration Plan

## Overview
Migrate from manual TypeScript types to auto-generated types from OpenAPI schema to eliminate client-server type mismatches.

## Phase 1: Preparation & Setup ✅

- [x] **Install openapi-ts**: `@hey-api/openapi-ts` package installed
- [x] **Add npm scripts**: Generation scripts added to package.json
- [x] **Generate initial types**: Types generated in `src/generated/`
- [x] **Analysis complete**: Comparison analysis created

## Phase 2: Parallel Integration (Next Steps)

### 2A: Update API Client Layer
**File:** `src/services/api.ts`

**Changes Needed:**
1. **Remove ApiResponse wrapper assumption**
   ```typescript
   // Current (incorrect)
   const response = await axios.post<ApiResponse<JobResponse>>('/api/v1/jobs', data);
   return response.data.data; // ❌ Wrong - server doesn't wrap responses
   
   // Generated types (correct)
   const response = await axios.post<JobResponse>('/api/v1/jobs', data);
   return response.data; // ✅ Direct response
   ```

2. **Import generated types**
   ```typescript
   import { 
     JobResponse, 
     CreateJobRequest, 
     JobListResponse,
     PlaybackProgressResponse,
     UpdateProgressRequest
   } from '../generated';
   ```

3. **Update method signatures** to use generated types

### 2B: Update Redux Store Types
**Files:** Redux slices and state types

**Changes Needed:**
1. Replace manual `Job` interface with generated `JobResponse`
2. Update progress-related state to use `PlaybackProgressResponse`
3. Fix field name mismatches (`position` → `position_seconds`)

### 2C: Component Updates
**Priority Components to Update:**

1. **Job-related components**
   - Update to handle `user_id`, `description`, `progress` fields
   - Fix missing timestamp fields (`started_at`, `completed_at`)

2. **Progress components**
   - Update field names: `position` → `position_seconds`
   - Handle new progress fields: `percentage_complete`, `is_completed`
   - Update chapter handling: `chapter` → `current_chapter_id`

3. **Auth components**
   - Handle `token_type` field in login responses
   - Remove assumption of nested user object

## Phase 3: Client Generation with Services

### 3A: Generate Full Client
```bash
npm install @hey-api/client-axios
npm run generate-api  # Full client with service methods
```

### 3B: Replace Manual API Client
**Benefits:**
- Auto-generated service methods for each endpoint
- Built-in TypeScript types for requests/responses
- Automatic parameter validation
- Consistent error handling

**Example Generated Service:**
```typescript
// Generated service method
export const createJob = async (data: CreateJobApiV1JobsPostData) => {
  return await client.post<CreateJobApiV1JobsPostResponse>('/api/v1/jobs', data);
};
```

## Phase 4: Development Workflow Integration

### 4A: Add to Build Process
```json
{
  "scripts": {
    "dev": "npm run generate-api && vite",
    "build": "npm run generate-api && tsc -b && vite build",
    "generate-api": "openapi-ts --input http://localhost:8000/openapi.json --output ./src/generated --client @hey-api/client-axios"
  }
}
```

### 4B: Add Pre-commit Hook
```bash
# Regenerate types before commits to catch API changes
npm install husky --save-dev
```

### 4C: CI/CD Integration
- Add API schema validation to CI
- Fail builds if client-server types are out of sync
- Auto-regenerate types on API changes

## Phase 5: Error Handling Enhancement

### 5A: Use Generated Error Types
```typescript
// Generated validation error handling
import { HttpValidationError } from '../generated';

try {
  const result = await createJob(data);
} catch (error) {
  if (error.response?.status === 422) {
    const validationError: HttpValidationError = error.response.data;
    // Handle validation errors properly
  }
}
```

## Rollback Plan

### Minimal Risk Migration Strategy:
1. **Keep manual types** alongside generated types initially
2. **Update one component at a time** to use generated types
3. **Test thoroughly** before removing manual types
4. **Easy rollback** by switching imports back to manual types

### Testing Strategy:
1. **Unit tests** for API client with generated types
2. **Integration tests** for key user flows
3. **Type checking** with `tsc --noEmit`
4. **Manual testing** of critical features

## Benefits After Migration

### ✅ **Eliminated Issues:**
- No more client-server type mismatches
- Automatic type updates when API changes
- Better IDE autocomplete and error detection
- Consistent error handling across all endpoints

### ✅ **Developer Experience:**
- Single source of truth for API contracts
- Automatic validation of request/response shapes
- Reduced manual type maintenance
- Better documentation through generated types

### ✅ **Production Benefits:**
- Fewer runtime errors from type mismatches
- Better error handling with proper validation error types
- More reliable API integration
- Faster development with auto-generated client methods

## Next Action Items

1. **Start with API client layer** - Update `src/services/api.ts`
2. **Update one Redux slice** as proof of concept
3. **Migrate one component** to validate the approach
4. **Set up regeneration workflow** for development

The migration is **low risk** and **high value** - we can proceed incrementally while maintaining full functionality.