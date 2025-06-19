import React from 'react';
import { clsx } from 'clsx';

interface AlertProps {
  variant?: 'success' | 'error' | 'warning' | 'info';
  children: React.ReactNode;
  className?: string;
}

const Alert: React.FC<AlertProps> = ({
  variant = 'info',
  children,
  className
}) => {
  const baseClasses = 'p-4 rounded-md border';
  
  const variantClasses = {
    success: 'bg-green-50 border-green-200 text-green-800',
    error: 'bg-red-50 border-red-200 text-red-800',
    warning: 'bg-yellow-50 border-yellow-200 text-yellow-800',
    info: 'bg-blue-50 border-blue-200 text-blue-800'
  };

  const iconClasses = {
    success: '✅',
    error: '❌',
    warning: '⚠️',
    info: 'ℹ️'
  };

  return (
    <div
      className={clsx(
        baseClasses,
        variantClasses[variant],
        className
      )}
      role="alert"
    >
      <div className="flex items-start">
        <span className="mr-2 text-lg" aria-hidden="true">
          {iconClasses[variant]}
        </span>
        <div className="flex-1">
          {children}
        </div>
      </div>
    </div>
  );
};

export default Alert;
export { Alert };