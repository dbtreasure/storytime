import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppSelector, useAppDispatch } from '../hooks/redux';
import { fetchJobs, cancelJob } from '../store/slices/jobsSlice';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Spinner } from '../components/ui/Spinner';
import { Alert } from '../components/ui/Alert';
import {
  MagnifyingGlassIcon,
  FunnelIcon,
  EyeIcon,
  XMarkIcon,
  PlayIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ArrowLeftIcon,
} from '@heroicons/react/24/outline';

const Jobs: React.FC = () => {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { jobs, isLoading, error } = useAppSelector((state) => state.jobs);

  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [sortBy, setSortBy] = useState('createdAt');
  const [currentPage, setCurrentPage] = useState(1);
  const [cancellingJobs, setCancellingJobs] = useState<Set<string>>(new Set());

  const jobsPerPage = 10;

  useEffect(() => {
    dispatch(fetchJobs({}));
  }, [dispatch]);

  const handleCancelJob = async (jobId: string) => {
    setCancellingJobs(prev => new Set(prev).add(jobId));
    try {
      await dispatch(cancelJob(jobId)).unwrap();
    } catch (err) {
      console.error('Failed to cancel job:', err);
    } finally {
      setCancellingJobs(prev => {
        const newSet = new Set(prev);
        newSet.delete(jobId);
        return newSet;
      });
    }
  };

  // Filter and sort jobs
  const filteredJobs = jobs
    .filter(job => {
      const matchesSearch = job.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           job.id.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesStatus = statusFilter === 'all' || job.status === statusFilter.toUpperCase();
      return matchesSearch && matchesStatus;
    })
    .sort((a, b) => {
      switch (sortBy) {
        case 'created_at':
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        case 'updated_at':
          return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
        case 'title':
          return (a.title || '').localeCompare(b.title || '');
        case 'status':
          return a.status.localeCompare(b.status);
        default:
          return 0;
      }
    });

  // Pagination
  const totalPages = Math.ceil(filteredJobs.length / jobsPerPage);
  const startIndex = (currentPage - 1) * jobsPerPage;
  const paginatedJobs = filteredJobs.slice(startIndex, startIndex + jobsPerPage);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return <CheckCircleIcon className="h-5 w-5 text-green-600" />;
      case 'PROCESSING':
        return <Spinner size="sm" />;
      case 'PENDING':
        return <ClockIcon className="h-5 w-5 text-blue-600" />;
      case 'FAILED':
        return <ExclamationTriangleIcon className="h-5 w-5 text-red-600" />;
      case 'CANCELLED':
        return <XMarkIcon className="h-5 w-5 text-gray-600" />;
      default:
        return <ClockIcon className="h-5 w-5 text-gray-600" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return 'bg-green-100 text-green-800';
      case 'PROCESSING':
      case 'PENDING':
        return 'bg-blue-100 text-blue-800';
      case 'FAILED':
        return 'bg-red-100 text-red-800';
      case 'CANCELLED':
        return 'bg-gray-100 text-gray-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const canCancelJob = (status: string) => {
    return status === 'PENDING' || status === 'PROCESSING';
  };

  if (isLoading && jobs.length === 0) {
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
        <h1 className="text-3xl font-bold text-gray-900">Jobs</h1>
        <p className="text-gray-600 mt-2">
          Monitor and manage your audiobook generation jobs.
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
                placeholder="Search jobs by title or ID..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
          </div>

          <div className="flex gap-4">
            <div className="min-w-[140px]">
              <Select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                options={[
                  { value: 'all', label: 'All Status' },
                  { value: 'pending', label: 'Pending' },
                  { value: 'running', label: 'Running' },
                  { value: 'completed', label: 'Completed' },
                  { value: 'failed', label: 'Failed' }
                ]}
              />
            </div>

            <div className="min-w-[140px]">
              <Select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                options={[
                  { value: 'createdAt', label: 'Created Date' },
                  { value: 'updatedAt', label: 'Updated Date' },
                  { value: 'title', label: 'Title' },
                  { value: 'status', label: 'Status' }
                ]}
              />
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-gray-500">
            Showing {filteredJobs.length} of {jobs.length} jobs
          </p>
          <Button
            size="sm"
            onClick={() => navigate('/upload')}
          >
            New Job
          </Button>
        </div>
      </Card>

      {/* Jobs List */}
      {filteredJobs.length === 0 ? (
        <Card className="p-8 text-center">
          <FunnelIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-4 text-lg font-medium text-gray-900">
            {jobs.length === 0 ? 'No jobs yet' : 'No jobs match your filters'}
          </h3>
          <p className="mt-2 text-gray-500">
            {jobs.length === 0
              ? 'Get started by creating your first audiobook job.'
              : 'Try adjusting your search or filter criteria.'
            }
          </p>
          {jobs.length === 0 && (
            <Button
              className="mt-4"
              onClick={() => navigate('/upload')}
            >
              Create Your First Job
            </Button>
          )}
        </Card>
      ) : (
        <>
          <div className="space-y-4">
            {paginatedJobs.map((job) => (
              <Card key={job.id} className="p-6 hover:shadow-lg transition-shadow">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4 flex-1">
                    <div className="flex-shrink-0">
                      {getStatusIcon(job.status)}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-3">
                        <h3 className="text-lg font-medium text-gray-900 truncate">
                          {job.title || `Job ${job.id.slice(0, 8)}`}
                        </h3>
                        <Badge className={getStatusColor(job.status)}>
                          {job.status.toLowerCase()}
                        </Badge>
                      </div>

                      <div className="mt-1 flex items-center space-x-4 text-sm text-gray-500">
                        <span>ID: {job.id.slice(0, 8)}</span>
                        <span>•</span>
                        <span>Created: {formatDate(job.created_at)}</span>
                        {job.config?.voice_config?.provider && (
                          <>
                            <span>•</span>
                            <span>Provider: {job.config.voice_config.provider}</span>
                          </>
                        )}
                      </div>

                    </div>
                  </div>

                  <div className="flex items-center space-x-2 ml-4">
                    {job.status === 'COMPLETED' && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => navigate(`/library/${job.id}`)}
                      >
                        <PlayIcon className="h-4 w-4 mr-1" />
                        Play
                      </Button>
                    )}

                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => navigate(`/jobs/${job.id}`)}
                    >
                      <EyeIcon className="h-4 w-4 mr-1" />
                      View
                    </Button>

                    {canCancelJob(job.status) && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleCancelJob(job.id)}
                        disabled={cancellingJobs.has(job.id)}
                        className="text-red-600 hover:text-red-700 border-red-300 hover:border-red-400"
                      >
                        {cancellingJobs.has(job.id) ? (
                          <Spinner size="sm" />
                        ) : (
                          <XMarkIcon className="h-4 w-4" />
                        )}
                      </Button>
                    )}
                  </div>
                </div>
              </Card>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-6">
              <p className="text-sm text-gray-500">
                Showing {startIndex + 1} to {Math.min(startIndex + jobsPerPage, filteredJobs.length)} of {filteredJobs.length} results
              </p>

              <div className="flex space-x-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(page => Math.max(1, page - 1))}
                  disabled={currentPage === 1}
                >
                  Previous
                </Button>

                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  const pageNum = i + 1;
                  return (
                    <Button
                      key={pageNum}
                      variant={currentPage === pageNum ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setCurrentPage(pageNum)}
                    >
                      {pageNum}
                    </Button>
                  );
                })}

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(page => Math.min(totalPages, page + 1))}
                  disabled={currentPage === totalPages}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default Jobs;
