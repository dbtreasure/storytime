# Audio Streaming API

The Audio Streaming API provides endpoints for streaming audio content with support for resume functionality, metadata retrieval, and playlist generation.

## Overview

The streaming API uses pre-signed URLs to provide direct CDN streaming without proxying through the application server. This approach offers:

- **Performance**: Direct CDN streaming without proxy overhead
- **Scalability**: Offloads bandwidth to DigitalOcean's infrastructure
- **Security**: Time-limited URLs with authentication verification
- **Consistency**: Uses the same infrastructure as file uploads

## Endpoints

### Get Streaming URL

```http
GET /api/v1/audio/{job_id}/stream
```

Returns a pre-signed URL optimized for audio streaming with appropriate headers for in-browser playback.

**Response:**
```json
{
  "streaming_url": "https://nyc3.digitaloceanspaces.com/...",
  "expires_at": "2024-01-01T12:00:00",
  "file_key": "jobs/job-id/audio.mp3",
  "content_type": "audio/mpeg"
}
```

**Headers set on streaming URL:**
- `Content-Disposition: inline` - For in-browser playback
- `Content-Type: audio/mpeg` - Proper audio handling
- `Cache-Control: public, max-age=3600` - Optimal streaming performance

### Get Audio Metadata

```http
GET /api/v1/audio/{job_id}/metadata
```

Returns metadata about the audio file including duration, format, and file size.

**Response:**
```json
{
  "job_id": "job-id",
  "title": "Audio Book Title",
  "status": "COMPLETED",
  "format": "audio/mpeg",
  "duration": 120.5,
  "file_size": 1024000,
  "created_at": "2024-01-01T10:00:00",
  "completed_at": "2024-01-01T10:05:00",
  "chapters": []
}
```

### Get Playlist

```http
GET /api/v1/audio/{job_id}/playlist
```

Returns an M3U playlist for the audio content. Supports both single-file and multi-chapter audiobooks.

**Response (Single File):**
```m3u
#EXTM3U
#EXTINF:-1,Audio Book Title
https://nyc3.digitaloceanspaces.com/...
```

**Response (Multi-Chapter):**
```m3u
#EXTM3U
#EXTINF:300,Chapter 1 - Introduction
https://nyc3.digitaloceanspaces.com/.../chapter_1.mp3
#EXTINF:450,Chapter 2 - The Journey Begins
https://nyc3.digitaloceanspaces.com/.../chapter_2.mp3
```

## Integration with Existing APIs

The existing job audio endpoint has been enhanced to provide both download and streaming URLs:

```http
GET /api/v1/jobs/{job_id}/audio
```

**Enhanced Response:**
```json
{
  "download_url": "https://...",  // For downloading
  "streaming_url": "https://...", // For streaming
  "file_key": "jobs/job-id/audio.mp3",
  "content_type": "audio/mpeg"
}
```

## Client Implementation

### Basic HTML5 Audio Player

```html
<audio controls>
  <source src="{streaming_url}" type="audio/mpeg">
  Your browser does not support the audio element.
</audio>
```

### JavaScript with Resume Support

```javascript
// Get streaming URL
const response = await fetch(`/api/v1/audio/${jobId}/stream`, {
  headers: { 'Authorization': `Bearer ${token}` }
});
const { streaming_url } = await response.json();

// Create audio element
const audio = new Audio(streaming_url);

// Resume from saved position
const savedPosition = localStorage.getItem(`audio-position-${jobId}`);
if (savedPosition) {
  audio.currentTime = parseFloat(savedPosition);
}

// Save position periodically
audio.addEventListener('timeupdate', () => {
  localStorage.setItem(`audio-position-${jobId}`, audio.currentTime);
});

// Play
audio.play();
```

## Security Considerations

1. **Authentication**: All endpoints require valid JWT authentication
2. **Authorization**: Users can only access audio from their own jobs
3. **URL Expiration**: Pre-signed URLs expire after 1 hour by default
4. **CORS**: Proper CORS headers are set for browser compatibility

## Future Enhancements

1. **Adaptive Bitrate Streaming**: Support for multiple quality levels
2. **Chapter Markers**: Enhanced metadata with chapter timestamps
3. **Transcripts**: Synchronized text transcripts with audio
4. **Analytics**: Playback analytics and progress tracking