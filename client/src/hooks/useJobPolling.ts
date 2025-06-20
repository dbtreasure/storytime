import { useEffect, useRef } from 'react';
import { useAppDispatch, useAppSelector } from './redux';
import { fetchJobs, fetchJob } from '../store/slices/jobsSlice';

interface UseJobPollingOptions {
  interval?: number; // Polling interval in milliseconds
  enabled?: boolean; // Whether polling is enabled
  jobId?: string; // If provided, poll specific job instead of job list
}

export const useJobPolling = (options: UseJobPollingOptions = {}) => {
  const {
    interval = 5000, // Default 5 seconds
    enabled = true,
    jobId,
  } = options;

  const dispatch = useAppDispatch();
  const { jobs, currentJob } = useAppSelector((state) => state.jobs);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // Check if there are any active jobs that need polling
  const hasActiveJobs = jobs.some(job =>
    job.status === 'PENDING' || job.status === 'PROCESSING'
  ) || (currentJob && (currentJob.status === 'PENDING' || currentJob.status === 'PROCESSING'));

  useEffect(() => {
    if (!enabled) return;

    const shouldPoll = jobId ?
      (currentJob?.status === 'PENDING' || currentJob?.status === 'PROCESSING') :
      hasActiveJobs;

    if (shouldPoll) {
      intervalRef.current = setInterval(() => {
        if (jobId) {
          // Poll specific job
          dispatch(fetchJob(jobId));
        } else {
          // Poll job list
          dispatch(fetchJobs({}));
        }
      }, interval);

      return () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      };
    }
  }, [dispatch, enabled, interval, jobId, hasActiveJobs, currentJob?.status]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, []);

  return {
    isPolling: !!intervalRef.current,
    hasActiveJobs,
  };
};
