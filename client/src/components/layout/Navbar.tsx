import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAppSelector, useAppDispatch } from '../../hooks/redux';
import { logout } from '../../store/slices/authSlice';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import {
  HomeIcon,
  CloudArrowUpIcon,
  BriefcaseIcon,
  BookOpenIcon,
  UserCircleIcon,
  ArrowRightOnRectangleIcon,
} from '@heroicons/react/24/outline';

interface NavbarProps {
  className?: string;
}

const Navbar: React.FC<NavbarProps> = ({ className = '' }) => {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { user } = useAppSelector((state) => state.auth);
  const { jobs } = useAppSelector((state) => state.jobs);

  const handleLogout = () => {
    dispatch(logout());
    navigate('/login');
  };

  const runningJobsCount = jobs.filter(
    job => job.status === 'running' || job.status === 'pending'
  ).length;

  const navigationItems = [
    {
      name: 'Dashboard',
      href: '/dashboard',
      icon: HomeIcon,
    },
    {
      name: 'Upload',
      href: '/upload',
      icon: CloudArrowUpIcon,
    },
    {
      name: 'Jobs',
      href: '/jobs',
      icon: BriefcaseIcon,
      badge: runningJobsCount > 0 ? runningJobsCount : undefined,
    },
    {
      name: 'Library',
      href: '/library',
      icon: BookOpenIcon,
    },
  ];

  return (
    <div className={`bg-white shadow-lg border-r border-gray-200 flex flex-col h-full ${className}`}>
      {/* Header */}
      <div className="p-6 border-b border-gray-200">
        <h1 className="text-xl font-bold text-gray-900">StorytimeTTS</h1>
        <p className="text-sm text-gray-500 mt-1">
          AI-powered audiobook generation
        </p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-2">
        {navigationItems.map((item) => (
          <NavLink
            key={item.name}
            to={item.href}
            className={({ isActive }) =>
              `group flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-colors duration-200 ${
                isActive
                  ? 'bg-blue-50 text-blue-700 border-r-2 border-blue-700'
                  : 'text-gray-700 hover:bg-gray-50 hover:text-gray-900'
              }`
            }
          >
            <item.icon
              className="mr-3 h-5 w-5 flex-shrink-0"
              aria-hidden="true"
            />
            <span className="flex-1">{item.name}</span>
            {item.badge && (
              <Badge
                variant="secondary"
                className="ml-2 bg-red-100 text-red-800"
              >
                {item.badge}
              </Badge>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Job Status Indicator */}
      {runningJobsCount > 0 && (
        <div className="px-4 py-3 bg-blue-50 border-t border-blue-200">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <div className="w-2 h-2 bg-blue-600 rounded-full animate-pulse"></div>
            </div>
            <div className="ml-3 flex-1 min-w-0">
              <p className="text-sm text-blue-800 font-medium">
                {runningJobsCount} job{runningJobsCount > 1 ? 's' : ''} running
              </p>
            </div>
          </div>
        </div>
      )}

      {/* User Profile */}
      <div className="p-4 border-t border-gray-200">
        <div className="flex items-center space-x-3 mb-3">
          <div className="flex-shrink-0">
            <UserCircleIcon className="h-8 w-8 text-gray-400" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">
              {user?.firstName} {user?.lastName}
            </p>
            <p className="text-xs text-gray-500 truncate">
              {user?.email}
            </p>
          </div>
        </div>
        
        <Button
          variant="outline"
          size="sm"
          onClick={handleLogout}
          className="w-full justify-start"
        >
          <ArrowRightOnRectangleIcon className="mr-2 h-4 w-4" />
          Sign out
        </Button>
      </div>
    </div>
  );
};

export default Navbar;