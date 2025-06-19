import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppSelector, useAppDispatch } from '../hooks/redux';
import { fetchJobs } from '../store/slices/jobsSlice';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Spinner } from '../components/ui/Spinner';
import {
  CloudArrowUpIcon,
  BriefcaseIcon,
  BookOpenIcon,
  PlayIcon,
} from '@heroicons/react/24/outline';

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { user } = useAppSelector((state) => state.auth);
  const { jobs, loading: jobsLoading } = useAppSelector((state) => state.jobs);

  useEffect(() => {
    dispatch(fetchJobs());
  }, [dispatch]);

  const recentJobs = jobs.slice(0, 5);
  const completedJobs = jobs.filter(job => job.status === 'completed');
  const runningJobs = jobs.filter(job => job.status === 'running' || job.status === 'pending');
  const failedJobs = jobs.filter(job => job.status === 'failed');

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'running':
      case 'pending':
        return 'bg-blue-100 text-blue-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Welcome Section */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">
          Welcome back!
        </h1>
        <p className="text-gray-600 mt-2">
          Transform your stories into immersive audiobooks with AI-powered voices.
        </p>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <Button
          size="lg"
          onClick={() => navigate('/upload')}
          className="h-20 flex-col space-y-2"
        >
          <CloudArrowUpIcon className="h-6 w-6" />
          <span>Upload New Story</span>
        </Button>
        
        <Button
          variant="outline"
          size="lg"
          onClick={() => navigate('/jobs')}
          className="h-20 flex-col space-y-2"
        >
          <BriefcaseIcon className="h-6 w-6" />
          <span>View All Jobs</span>
        </Button>
        
        <Button
          variant="outline"
          size="lg"
          onClick={() => navigate('/library')}
          className="h-20 flex-col space-y-2"
        >
          <BookOpenIcon className="h-6 w-6" />
          <span>Browse Library</span>
        </Button>
      </div>

      {/* Statistics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <Card className="p-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center">
                <BriefcaseIcon className="h-5 w-5 text-blue-600" />
              </div>
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Total Jobs</p>
              <p className="text-2xl font-semibold text-gray-900">{jobs.length}</p>
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <div className="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center">
                <BookOpenIcon className="h-5 w-5 text-green-600" />
              </div>
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Completed</p>
              <p className="text-2xl font-semibold text-gray-900">{completedJobs.length}</p>
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <div className="w-8 h-8 bg-yellow-100 rounded-lg flex items-center justify-center">
                <div className="w-2 h-2 bg-yellow-600 rounded-full animate-pulse" />
              </div>
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Running</p>
              <p className="text-2xl font-semibold text-gray-900">{runningJobs.length}</p>
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <div className="w-8 h-8 bg-red-100 rounded-lg flex items-center justify-center">
                <div className="w-2 h-2 bg-red-600 rounded-full" />
              </div>
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Failed</p>
              <p className="text-2xl font-semibold text-gray-900">{failedJobs.length}</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Recent Jobs */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-gray-900">Recent Jobs</h2>
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate('/jobs')}
          >
            View All
          </Button>
        </div>

        {jobsLoading ? (
          <div className="flex justify-center py-8">
            <Spinner size="lg" />
          </div>
        ) : recentJobs.length === 0 ? (
          <div className="text-center py-8">
            <BriefcaseIcon className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-4 text-lg font-medium text-gray-900">No jobs yet</h3>
            <p className="mt-2 text-gray-500">
              Get started by uploading your first story.
            </p>
            <Button
              className="mt-4"
              onClick={() => navigate('/upload')}
            >
              Upload Story
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            {recentJobs.map((job) => (
              <div
                key={job.id}
                className="flex items-center justify-between p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors cursor-pointer"
                onClick={() => navigate(`/jobs/${job.id}`)}
              >
                <div className="flex items-center space-x-4">
                  <div className="flex-shrink-0">
                    {job.status === 'completed' ? (
                      <PlayIcon className="h-5 w-5 text-green-600" />
                    ) : job.status === 'running' || job.status === 'pending' ? (
                      <div className="w-2 h-2 bg-blue-600 rounded-full animate-pulse" />
                    ) : (
                      <div className="w-2 h-2 bg-red-600 rounded-full" />
                    )}
                  </div>
                  <div>
                    <h3 className="text-sm font-medium text-gray-900">
                      {job.title || `Job ${job.id.slice(0, 8)}`}
                    </h3>
                    <p className="text-xs text-gray-500">
                      {formatDate(job.createdAt)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <Badge className={getStatusColor(job.status)}>
                    {job.status}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Recent Progress Section */}
      {completedJobs.length > 0 && (
        <Card className="p-6 mt-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-gray-900">Continue Listening</h2>
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/library')}
            >
              View Library
            </Button>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {completedJobs.slice(0, 3).map((job) => (
              <div
                key={job.id}
                className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors cursor-pointer"
                onClick={() => navigate(`/library/${job.id}`)}
              >
                <div className="flex-shrink-0">
                  <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                    <BookOpenIcon className="h-5 w-5 text-blue-600" />
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {job.title || `Story ${job.id.slice(0, 8)}`}
                  </p>
                  <p className="text-xs text-gray-500">
                    Ready to play
                  </p>
                </div>
                <PlayIcon className="h-4 w-4 text-gray-400" />
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
};

export default Dashboard;