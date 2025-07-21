import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAppSelector, useAppDispatch } from '../../hooks/redux';
import { logout } from '../../store/slices/authSlice';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import {
  HomeIcon,
  BriefcaseIcon,
  BookOpenIcon,
  MicrophoneIcon,
  ArrowRightOnRectangleIcon,
  Bars3Icon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import clsx from 'clsx';

interface NavbarProps {
  className?: string;
}

const Navbar: React.FC<NavbarProps> = ({ className = '' }) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { user } = useAppSelector((state) => state.auth);
  const { jobs } = useAppSelector((state) => state.jobs);

  const handleLogout = () => {
    dispatch(logout());
    navigate('/login');
  };

  const runningJobsCount = jobs.filter(
    (job) => job.status === 'PROCESSING' || job.status === 'PENDING',
  ).length;

  const navigationItems = [
    {
      name: 'Dashboard',
      href: '/dashboard',
      icon: HomeIcon,
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
    {
      name: 'Voice Assistant',
      href: '/voice-assistant',
      icon: MicrophoneIcon,
    },
  ];

  return (
    <nav className={clsx('bg-white shadow', className)}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          <div className="flex items-center">
            <button
              className="md:hidden mr-2"
              onClick={() => setMenuOpen((open) => !open)}
            >
              {menuOpen ? (
                <XMarkIcon className="h-6 w-6" />
              ) : (
                <Bars3Icon className="h-6 w-6" />
              )}
            </button>
            <span
              onClick={() => navigate('/dashboard')}
              className="text-xl font-bold text-gray-900 cursor-pointer"
            >
              StorytimeTTS
            </span>
            <div className="hidden md:flex md:items-center md:space-x-4 ml-8">
              {navigationItems.map((item) => (
                <NavLink
                  key={item.name}
                  to={item.href}
                  className={({ isActive }) =>
                    clsx(
                      'flex items-center px-3 py-2 text-sm font-medium rounded-md',
                      isActive
                        ? 'text-blue-600 border-b-2 border-blue-600'
                        : 'text-gray-700 hover:text-blue-600',
                    )
                  }
                >
                  <item.icon className="h-5 w-5 mr-1" />
                  <span className="flex-1">{item.name}</span>
                  {item.badge && (
                    <Badge
                      variant="secondary"
                      className="ml-1 bg-red-100 text-red-800"
                    >
                      {item.badge}
                    </Badge>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <span className="hidden sm:block text-sm text-gray-700 truncate">
              {user?.email}
            </span>
            <Button variant="outline" size="sm" onClick={handleLogout}>
              <ArrowRightOnRectangleIcon className="h-4 w-4 mr-1" />
              Sign out
            </Button>
          </div>
        </div>
      </div>
      {menuOpen && (
        <div className="md:hidden px-2 pt-2 pb-3 space-y-1">
          {navigationItems.map((item) => (
            <NavLink
              key={item.name}
              to={item.href}
              onClick={() => setMenuOpen(false)}
              className={({ isActive }) =>
                clsx(
                  'block px-3 py-2 rounded-md text-base font-medium',
                  isActive
                    ? 'text-blue-600 bg-blue-50'
                    : 'text-gray-700 hover:text-blue-600 hover:bg-gray-50',
                )
              }
            >
              <div className="flex items-center">
                <item.icon className="h-5 w-5 mr-2" />
                <span className="flex-1">{item.name}</span>
                {item.badge && (
                  <Badge
                    variant="secondary"
                    className="ml-2 bg-red-100 text-red-800"
                  >
                    {item.badge}
                  </Badge>
                )}
              </div>
            </NavLink>
          ))}
        </div>
      )}
    </nav>
  );
};

export default Navbar;
