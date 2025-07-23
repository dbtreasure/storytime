import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { 
  MicrophoneIcon, 
  StopIcon,
  PlayIcon,
  CheckCircleIcon,
  XCircleIcon,
  AcademicCapIcon,
  MagnifyingGlassIcon
} from '@heroicons/react/24/outline';
import { useAppSelector } from '../hooks/redux';
import { 
  PipecatClient,
  PipecatClientOptions,
  RTVIEvent 
} from '@pipecat-ai/client-js';
import { WebSocketTransport } from '@pipecat-ai/websocket-transport';
import { apiClient } from '../services/api';

interface VoiceAssistantState {
  serviceStatus: 'unknown' | 'stopped' | 'starting' | 'running' | 'error';
  clientStatus: 'disconnected' | 'connecting' | 'connected' | 'error';
  error: string | null;
  websocketUrl: string | null;
  mcpFunctions: string[];
}

const VoiceAssistant: React.FC = () => {
  const [searchParams] = useSearchParams();
  const mode = searchParams.get('mode'); // 'tutor' or 'xray'
  const jobId = searchParams.get('jobId');
  
  const [state, setState] = useState<VoiceAssistantState>({
    serviceStatus: 'unknown',
    clientStatus: 'disconnected',
    error: null,
    websocketUrl: null,
    mcpFunctions: []
  });

  const { user } = useAppSelector((state) => state.auth);
  const pipecatClientRef = useRef<PipecatClient | null>(null);
  const botAudioRef = useRef<HTMLAudioElement | null>(null);

  const updateState = useCallback((updates: Partial<VoiceAssistantState>) => {
    setState(prev => ({ ...prev, ...updates }));
  }, []);

  // Check service status
  const checkStatus = useCallback(async () => {
    try {
      const response = await apiClient.get('/api/v1/voice-assistant/status');
      const data = response.data;
      
      updateState({
        serviceStatus: data.status === 'running' ? 'running' : 'stopped',
        websocketUrl: data.websocket_url,
        mcpFunctions: data.mcp_functions || [],
        error: null
      });
    } catch (error: any) {
      updateState({ 
        serviceStatus: 'error',
        error: error.response?.data?.detail || `Failed to check status: ${error.message}` 
      });
    }
  }, [updateState]);

  // Start the voice assistant service
  const startService = useCallback(async () => {
    updateState({ serviceStatus: 'starting', error: null });
    
    try {
      // Pass mode and jobId parameters to backend for context-aware initialization
      const params: any = {};
      if (mode) params.mode = mode;
      if (jobId) params.jobId = jobId;
      
      const response = await apiClient.post('/api/v1/voice-assistant/start', params);
      const data = response.data;
      
      updateState({
        serviceStatus: 'running',
        websocketUrl: data.websocket_url,
        mcpFunctions: data.mcp_functions || [],
        error: null
      });
    } catch (error: any) {
      updateState({ 
        serviceStatus: 'error',
        error: error.response?.data?.detail || `Failed to start service: ${error.message}` 
      });
    }
  }, [updateState]);

  // Stop the voice assistant service
  const stopService = useCallback(async () => {
    try {
      await apiClient.post('/api/v1/voice-assistant/stop');
      
      updateState({
        serviceStatus: 'stopped',
        websocketUrl: null,
        mcpFunctions: [],
        error: null
      });
    } catch (error: any) {
      updateState({ 
        serviceStatus: 'error',
        error: error.response?.data?.detail || `Failed to stop service: ${error.message}` 
      });
    }
  }, [updateState]);

  // Connect to voice assistant using official Pipecat client
  const connectToVoiceAssistant = useCallback(async () => {
    if (!state.websocketUrl) return;
    
    updateState({ clientStatus: 'connecting' });
    
    try {
      // Create bot audio element if it doesn't exist
      if (!botAudioRef.current) {
        botAudioRef.current = document.createElement('audio');
        botAudioRef.current.autoplay = true;
        document.body.appendChild(botAudioRef.current);
      }
      
      const setupAudioTrack = (track: MediaStreamTrack) => {
        console.log('Setting up audio track');
        if (botAudioRef.current) {
          if (botAudioRef.current.srcObject && 'getAudioTracks' in botAudioRef.current.srcObject) {
            const oldTrack = botAudioRef.current.srcObject.getAudioTracks()[0];
            if (oldTrack?.id === track.id) return;
          }
          botAudioRef.current.srcObject = new MediaStream([track]);
        }
      };

      const setupMediaTracks = () => {
        if (!pipecatClientRef.current) return;
        const tracks = pipecatClientRef.current.tracks();
        if (tracks.bot?.audio) {
          setupAudioTrack(tracks.bot.audio);
        }
      };

      // Configure Pipecat client
      const pipecatConfig: PipecatClientOptions = {
        transport: new WebSocketTransport(),
        enableMic: true,
        enableCam: false,
        callbacks: {
          onConnected: () => {
            console.log('Pipecat client connected');
            updateState({ clientStatus: 'connected', error: null });
          },
          onDisconnected: () => {
            console.log('Pipecat client disconnected');
            updateState({ clientStatus: 'disconnected' });
          },
          onBotReady: (data) => {
            console.log('Bot ready:', data);
            setupMediaTracks();
          },
          onUserTranscript: (data) => {
            if (data.final) {
              console.log('User spoke:', data.text);
            }
          },
          onBotTranscript: (data) => {
            console.log('Bot speaking:', data.text);
          },
          onMessageError: (error) => {
            console.error('Pipecat message error:', error);
            updateState({ clientStatus: 'error', error: error.message });
          },
          onError: (error) => {
            console.error('Pipecat error:', error);
            updateState({ clientStatus: 'error', error: error.message });
          },
        },
      };

      // Create Pipecat client
      pipecatClientRef.current = new PipecatClient(pipecatConfig);

      // Set up track listeners
      pipecatClientRef.current.on(RTVIEvent.TrackStarted, (track, participant) => {
        if (!participant?.local && track.kind === 'audio') {
          setupAudioTrack(track);
        }
      });

      pipecatClientRef.current.on(RTVIEvent.TrackStopped, (track, participant) => {
        console.log(`Track stopped: ${track.kind} from ${participant?.name || 'unknown'}`);
      });

      // Initialize devices and connect
      await pipecatClientRef.current.initDevices();
      
      // Use API server endpoint for Pipecat connection with authentication
      const response = await apiClient.post('/api/v1/voice-assistant/connect');
      const connectionData = response.data;
      
      await pipecatClientRef.current.connect({ 
        connectionUrl: connectionData.connectionUrl 
      });

      console.log('Successfully connected to Pipecat voice assistant');
      
    } catch (error) {
      console.error('Failed to connect to voice assistant:', error);
      updateState({ 
        clientStatus: 'error', 
        error: `Connection failed: ${error instanceof Error ? error.message : error}` 
      });
    }
  }, [state.websocketUrl, updateState]);

  // Disconnect from voice assistant
  const disconnectFromVoiceAssistant = useCallback(async () => {
    if (pipecatClientRef.current) {
      try {
        await pipecatClientRef.current.disconnect();
        pipecatClientRef.current = null;
        
        if (botAudioRef.current?.srcObject && 'getAudioTracks' in botAudioRef.current.srcObject) {
          botAudioRef.current.srcObject.getAudioTracks().forEach((track) => track.stop());
          botAudioRef.current.srcObject = null;
        }
        
        updateState({ clientStatus: 'disconnected' });
        console.log('Disconnected from voice assistant');
      } catch (error) {
        console.error('Error disconnecting from voice assistant:', error);
      }
    }
  }, [updateState]);

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

  const getClientStatusColor = () => {
    switch (state.clientStatus) {
      case 'connected': return 'bg-green-500';
      case 'connecting': return 'bg-yellow-500 animate-pulse';
      case 'disconnected': return 'bg-gray-500';
      case 'error': return 'bg-red-500';
      default: return 'bg-gray-400';
    }
  };

  const getClientStatusText = () => {
    switch (state.clientStatus) {
      case 'connected': return 'Connected to Voice Assistant';
      case 'connecting': return 'Connecting...';
      case 'disconnected': return 'Not Connected';
      case 'error': return 'Connection Error';
      default: return 'Unknown';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 flex items-center">
            {mode === 'tutor' && <AcademicCapIcon className="h-8 w-8 text-blue-600 mr-3" />}
            {mode === 'xray' && <MagnifyingGlassIcon className="h-8 w-8 text-purple-600 mr-3" />}
            Voice Assistant
            {mode === 'tutor' && <span className="ml-3 text-blue-600"> - Tutoring Mode</span>}
            {mode === 'xray' && <span className="ml-3 text-purple-600"> - X-ray Lookup</span>}
          </h1>
          <p className="mt-2 text-gray-600">
            {mode === 'tutor' && jobId && 
              `Ready for Socratic dialogue about your audiobook. Ask questions and explore ideas!`}
            {mode === 'xray' && jobId && 
              `Ask contextual questions while listening - "Who is Elizabeth?", "What is happening?", etc.`}
            {!mode && 
              `AI-powered voice assistant with your audiobook library access`}
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

        {/* Client Connection Status */}
        <Card className="mb-6 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-3">
              <div className={`w-3 h-3 rounded-full ${getClientStatusColor()}`} />
              <span className="text-lg font-semibold">{getClientStatusText()}</span>
            </div>
          </div>
          
          <div className="flex space-x-4">
            {state.serviceStatus === 'running' && state.clientStatus === 'disconnected' && (
              <Button
                onClick={connectToVoiceAssistant}
                variant="primary"
                className="flex items-center"
              >
                <MicrophoneIcon className="h-5 w-5 mr-2" />
                Connect & Start Voice Chat
              </Button>
            )}
            
            {state.clientStatus === 'connected' && (
              <Button
                onClick={disconnectFromVoiceAssistant}
                variant="secondary"
                className="flex items-center"
              >
                <StopIcon className="h-5 w-5 mr-2" />
                Disconnect Voice Chat
              </Button>
            )}
            
            {state.clientStatus === 'connecting' && (
              <Button disabled variant="secondary" className="flex items-center">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-900 mr-2"></div>
                Connecting...
              </Button>
            )}
          </div>
        </Card>

        {/* Service Control */}
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