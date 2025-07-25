import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAppSelector, useAppDispatch } from '../hooks/redux';
import { useJobPolling } from '../hooks/useJobPolling';
import { fetchJob, cancelJob } from '../store/slices/jobsSlice';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Spinner } from '../components/ui/Spinner';
import { Alert } from '../components/ui/Alert';
import {
  ArrowLeftIcon,
  PlayIcon,
  XMarkIcon,
  ClockIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  BookOpenIcon,
  DocumentTextIcon,
  ArrowUpIcon,
  AcademicCapIcon,
  MagnifyingGlassIcon,
} from '@heroicons/react/24/outline';
import { JobStepResponse } from '../schemas';
import { EyeIcon } from '@heroicons/react/24/outline';

interface TaskTreeNode {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  startTime?: string;
  endTime?: string;
  error?: string;
  children?: TaskTreeNode[];
  progress?: number;
}

const JobDetails: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { currentJob: selectedJob, isLoading: loading, error } = useAppSelector((state) => state.jobs);

  const [expandedTasks, setExpandedTasks] = useState<Set<string>>(new Set());
  const [cancelling, setCancelling] = useState(false);

  // Convert JobStepResponse to TaskTreeNode format
  const convertStepsToTasks = (steps: JobStepResponse[]): TaskTreeNode[] => {
    return steps.map(step => ({
      id: step.id,
      name: step.step_name,
      status: step.status.toLowerCase() as 'pending' | 'running' | 'completed' | 'failed',
      startTime: step.started_at || undefined,
      endTime: step.completed_at || undefined,
      error: step.error_message || undefined,
      progress: step.progress,
      children: []
    }));
  };

  useEffect(() => {
    if (jobId) {
      dispatch(fetchJob({ jobId, isPolling: false }));
    }
  }, [dispatch, jobId]);

  // Enable live job status updates for this specific job
  useJobPolling({ interval: 3000, enabled: true, jobId });

  // Debug job progress
  useEffect(() => {
    if (selectedJob) {
      console.log('Job details:', {
        id: selectedJob.id,
        status: selectedJob.status,
        progress: selectedJob.progress,
        steps: selectedJob.steps?.map(s => ({ name: s.step_name, status: s.status, progress: s.progress }))
      });
      console.log('Job config:', selectedJob.config);
      console.log('Has tutoring analysis:', !!selectedJob.config?.tutoring_analysis);
      if (selectedJob.config?.tutoring_analysis) {
        console.log('Tutoring analysis:', selectedJob.config.tutoring_analysis);
      }
    }
  }, [selectedJob]);

  const handleCancelJob = async () => {
    if (!jobId) return;

    setCancelling(true);
    try {
      await dispatch(cancelJob(jobId)).unwrap();
    } catch (err) {
      console.error('Failed to cancel job:', err);
    } finally {
      setCancelling(false);
    }
  };

  const toggleTaskExpansion = (taskId: string) => {
    setExpandedTasks(prev => {
      const newSet = new Set(prev);
      if (newSet.has(taskId)) {
        newSet.delete(taskId);
      } else {
        newSet.add(taskId);
      }
      return newSet;
    });
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircleIcon className="h-5 w-5 text-green-600" />;
      case 'running':
        return <Spinner size="sm" />;
      case 'failed':
        return <ExclamationTriangleIcon className="h-5 w-5 text-red-600" />;
      case 'pending':
        return <ClockIcon className="h-5 w-5 text-gray-400" />;
      default:
        return <ClockIcon className="h-5 w-5 text-gray-400" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'running':
        return 'bg-blue-100 text-blue-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      case 'pending':
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
      second: '2-digit',
    });
  };

  const formatDuration = (startTime: string, endTime?: string) => {
    const start = new Date(startTime);
    const end = endTime ? new Date(endTime) : new Date();
    const diffMs = end.getTime() - start.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);

    if (diffHour > 0) {
      return `${diffHour}h ${diffMin % 60}m ${diffSec % 60}s`;
    } else if (diffMin > 0) {
      return `${diffMin}m ${diffSec % 60}s`;
    } else {
      return `${diffSec}s`;
    }
  };

  const renderTaskTree = (tasks: TaskTreeNode[], level = 0) => {
    return tasks.map((task) => (
      <div key={task.id} className="mb-2">
        <div
          className={`flex items-center p-3 rounded-lg border ${
            task.status === 'failed' ? 'border-red-200 bg-red-50' : 'border-gray-200 bg-white'
          }`}
          style={{ marginLeft: `${level * 20}px` }}
        >
          <div className="flex items-center flex-1">
            {task.children && task.children.length > 0 && (
              <button
                onClick={() => toggleTaskExpansion(task.id)}
                className="mr-2 p-1 hover:bg-gray-100 rounded"
              >
                {expandedTasks.has(task.id) ? (
                  <ChevronDownIcon className="h-4 w-4" />
                ) : (
                  <ChevronRightIcon className="h-4 w-4" />
                )}
              </button>
            )}

            <div className="mr-3 flex-shrink-0">
              {getStatusIcon(task.status)}
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center space-x-2">
                <h4 className="text-sm font-medium text-gray-900 truncate">
                  {task.name}
                </h4>
                <Badge className={getStatusColor(task.status)}>
                  {task.status}
                </Badge>
              </div>

              <div className="mt-1 flex items-center space-x-4 text-xs text-gray-500">
                {task.startTime && (
                  <span>
                    Started: {formatDate(task.startTime)}
                  </span>
                )}
                {task.startTime && (
                  <span>
                    Duration: {formatDuration(task.startTime, task.endTime)}
                  </span>
                )}
              </div>

              {task.progress !== undefined && task.status === 'running' && (
                <div className="mt-2">
                  <div className="w-full bg-gray-200 rounded-full h-1.5">
                    <div
                      className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
                      style={{ width: `${task.progress}%` }}
                    />
                  </div>
                </div>
              )}

              {task.error && (
                <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
                  <strong>Error:</strong> {task.error}
                </div>
              )}
            </div>
          </div>
        </div>

        {task.children &&
         task.children.length > 0 &&
         expandedTasks.has(task.id) && (
          <div className="mt-2">
            {renderTaskTree(task.children, level + 1)}
          </div>
        )}
      </div>
    ));
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error || !selectedJob) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <Alert variant="error">
          {error || 'Job not found'}
        </Alert>
        <Button
          variant="outline"
          onClick={() => navigate('/jobs')}
          className="mt-4"
        >
          <ArrowLeftIcon className="h-4 w-4 mr-2" />
          Back to Jobs
        </Button>
      </div>
    );
  }

  const canCancel = selectedJob.status === 'PENDING' || selectedJob.status === 'PROCESSING';

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header with Breadcrumbs */}
      <div className="mb-8">
        {/* Breadcrumbs */}
        <div className="flex items-center space-x-2 text-sm text-gray-600 mb-4">
          <button
            onClick={() => navigate('/jobs')}
            className="hover:text-blue-600 transition-colors"
          >
            Jobs
          </button>
          {selectedJob.parent && (
            <>
              <ChevronRightIcon className="h-4 w-4" />
              <button
                onClick={() => navigate(`/jobs/${selectedJob.parent!.id}`)}
                className="hover:text-blue-600 transition-colors flex items-center space-x-1"
              >
                <BookOpenIcon className="h-4 w-4" />
                <span>{selectedJob.parent.title || `Job ${selectedJob.parent.id.slice(0, 8)}`}</span>
              </button>
            </>
          )}
          <ChevronRightIcon className="h-4 w-4" />
          <span className="flex items-center space-x-1">
            {selectedJob.parent_job_id ? (
              <DocumentTextIcon className="h-4 w-4" />
            ) : selectedJob.children && selectedJob.children.length > 0 ? (
              <BookOpenIcon className="h-4 w-4" />
            ) : null}
            <span>{selectedJob.title || `Job ${selectedJob.id.slice(0, 8)}`}</span>
          </span>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/jobs')}
            >
              <ArrowLeftIcon className="h-4 w-4 mr-2" />
              Back to Jobs
            </Button>

            {selectedJob.parent_job_id && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate(`/jobs/${selectedJob.parent_job_id}`)}
                className="text-blue-600 hover:text-blue-700 border-blue-300 hover:border-blue-400"
              >
                <ArrowUpIcon className="h-4 w-4 mr-2" />
                Go to Parent Book
              </Button>
            )}

            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                {selectedJob.title || `Job ${selectedJob.id.slice(0, 8)}`}
              </h1>
              <p className="text-gray-600 mt-1">
                Job ID: {selectedJob.id}
                {selectedJob.parent_job_id && (
                  <span className="ml-2 inline-flex items-center text-blue-600">
                    <DocumentTextIcon className="h-4 w-4 mr-1" />
                    Chapter Job
                  </span>
                )}
                {selectedJob.children && selectedJob.children.length > 0 && (
                  <span className="ml-2 inline-flex items-center text-blue-600">
                    <BookOpenIcon className="h-4 w-4 mr-1" />
                    Book Job ({selectedJob.children.length} chapters)
                  </span>
                )}
              </p>
            </div>
          </div>

        <div className="flex items-center space-x-2">
          {selectedJob.status === 'COMPLETED' && (
            <Button
              onClick={() => navigate(`/library/${selectedJob.id}`)}
            >
              <PlayIcon className="h-4 w-4 mr-2" />
              Play Audiobook
            </Button>
          )}

          {/* Tutoring buttons - show if tutoring analysis is available */}
          {selectedJob.config?.tutoring_analysis && (
            <>
              <Button
                variant="outline"
                onClick={() => {
                  // Navigate to voice assistant with tutoring context
                  navigate(`/voice-assistant?mode=tutor&jobId=${selectedJob.id}`);
                }}
                className="text-blue-600 hover:text-blue-700 border-blue-300 hover:border-blue-400"
              >
                <AcademicCapIcon className="h-4 w-4 mr-2" />
                Ask Tutor
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  // Navigate to voice assistant with X-ray lookup context
                  navigate(`/voice-assistant?mode=xray&jobId=${selectedJob.id}`);
                }}
                className="text-purple-600 hover:text-purple-700 border-purple-300 hover:border-purple-400"
              >
                <MagnifyingGlassIcon className="h-4 w-4 mr-2" />
                X-ray Lookup
              </Button>
            </>
          )}

          {canCancel && (
            <Button
              variant="outline"
              onClick={handleCancelJob}
              disabled={cancelling}
              className="text-red-600 hover:text-red-700 border-red-300 hover:border-red-400"
            >
              {cancelling ? (
                <Spinner size="sm" />
              ) : (
                <XMarkIcon className="h-4 w-4 mr-2" />
              )}
              Cancel Job
            </Button>
          )}
        </div>
        </div>
      </div>

      {/* Job Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <Card className="p-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              {getStatusIcon(selectedJob.status)}
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Status</p>
              <div className="flex items-center space-x-2 mt-1">
                <Badge className={getStatusColor(selectedJob.status)}>
                  {selectedJob.status}
                </Badge>
              </div>
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <InformationCircleIcon className="h-5 w-5 text-blue-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Provider</p>
              <p className="text-lg font-semibold text-gray-900 mt-1">
                {selectedJob.config?.provider || 'OpenAI'}
              </p>
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <ClockIcon className="h-5 w-5 text-gray-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Created</p>
              <p className="text-lg font-semibold text-gray-900 mt-1">
                {formatDate(selectedJob.created_at)}
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Progress */}
      {selectedJob.progress !== undefined && (
        <Card className="p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Overall Progress</h2>
            <span className="text-sm text-gray-500">
              {selectedJob.status === 'COMPLETED' ? '100' : Math.round(selectedJob.progress)}%
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-3">
            <div
              className="bg-blue-600 h-3 rounded-full transition-all duration-300"
              style={{ width: `${selectedJob.status === 'COMPLETED' ? 100 : selectedJob.progress}%` }}
            />
          </div>
        </Card>
      )}

      {/* Related Jobs (Children) */}
      {selectedJob.children && selectedJob.children.length > 0 && (
        <Card className="p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <BookOpenIcon className="h-5 w-5 mr-2" />
            Chapter Jobs ({selectedJob.children.length})
          </h2>
          <div className="space-y-3">
            {selectedJob.children.map((child) => (
              <div key={child.id} className="flex items-center justify-between p-3 border rounded-lg hover:bg-gray-50">
                <div className="flex items-center space-x-3">
                  <DocumentTextIcon className="h-5 w-5 text-green-600" />
                  <div>
                    <h4 className="font-medium">{child.title || `Chapter ${child.id.slice(0, 8)}`}</h4>
                    <p className="text-sm text-gray-500">Created: {formatDate(child.created_at)}</p>
                  </div>
                  <Badge className={getStatusColor(child.status)}>
                    {child.status.toLowerCase()}
                  </Badge>
                </div>
                <div className="flex items-center space-x-2">
                  {child.status === 'COMPLETED' && (
                    <Button variant="outline" size="sm" onClick={() => navigate(`/library/${child.id}`)}>
                      <PlayIcon className="h-4 w-4 mr-1" />
                      Play
                    </Button>
                  )}
                  <Button variant="outline" size="sm" onClick={() => navigate(`/jobs/${child.id}`)}>
                    <EyeIcon className="h-4 w-4 mr-1" />
                    View
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Task Tree */}
      <Card className="p-6 mb-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-gray-900">Task Progress</h2>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              // Toggle all tasks
              const allTaskIds = selectedJob.steps?.map(t => t.id) || [];
              if (allTaskIds.every(id => expandedTasks.has(id))) {
                setExpandedTasks(new Set());
              } else {
                setExpandedTasks(new Set(allTaskIds));
              }
            }}
          >
            {selectedJob.steps?.every(t => expandedTasks.has(t.id)) ? 'Collapse All' : 'Expand All'}
          </Button>
        </div>

        {selectedJob.steps && selectedJob.steps.length > 0 ? (
          <div className="space-y-2">
            {renderTaskTree(convertStepsToTasks(selectedJob.steps))}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">
            <ClockIcon className="mx-auto h-12 w-12 text-gray-400 mb-4" />
            <p>Task details will appear here once the job starts processing.</p>
          </div>
        )}
      </Card>

      {/* Error Message */}
      {selectedJob.error_message && (
        <Card className="p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Error Details</h2>
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-start space-x-2">
              <ExclamationTriangleIcon className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm text-red-700">
                  {selectedJob.error_message}
                </p>
              </div>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
};

export default JobDetails;
