import React from 'react';
import { clsx } from 'clsx';

interface BadgeProps {
  variant?: 'pending' | 'running' | 'completed' | 'failed' | 'secondary';
  size?: 'sm' | 'md';
  children: React.ReactNode;
  className?: string;
}

const Badge: React.FC<BadgeProps> = ({
  variant = 'pending',
  size = 'md',
  children,
  className
}) => {
  const baseClasses = 'inline-flex items-center font-medium rounded-full';

  const variantClasses = {
    pending: 'bg-yellow-100 text-yellow-800',
    running: 'bg-blue-100 text-blue-800',
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
    secondary: 'bg-gray-100 text-gray-800'
  };

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-sm'
  };

  const dotClasses = {
    pending: 'bg-yellow-400',
    running: 'bg-blue-400',
    completed: 'bg-green-400',
    failed: 'bg-red-400',
    secondary: 'bg-gray-400'
  };

  return (
    <span
      className={clsx(
        baseClasses,
        variantClasses[variant],
        sizeClasses[size],
        className
      )}
    >
      <span
        className={clsx(
          'w-1.5 h-1.5 rounded-full mr-1.5',
          dotClasses[variant]
        )}
        aria-hidden="true"
      />
      {children}
    </span>
  );
};

export default Badge;
export { Badge };
