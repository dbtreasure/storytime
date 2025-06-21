import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppSelector, useAppDispatch } from '../hooks/redux';
import { fetchJobs } from '../store/slices/jobsSlice';
import { useAudioPlayer } from '../hooks/useAudioPlayer';
// import AudioPlayer from '../components/AudioPlayer';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Spinner } from '../components/ui/Spinner';
import { Alert } from '../components/ui/Alert';
import {
  BookOpenIcon,
  PlayIcon,
  PauseIcon,
  MagnifyingGlassIcon,
  FunnelIcon,
  CalendarIcon,
  ClockIcon,
  SpeakerWaveIcon,
  CloudArrowUpIcon,
  ArrowLeftIcon,
} from '@heroicons/react/24/outline';

interface AudioBook {
  id: string;
  title: string;
  createdAt: string;
  duration?: number;
  ttsProvider: string;
  chapters?: number;
  progress?: number; // 0-100, listening progress
  thumbnail?: string;
  description?: string;
}

const Library: React.FC = () => {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { jobs, isLoading: loading, error } = useAppSelector((state) => state.jobs);
  const audioPlayer = useAudioPlayer();

  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('createdAt');
  const [filterBy, setFilterBy] = useState('all');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  useEffect(() => {
    dispatch(fetchJobs({ status: 'COMPLETED' }));
  }, [dispatch]);


  // Filter completed jobs to get audiobooks
  const audiobooks: AudioBook[] = jobs
    .filter(job => job.status === 'COMPLETED')
    .map(job => ({
      id: job.id,
      title: job.title || `Audiobook ${job.id.slice(0, 8)}`,
      createdAt: job.created_at,
      ttsProvider: job.config?.voice_config?.provider || 'openai',
      chapters: job.result_data?.chapters?.length || 0,
      duration: job.result_data?.duration,
      progress: 0, // Progress would come from separate progress API
      description: undefined,
    }));

  // Filter and sort audiobooks
  const filteredAudiobooks = audiobooks
    .filter(book => {
      const matchesSearch = book.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           book.id.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesFilter = filterBy === 'all' ||
                           (filterBy === 'openai' && book.ttsProvider === 'openai') ||
                           (filterBy === 'elevenlabs' && book.ttsProvider === 'elevenlabs') ||
                           (filterBy === 'in_progress' && book.progress && book.progress > 0 && book.progress < 100) ||
                           (filterBy === 'completed' && book.progress === 100);
      return matchesSearch && matchesFilter;
    })
    .sort((a, b) => {
      switch (sortBy) {
        case 'createdAt':
          return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
        case 'title':
          return a.title.localeCompare(b.title);
        case 'duration':
          return (b.duration || 0) - (a.duration || 0);
        case 'progress':
          return (b.progress || 0) - (a.progress || 0);
        default:
          return 0;
      }
    });

  const formatDuration = (minutes?: number) => {
    if (!minutes) return 'Unknown';
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
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

  const handlePlayAudio = (bookId: string) => {
    console.log('handlePlayAudio called:', {
      bookId,
      currentJobId: audioPlayer.currentJobId,
      isPlaying: audioPlayer.isPlaying,
      isLoading: audioPlayer.isLoading
    });

    if (audioPlayer.currentJobId === bookId && audioPlayer.isPlaying) {
      audioPlayer.pause();
    } else if (audioPlayer.currentJobId === bookId && !audioPlayer.isPlaying) {
      audioPlayer.play();
    } else {
      audioPlayer.loadJob(bookId);
    }
  };

  const isCurrentlyPlaying = (bookId: string) => {
    return audioPlayer.currentJobId === bookId && audioPlayer.isPlaying;
  };

  const isCurrentBook = (bookId: string) => {
    return audioPlayer.currentJobId === bookId;
  };

  const renderGridView = () => (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
      {filteredAudiobooks.map((book) => (
        <Card
          key={book.id}
          className="overflow-hidden hover:shadow-lg transition-shadow cursor-pointer"
          onClick={() => navigate(`/library/${book.id}`)}
        >
          <div className="aspect-w-16 aspect-h-9 bg-gradient-to-br from-blue-500 to-purple-600 relative">
            <div className="absolute inset-0 flex items-center justify-center">
              <BookOpenIcon className="h-12 w-12 text-white opacity-80" />
            </div>
            <div className="absolute top-2 right-2">
              <Badge className={getProviderColor(book.ttsProvider)}>
                {book.ttsProvider}
              </Badge>
            </div>
          </div>

          <div className="p-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-2 line-clamp-2">
              {book.title}
            </h3>

            <div className="space-y-2 text-sm text-gray-500 mb-4">
              <div className="flex items-center">
                <CalendarIcon className="h-4 w-4 mr-2" />
                {formatDate(book.createdAt)}
              </div>

              {book.duration && (
                <div className="flex items-center">
                  <ClockIcon className="h-4 w-4 mr-2" />
                  {formatDuration(book.duration)}
                </div>
              )}

              {book.chapters && book.chapters > 0 && (
                <div className="flex items-center">
                  <BookOpenIcon className="h-4 w-4 mr-2" />
                  {book.chapters} chapters
                </div>
              )}
            </div>

            {book.progress && book.progress > 0 && (
              <div className="mb-4">
                <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                  <span>Progress</span>
                  <span>{Math.round(book.progress || 0)}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${book.progress || 0}%` }}
                  />
                </div>
              </div>
            )}

            <Button
              className="w-full"
              onClick={(e) => {
                e.stopPropagation(); // Prevent card navigation
                handlePlayAudio(book.id);
              }}
              disabled={audioPlayer.isLoading && isCurrentBook(book.id)}
            >
              {audioPlayer.isLoading && isCurrentBook(book.id) ? (
                <Spinner size="sm" />
              ) : isCurrentlyPlaying(book.id) ? (
                <PauseIcon className="h-4 w-4 mr-2" />
              ) : (
                <PlayIcon className="h-4 w-4 mr-2" />
              )}
              {isCurrentlyPlaying(book.id) ? 'Pause' : book.progress && book.progress > 0 ? 'Continue' : 'Play'}
            </Button>
          </div>
        </Card>
      ))}
    </div>
  );

  const renderListView = () => (
    <div className="space-y-4">
      {filteredAudiobooks.map((book) => (
        <Card
          key={book.id}
          className="p-6 hover:shadow-lg transition-shadow cursor-pointer"
          onClick={() => navigate(`/library/${book.id}`)}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4 flex-1">
              <div className="flex-shrink-0">
                <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
                  <BookOpenIcon className="h-8 w-8 text-white" />
                </div>
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center space-x-3 mb-1">
                  <h3 className="text-lg font-semibold text-gray-900 truncate">
                    {book.title}
                  </h3>
                  <Badge className={getProviderColor(book.ttsProvider)}>
                    {book.ttsProvider}
                  </Badge>
                </div>

                <div className="flex items-center space-x-4 text-sm text-gray-500">
                  <span>{formatDate(book.createdAt)}</span>
                  {book.duration && (
                    <>
                      <span>•</span>
                      <span>{formatDuration(book.duration)}</span>
                    </>
                  )}
                  {book.chapters && book.chapters > 0 && (
                    <>
                      <span>•</span>
                      <span>{book.chapters} chapters</span>
                    </>
                  )}
                </div>

                {book.progress && book.progress > 0 && (
                  <div className="mt-2 max-w-xs">
                    <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                      <span>Progress</span>
                      <span>{Math.round(book.progress || 0)}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-1.5">
                      <div
                        className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
                        style={{ width: `${book.progress || 0}%` }}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="flex items-center space-x-2 ml-4">
              <Button
                onClick={(e) => {
                  e.stopPropagation(); // Prevent card navigation
                  handlePlayAudio(book.id);
                }}
                disabled={audioPlayer.isLoading && isCurrentBook(book.id)}
              >
                {audioPlayer.isLoading && isCurrentBook(book.id) ? (
                  <Spinner size="sm" />
                ) : isCurrentlyPlaying(book.id) ? (
                  <PauseIcon className="h-4 w-4 mr-2" />
                ) : (
                  <PlayIcon className="h-4 w-4 mr-2" />
                )}
                {isCurrentlyPlaying(book.id) ? 'Pause' : book.progress && book.progress > 0 ? 'Continue' : 'Play'}
              </Button>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );

  if (loading && audiobooks.length === 0) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-8">
        <Button
          variant="outline"
          size="sm"
          onClick={() => navigate('/dashboard')}
          className="mb-4"
        >
          <ArrowLeftIcon className="h-4 w-4 mr-2" />
          Back to Dashboard
        </Button>
        <h1 className="text-3xl font-bold text-gray-900">My Library</h1>
        <p className="text-gray-600 mt-2">
          Your collection of AI-generated audiobooks.
        </p>
      </div>

      {error && (
        <Alert variant="error" className="mb-6">
          {error}
        </Alert>
      )}

      {/* Filters and Search */}
      <Card className="p-6 mb-6">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1">
            <div className="relative">
              <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
              <Input
                type="text"
                placeholder="Search your library..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
          </div>

          <div className="flex gap-4">
            <div className="min-w-[140px]">
              <Select
                value={filterBy}
                onChange={(e) => setFilterBy(e.target.value)}
                options={[
                  { value: 'all', label: 'All Books' },
                  { value: 'openai', label: 'OpenAI' },
                  { value: 'elevenlabs', label: 'ElevenLabs' },
                  { value: 'in_progress', label: 'In Progress' },
                  { value: 'completed', label: 'Completed' }
                ]}
              />
            </div>

            <div className="min-w-[140px]">
              <Select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                options={[
                  { value: 'createdAt', label: 'Date Added' },
                  { value: 'title', label: 'Title' },
                  { value: 'duration', label: 'Duration' },
                  { value: 'progress', label: 'Progress' }
                ]}
              />
            </div>

            <div className="flex border border-gray-300 rounded-lg">
              <button
                onClick={() => setViewMode('grid')}
                className={`p-2 ${viewMode === 'grid' ? 'bg-blue-100 text-blue-600' : 'text-gray-400'}`}
              >
                <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M5 3a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2V5a2 2 0 00-2-2H5zM5 11a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2v-2a2 2 0 00-2-2H5zM11 5a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V5zM11 13a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                </svg>
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`p-2 ${viewMode === 'list' ? 'bg-blue-100 text-blue-600' : 'text-gray-400'}`}
              >
                <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-gray-500">
            {filteredAudiobooks.length} of {audiobooks.length} audiobooks
          </p>
          <Button
            size="sm"
            onClick={() => navigate('/upload')}
          >
            <CloudArrowUpIcon className="h-4 w-4 mr-2" />
            Add New Book
          </Button>
        </div>
      </Card>

      {/* Library Content */}
      {filteredAudiobooks.length === 0 ? (
        <Card className="p-8 text-center">
          <div className="max-w-md mx-auto">
            {audiobooks.length === 0 ? (
              <>
                <BookOpenIcon className="mx-auto h-12 w-12 text-gray-400" />
                <h3 className="mt-4 text-lg font-medium text-gray-900">
                  Your library is empty
                </h3>
                <p className="mt-2 text-gray-500">
                  Start building your audiobook collection by uploading your first story.
                </p>
                <Button
                  className="mt-4"
                  onClick={() => navigate('/upload')}
                >
                  <CloudArrowUpIcon className="h-4 w-4 mr-2" />
                  Upload Your First Story
                </Button>
              </>
            ) : (
              <>
                <FunnelIcon className="mx-auto h-12 w-12 text-gray-400" />
                <h3 className="mt-4 text-lg font-medium text-gray-900">
                  No books match your filters
                </h3>
                <p className="mt-2 text-gray-500">
                  Try adjusting your search or filter criteria to find your audiobooks.
                </p>
                <Button
                  variant="outline"
                  className="mt-4"
                  onClick={() => {
                    setSearchTerm('');
                    setFilterBy('all');
                  }}
                >
                  Clear Filters
                </Button>
              </>
            )}
          </div>
        </Card>
      ) : (
        viewMode === 'grid' ? renderGridView() : renderListView()
      )}

      {/* Stats */}
      {audiobooks.length > 0 && (
        <div className="mt-8 grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="p-4 text-center">
            <BookOpenIcon className="mx-auto h-8 w-8 text-blue-600 mb-2" />
            <p className="text-2xl font-bold text-gray-900">{audiobooks.length}</p>
            <p className="text-sm text-gray-500">Total Books</p>
          </Card>

          <Card className="p-4 text-center">
            <ClockIcon className="mx-auto h-8 w-8 text-green-600 mb-2" />
            <p className="text-2xl font-bold text-gray-900">
              {formatDuration(audiobooks.reduce((total, book) => total + (book.duration || 0), 0))}
            </p>
            <p className="text-sm text-gray-500">Total Duration</p>
          </Card>

          <Card className="p-4 text-center">
            <SpeakerWaveIcon className="mx-auto h-8 w-8 text-purple-600 mb-2" />
            <p className="text-2xl font-bold text-gray-900">
              {audiobooks.filter(book => book.ttsProvider === 'openai').length}
            </p>
            <p className="text-sm text-gray-500">OpenAI Books</p>
          </Card>

          <Card className="p-4 text-center">
            <SpeakerWaveIcon className="mx-auto h-8 w-8 text-orange-600 mb-2" />
            <p className="text-2xl font-bold text-gray-900">
              {audiobooks.filter(book => book.ttsProvider === 'elevenlabs').length}
            </p>
            <p className="text-sm text-gray-500">ElevenLabs Books</p>
          </Card>
        </div>
      )}

    </div>
  );
};

export default Library;
