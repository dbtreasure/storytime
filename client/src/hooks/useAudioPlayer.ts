import { useEffect, useRef, useCallback } from 'react';
import { useAppDispatch, useAppSelector } from './redux';
import {
  setAudioElement,
  setPlaying,
  setCurrentPosition,
  setDuration,
  setVolume as setVolumeAction,
  seekTo,
  updateProgress,
  loadAudio,
} from '../store/slices/audioSlice';

export const useAudioPlayer = () => {
  const dispatch = useAppDispatch();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const progressIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const {
    isPlaying,
    currentPosition,
    duration,
    volume,
    currentJobId,
    currentChapter,
    streamingUrl,
    isLoading,
    error,
  } = useAppSelector((state) => state.audio);

  // Initialize audio element
  useEffect(() => {
    if (!audioRef.current) {
      audioRef.current = new Audio();
      dispatch(setAudioElement(audioRef.current));
    }

    const audio = audioRef.current;

    const handleLoadedMetadata = () => {
      dispatch(setDuration(audio.duration));
    };

    const handleTimeUpdate = () => {
      dispatch(setCurrentPosition(audio.currentTime));
    };

    const handleEnded = () => {
      dispatch(setPlaying(false));
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = null;
      }
    };

    const handleError = () => {
      dispatch(setPlaying(false));
      console.error('Audio playback error');
    };

    audio.addEventListener('loadedmetadata', handleLoadedMetadata);
    audio.addEventListener('timeupdate', handleTimeUpdate);
    audio.addEventListener('ended', handleEnded);
    audio.addEventListener('error', handleError);

    return () => {
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
      audio.removeEventListener('timeupdate', handleTimeUpdate);
      audio.removeEventListener('ended', handleEnded);
      audio.removeEventListener('error', handleError);
    };
  }, [dispatch]);

  // Update audio source when streaming URL changes (no auto-play)
  useEffect(() => {
    if (audioRef.current && streamingUrl) {
      console.log('Setting audio source to:', streamingUrl);
      audioRef.current.src = streamingUrl;
      // Don't auto-play - let the AudioPlayer component control playback
    } else if (audioRef.current && !streamingUrl) {
      console.log('No streaming URL available, audio src not set');
    }
  }, [streamingUrl, dispatch]);

  // Update volume
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = volume;
    }
  }, [volume]);

  // Sync audio position with Redux state
  useEffect(() => {
    if (audioRef.current && Math.abs(audioRef.current.currentTime - currentPosition) > 1) {
      audioRef.current.currentTime = currentPosition;
    }
  }, [currentPosition]);

  // Progress update interval
  useEffect(() => {
    if (isPlaying && currentJobId) {
      progressIntervalRef.current = setInterval(() => {
        if (audioRef.current) {
          dispatch(updateProgress({
            jobId: currentJobId,
            positionSeconds: audioRef.current.currentTime,
            currentChapterId: currentChapter || undefined,
          }));
        }
      }, 10000); // Update every 10 seconds

      return () => {
        if (progressIntervalRef.current) {
          clearInterval(progressIntervalRef.current);
          progressIntervalRef.current = null;
        }
      };
    }
  }, [isPlaying, currentJobId, currentChapter, dispatch]);

  // Audio controls
  const play = useCallback(async () => {
    if (audioRef.current) {
      try {
        await audioRef.current.play();
        dispatch(setPlaying(true));
      } catch (error) {
        console.error('Failed to play audio:', error);
      }
    }
  }, [dispatch]);

  const pause = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      dispatch(setPlaying(false));
    }
  }, [dispatch]);

  const toggle = useCallback(() => {
    if (isPlaying) {
      pause();
    } else {
      play();
    }
  }, [isPlaying, play, pause]);

  const seek = useCallback((position: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = position;
      dispatch(seekTo(position));
    }
  }, [dispatch]);

  const loadJob = useCallback((jobId: string) => {
    dispatch(loadAudio(jobId));
  }, [dispatch]);

  const setVolume = useCallback((volume: number) => {
    const clampedVolume = Math.max(0, Math.min(1, volume));
    dispatch(setVolumeAction(clampedVolume));
  }, [dispatch]);

  // Skip forward/backward
  const skipForward = useCallback((seconds: number = 10) => {
    seek(Math.min(currentPosition + seconds, duration));
  }, [seek, currentPosition, duration]);

  const skipBackward = useCallback((seconds: number = 10) => {
    seek(Math.max(currentPosition - seconds, 0));
  }, [seek, currentPosition]);

  // Chapter navigation (for multi-chapter books)
  const nextChapter = useCallback(() => {
    // Implementation would depend on chapter structure in metadata
    // This is a placeholder for chapter navigation logic
  }, []);

  const previousChapter = useCallback(() => {
    // Implementation would depend on chapter structure in metadata
    // This is a placeholder for chapter navigation logic
  }, []);

  return {
    // State
    isPlaying,
    currentPosition,
    duration,
    volume,
    currentJobId,
    currentChapter,
    isLoading,
    error,

    // Controls
    play,
    pause,
    toggle,
    seek,
    skipForward,
    skipBackward,
    nextChapter,
    previousChapter,
    loadJob,
    setVolume,

    // Computed values
    progress: duration > 0 ? (currentPosition / duration) * 100 : 0,
    remainingTime: duration - currentPosition,
    canPlay: !!streamingUrl && !isLoading,
  };
};
