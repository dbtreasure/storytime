import React, { useState, useEffect, useCallback } from 'react';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { 
  MicrophoneIcon, 
  StopIcon,
  PlayIcon,
  CheckCircleIcon,
  XCircleIcon
} from '@heroicons/react/24/outline';
import { useAppSelector } from '../hooks/redux';

interface VoiceAssistantState {
  serviceStatus: 'unknown' | 'stopped' | 'starting' | 'running' | 'error';
  error: string | null;
  websocketUrl: string | null;
  mcpFunctions: string[];
}

const VoiceAssistant: React.FC = () => {
  const [state, setState] = useState<VoiceAssistantState>({
    serviceStatus: 'unknown',
    error: null,
    websocketUrl: null,
    mcpFunctions: []
  });

  const { user } = useAppSelector((state) => state.auth);

  const updateState = useCallback((updates: Partial<VoiceAssistantState>) => {
    setState(prev => ({ ...prev, ...updates }));
  }, []);

  // Check service status
  const checkStatus = useCallback(async () => {
    try {
      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${apiBaseUrl}/api/v1/voice-assistant/status`);
      
      if (response.ok) {
        const data = await response.json();
        updateState({
          serviceStatus: data.status === 'running' ? 'running' : 'stopped',
          websocketUrl: data.websocket_url,
          mcpFunctions: data.mcp_functions || [],
          error: null
        });
      } else {
        updateState({ 
          serviceStatus: 'error',
          error: `Status check failed: ${response.status}` 
        });
      }
    } catch (error) {
      updateState({ 
        serviceStatus: 'error',
        error: `Failed to check status: ${error}` 
      });
    }
  }, [updateState]);

  // Start the voice assistant service
  const startService = useCallback(async () => {
    updateState({ serviceStatus: 'starting', error: null });
    
    try {
      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${apiBaseUrl}/api/v1/voice-assistant/start`, {
        method: 'POST'
      });
      
      if (response.ok) {
        const data = await response.json();
        updateState({
          serviceStatus: 'running',
          websocketUrl: data.websocket_url,
          mcpFunctions: data.mcp_functions || [],
          error: null
        });
      } else {
        const errorData = await response.json();
        updateState({ 
          serviceStatus: 'error',
          error: errorData.detail || `Failed to start: ${response.status}` 
        });
      }
    } catch (error) {
      updateState({ 
        serviceStatus: 'error',
        error: `Failed to start service: ${error}` 
      });
    }
  }, [updateState]);

  // Stop the voice assistant service
  const stopService = useCallback(async () => {
    try {
      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${apiBaseUrl}/api/v1/voice-assistant/stop`, {
        method: 'POST'
      });
      
      if (response.ok) {
        updateState({
          serviceStatus: 'stopped',
          websocketUrl: null,
          mcpFunctions: [],
          error: null
        });
      } else {
        updateState({ 
          serviceStatus: 'error',
          error: `Failed to stop: ${response.status}` 
        });
      }
    } catch (error) {
      updateState({ 
        serviceStatus: 'error',
        error: `Failed to stop service: ${error}` 
      });
    }
  }, [updateState]);

  // Connect to the voice assistant WebSocket
  const connectToVoiceAssistant = useCallback(async () => {
    if (!state.websocketUrl) return;
    
    try {
      // Request microphone permission
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Connect to WebSocket
      const ws = new WebSocket(state.websocketUrl);
      
      ws.onopen = () => {
        console.log('Connected to voice assistant');
        // Start listening to microphone and speaking to assistant
      };
      
      ws.onmessage = (event) => {
        // Handle audio and text responses from assistant
        console.log('Received from assistant:', event.data);
      };
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
      
    } catch (error) {
      console.error('Failed to connect:', error);
      alert('Failed to access microphone or connect to voice assistant');
    }
  }, [state.websocketUrl]);

  // Check status on mount
  useEffect(() => {
    checkStatus();
  }, [checkStatus]);

  // Auto-refresh status every 10 seconds when running
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (state.serviceStatus === 'running') {
      interval = setInterval(checkStatus, 10000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [state.serviceStatus, checkStatus]);

  const getStatusColor = () => {
    switch (state.serviceStatus) {
      case 'running': return 'bg-green-500';
      case 'starting': return 'bg-yellow-500 animate-pulse';
      case 'stopped': return 'bg-gray-500';
      case 'error': return 'bg-red-500';
      default: return 'bg-gray-400';
    }
  };

  const getStatusText = () => {
    switch (state.serviceStatus) {
      case 'running': return 'Voice Assistant Running';
      case 'starting': return 'Starting...';
      case 'stopped': return 'Voice Assistant Stopped';
      case 'error': return 'Error';
      default: return 'Unknown Status';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Voice Assistant</h1>
          <p className="mt-2 text-gray-600">
            AI-powered voice assistant with your audiobook library access
          </p>
        </div>

        {/* Service Status */}
        <Card className="mb-6 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-3">
              <div className={`w-3 h-3 rounded-full ${getStatusColor()}`} />
              <span className="text-lg font-semibold">{getStatusText()}</span>
            </div>
            <Button onClick={checkStatus} variant="outline" size="sm">
              Refresh Status
            </Button>
          </div>

          {state.websocketUrl && (
            <div className="mb-4">
              <p className="text-sm text-gray-600">
                WebSocket URL: <code className="bg-gray-100 px-2 py-1 rounded">{state.websocketUrl}</code>
              </p>
            </div>
          )}

          {state.mcpFunctions.length > 0 && (
            <div className="mb-4">
              <p className="text-sm font-medium text-gray-700 mb-2">Available Functions:</p>
              <div className="flex flex-wrap gap-2">
                {state.mcpFunctions.map((func) => (
                  <span key={func} className="bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs">
                    {func}
                  </span>
                ))}
              </div>
            </div>
          )}

          {state.error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded">
              <div className="flex items-center">
                <XCircleIcon className="h-5 w-5 text-red-500 mr-2" />
                <span className="text-sm text-red-700">{state.error}</span>
              </div>
            </div>
          )}
        </Card>

        {/* Control Buttons */}
        <Card className="mb-6 p-6">
          <h2 className="text-xl font-semibold mb-4">Service Control</h2>
          <div className="flex space-x-4">
            <Button
              onClick={startService}
              disabled={state.serviceStatus === 'running' || state.serviceStatus === 'starting'}
              className="flex items-center"
            >
              <PlayIcon className="h-5 w-5 mr-2" />
              Start Voice Assistant
            </Button>

            <Button
              onClick={stopService}
              disabled={state.serviceStatus === 'stopped' || state.serviceStatus === 'starting'}
              variant="secondary"
              className="flex items-center"
            >
              <StopIcon className="h-5 w-5 mr-2" />
              Stop Voice Assistant
            </Button>

            {state.websocketUrl && (
              <Button
                onClick={connectToVoiceAssistant}
                variant="primary"
                className="flex items-center"
              >
                <MicrophoneIcon className="h-5 w-5 mr-2" />
                Start Voice Chat
              </Button>
            )}
          </div>
        </Card>

        {/* Usage Information */}
        <Card className="p-6">
          <h2 className="text-xl font-semibold mb-4">How to Use</h2>
          <div className="space-y-3 text-sm text-gray-600">
            <div className="flex items-start">
              <CheckCircleIcon className="h-5 w-5 text-green-500 mr-2 mt-0.5 flex-shrink-0" />
              <span>Start the voice assistant service using the button above</span>
            </div>
            <div className="flex items-start">
              <CheckCircleIcon className="h-5 w-5 text-green-500 mr-2 mt-0.5 flex-shrink-0" />
              <span>Connect using a WebSocket client or voice application to the provided URL</span>
            </div>
            <div className="flex items-start">
              <CheckCircleIcon className="h-5 w-5 text-green-500 mr-2 mt-0.5 flex-shrink-0" />
              <span>Speak naturally - the assistant can search your library and answer questions</span>
            </div>
            <div className="flex items-start">
              <CheckCircleIcon className="h-5 w-5 text-green-500 mr-2 mt-0.5 flex-shrink-0" />
              <span>Features include: library search, book-specific queries, and content analysis</span>
            </div>
          </div>

          <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded">
            <p className="text-sm text-blue-700">
              <strong>Architecture:</strong> This uses the official Pipecat framework with SileroVAD, 
              OpenAI Realtime API, and MCP integration for robust voice interactions.
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default VoiceAssistant;