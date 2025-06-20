import React, { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAppSelector, useAppDispatch } from '../hooks/redux';
import { fetchJob } from '../store/slices/jobsSlice';
import { useAudioPlayer } from '../hooks/useAudioPlayer';
import AudioPlayer from '../components/AudioPlayer';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Spinner } from '../components/ui/Spinner';
import { Alert } from '../components/ui/Alert';
import {
  ArrowLeftIcon,
  BookOpenIcon,
  CalendarIcon,
  ClockIcon,
  SpeakerWaveIcon,
} from '@heroicons/react/24/outline';

const BookDetails: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { currentJob: book, isLoading: loading, error } = useAppSelector((state) => state.jobs);
  const audioPlayer = useAudioPlayer();

  useEffect(() => {
    if (jobId) {
      dispatch(fetchJob(jobId));
    }
  }, [dispatch, jobId]);

  // Auto-start audio when page loads
  useEffect(() => {
    if (jobId && book?.status === 'COMPLETED' && !audioPlayer.currentJobId) {
      audioPlayer.loadJob(jobId);
    }
  }, [jobId, book?.status, audioPlayer.currentJobId, audioPlayer.loadJob]);

  const formatDuration = (minutes?: number) => {
    if (!minutes) return 'Unknown';
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'long',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getProviderColor = (provider: string) => {
    switch (provider) {
      case 'openai':
        return 'bg-green-100 text-green-800';
      case 'elevenlabs':
        return 'bg-purple-100 text-purple-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error || !book || book.status !== 'COMPLETED') {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <Alert variant="error">
          {error || 'Book not found or not ready for playback'}
        </Alert>
        <Button
          variant="outline"
          onClick={() => navigate('/library')}
          className="mt-4"
        >
          <ArrowLeftIcon className="h-4 w-4 mr-2" />
          Back to Library
        </Button>
      </div>
    );
  }

  const title = book.title || `Audiobook ${book.id.slice(0, 8)}`;
  const provider = book.config?.voice_config?.provider || 'openai';
  const chapters = book.result_data?.chapters?.length || 0;
  const duration = book.result_data?.duration;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <Button
          variant="outline"
          size="sm"
          onClick={() => navigate('/library')}
          className="mb-6"
        >
          <ArrowLeftIcon className="h-4 w-4 mr-2" />
          Back to Library
        </Button>

        <div className="flex items-center space-x-6 mb-6">
          <div className="flex-shrink-0">
            <div className="w-32 h-32 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center shadow-lg">
              <BookOpenIcon className="h-16 w-16 text-white opacity-90" />
            </div>
          </div>

          <div className="flex-1 min-w-0">
            <h1 className="text-4xl font-bold text-gray-900 mb-2">
              {title}
            </h1>

            <div className="flex items-center space-x-4 mb-4">
              <Badge className={getProviderColor(provider)}>
                {provider}
              </Badge>
              {chapters > 0 && (
                <span className="text-sm text-gray-500">
                  {chapters} chapters
                </span>
              )}
            </div>

            <div className="space-y-2 text-sm text-gray-600">
              <div className="flex items-center">
                <CalendarIcon className="h-4 w-4 mr-2" />
                Created {formatDate(book.created_at)}
              </div>

              {duration && (
                <div className="flex items-center">
                  <ClockIcon className="h-4 w-4 mr-2" />
                  {formatDuration(duration)}
                </div>
              )}

              <div className="flex items-center">
                <SpeakerWaveIcon className="h-4 w-4 mr-2" />
                AI-generated with {provider} voices
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Audio Player */}
      {audioPlayer.currentJobId === jobId && (
        <div className="mb-8">
          <AudioPlayer
            jobId={jobId}
            title={title}
            className="shadow-lg"
          />
        </div>
      )}

      {/* Book Information */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Audio Details</h3>
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-gray-600">Status:</span>
              <Badge className="bg-green-100 text-green-800">
                {book.status}
              </Badge>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Provider:</span>
              <span className="font-medium">{provider}</span>
            </div>
            {duration && (
              <div className="flex justify-between">
                <span className="text-gray-600">Duration:</span>
                <span className="font-medium">{formatDuration(duration)}</span>
              </div>
            )}
            {chapters > 0 && (
              <div className="flex justify-between">
                <span className="text-gray-600">Chapters:</span>
                <span className="font-medium">{chapters}</span>
              </div>
            )}
          </div>
        </Card>

        <Card className="p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Technical Info</h3>
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-gray-600">Job ID:</span>
              <span className="font-mono text-xs">{book.id.slice(0, 8)}...</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Created:</span>
              <span className="text-sm">{formatDate(book.created_at)}</span>
            </div>
            {book.completed_at && (
              <div className="flex justify-between">
                <span className="text-gray-600">Completed:</span>
                <span className="text-sm">{formatDate(book.completed_at)}</span>
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* Chapter List */}
      {chapters > 0 && (
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Chapters</h3>
          <div className="text-sm text-gray-600">
            This audiobook contains {chapters} chapters. Chapter navigation and individual chapter playback coming soon.
          </div>
        </Card>
      )}
    </div>
  );
};

export default BookDetails;
