import React, { useEffect, useState, useRef } from 'react';
import { useAudioPlayer } from '../hooks/useAudioPlayer';
import { Button } from './ui/Button';
import { Card } from './ui/Card';
import {
  SpeakerWaveIcon,
  SpeakerXMarkIcon,
  BackwardIcon,
  ForwardIcon,
  StopIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline';

interface AudioPlayerProps {
  jobId: string;
  title?: string;
  autoPlay?: boolean;
  className?: string;
}

export const AudioPlayer: React.FC<AudioPlayerProps> = ({
  jobId,
  title,
  autoPlay = false,
  className = '',
}) => {
  const audioPlayer = useAudioPlayer();
  const [isDragging, setIsDragging] = useState(false);
  const [localPosition, setLocalPosition] = useState(0);
  const progressRef = useRef<HTMLDivElement>(null);

  // Load audio when component mounts or jobId changes
  useEffect(() => {
    if (jobId && audioPlayer.currentJobId !== jobId) {
      audioPlayer.loadJob(jobId);
    }
  }, [jobId, audioPlayer.currentJobId, audioPlayer.loadJob]);

  // Auto-play if requested and audio is loaded
  useEffect(() => {
    if (autoPlay && audioPlayer.canPlay && audioPlayer.currentJobId === jobId && !audioPlayer.isPlaying) {
      audioPlayer.play();
    }
  }, [autoPlay, audioPlayer.canPlay, audioPlayer.currentJobId, jobId, audioPlayer.isPlaying, audioPlayer.play]);

  // Update local position when not dragging
  useEffect(() => {
    if (!isDragging) {
      setLocalPosition(audioPlayer.currentPosition);
    }
  }, [audioPlayer.currentPosition, isDragging]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const handleProgressClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!progressRef.current || !audioPlayer.duration) return;

    const rect = progressRef.current.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const width = rect.width;
    const newPosition = (clickX / width) * audioPlayer.duration;

    audioPlayer.seek(newPosition);
  };

  const handleProgressMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    setIsDragging(true);
    handleProgressClick(e);
  };

  const handleProgressMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDragging || !progressRef.current || !audioPlayer.duration) return;

    const rect = progressRef.current.getBoundingClientRect();
    const moveX = e.clientX - rect.left;
    const width = rect.width;
    const newPosition = Math.max(0, Math.min(audioPlayer.duration, (moveX / width) * audioPlayer.duration));

    setLocalPosition(newPosition);
  };

  const handleProgressMouseUp = () => {
    if (isDragging) {
      audioPlayer.seek(localPosition);
      setIsDragging(false);
    }
  };

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const volume = parseFloat(e.target.value);
    audioPlayer.setVolume(volume);
  };

  // Don't render if this isn't the current job
  if (audioPlayer.currentJobId !== jobId) {
    return null;
  }

  const currentPosition = isDragging ? localPosition : audioPlayer.currentPosition;
  const progressPercentage = audioPlayer.duration > 0 ? (currentPosition / audioPlayer.duration) * 100 : 0;

  return (
    <Card className={`p-4 ${className}`}>
      <div className="space-y-4">
        {/* Title */}
        {title && (
          <div className="text-center">
            <h3 className="text-lg font-semibold text-gray-900 truncate">{title}</h3>
          </div>
        )}

        {/* Main Controls */}
        <div className="flex items-center justify-center space-x-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => audioPlayer.skipBackward(10)}
            disabled={!audioPlayer.canPlay}
          >
            <BackwardIcon className="h-4 w-4" />
          </Button>

          <Button
            size="lg"
            onClick={audioPlayer.toggle}
            disabled={audioPlayer.isLoading}
            className="w-12 h-12 rounded-full"
          >
            {audioPlayer.isLoading ? (
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : audioPlayer.isPlaying ? (
              <span className="text-xl font-bold text-white">⏸</span>
            ) : (
              <span className="text-xl font-bold text-white">▶</span>
            )}
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => audioPlayer.skipForward(10)}
            disabled={!audioPlayer.canPlay}
          >
            <ForwardIcon className="h-4 w-4" />
          </Button>
        </div>

        {/* Progress Bar */}
        <div className="space-y-2">
          <div
            ref={progressRef}
            className="relative w-full h-2 bg-gray-200 rounded-full cursor-pointer"
            onMouseDown={handleProgressMouseDown}
            onMouseMove={handleProgressMouseMove}
            onMouseUp={handleProgressMouseUp}
            onMouseLeave={handleProgressMouseUp}
          >
            {/* Progress fill */}
            <div
              className="absolute top-0 left-0 h-full bg-blue-600 rounded-full transition-all duration-150"
              style={{ width: `${progressPercentage}%` }}
            />
            
            {/* Scrub handle */}
            <div
              className="absolute top-1/2 transform -translate-y-1/2 w-4 h-4 bg-white border-2 border-blue-600 rounded-full shadow-sm cursor-grab active:cursor-grabbing"
              style={{ left: `calc(${progressPercentage}% - 8px)` }}
            />
          </div>

          {/* Time Display */}
          <div className="flex justify-between text-xs text-gray-500">
            <span>{formatTime(currentPosition)}</span>
            <span>{formatTime(audioPlayer.duration)}</span>
          </div>
        </div>

        {/* Volume Control */}
        <div className="flex items-center space-x-2">
          <SpeakerWaveIcon className="h-4 w-4 text-gray-500" />
          <input
            type="range"
            min="0"
            max="1"
            step="0.1"
            value={audioPlayer.volume}
            onChange={handleVolumeChange}
            className="flex-1 h-1 bg-gray-200 rounded-lg appearance-none cursor-pointer"
          />
          <span className="text-xs text-gray-500 w-8">
            {Math.round(audioPlayer.volume * 100)}%
          </span>
        </div>

        {/* Loading/Error States */}
        {audioPlayer.isLoading && (
          <div className="text-center text-sm text-gray-500">
            Loading audio...
          </div>
        )}

        {audioPlayer.error && (
          <div className="text-center text-sm text-red-600">
            Error: {audioPlayer.error}
          </div>
        )}
      </div>
    </Card>
  );
};

export default AudioPlayer;