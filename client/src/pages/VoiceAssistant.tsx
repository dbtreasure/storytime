import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Input } from '../components/ui/Input';
import { 
  MicrophoneIcon, 
  SpeakerWaveIcon,
  StopIcon,
  PlayIcon 
} from '@heroicons/react/24/outline';
import { useAppSelector } from '../hooks/redux';

interface VoiceAssistantState {
  isConnected: boolean;
  isRecording: boolean;
  isPlaying: boolean;
  transcript: string;
  response: string;
  error: string | null;
  connectionStatus: 'disconnected' | 'connecting' | 'connected' | 'failed';
  reconnectAttempts: number;
}

const VoiceAssistant: React.FC = () => {
  const [state, setState] = useState<VoiceAssistantState>({
    isConnected: false,
    isRecording: false,
    isPlaying: false,
    transcript: '',
    response: '',
    error: null,
    connectionStatus: 'disconnected',
    reconnectAttempts: 0
  });
  
  const [jobId, setJobId] = useState('');
  const [testMessage, setTestMessage] = useState('What\'s in my library about luck?');
  
  const { user } = useAppSelector((state) => state.auth);
  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const audioQueueRef = useRef<string[]>([]);
  const isPlayingAudioRef = useRef<boolean>(false);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const maxReconnectAttempts = 5;
  const reconnectBaseDelay = 1000; // 1 second

  const updateState = useCallback((updates: Partial<VoiceAssistantState>) => {
    setState(prev => ({ ...prev, ...updates }));
  }, []);

  // Test token validity
  const testToken = useCallback(async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      updateState({ error: 'No token found' });
      return;
    }
    
    try {
      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${apiBaseUrl}/api/v1/auth/me`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (response.ok) {
        const user = await response.json();
        updateState({ error: null });
        console.log('Token is valid, user:', user);
      } else {
        updateState({ error: `Token test failed: ${response.status} ${response.statusText}` });
        console.error('Token test failed:', response.status, await response.text());
      }
    } catch (error) {
      updateState({ error: `Token test error: ${error}` });
      console.error('Token test error:', error);
    }
  }, [updateState]);

  // Convert Float32Array to Int16Array PCM16 format (from OpenAI best practices)
  const floatTo16BitPCM = useCallback((float32Array: Float32Array): Int16Array => {
    const int16Array = new Int16Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i++) {
      const s = Math.max(-1, Math.min(1, float32Array[i]));
      int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return int16Array;
  }, []);

  // Initialize audio context
  const initializeAudio = useCallback(async () => {
    try {
      audioContextRef.current = new AudioContext({ sampleRate: 24000 });
      return true;
    } catch (error) {
      console.error('Failed to initialize audio:', error);
      updateState({ error: 'Failed to initialize audio system' });
      return false;
    }
  }, [updateState]);

  // Clean up reconnection timeout
  const clearReconnectTimeout = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  // Schedule reconnection with exponential backoff
  const scheduleReconnect = useCallback((attempts: number) => {
    if (attempts >= maxReconnectAttempts) {
      return;
    }
    
    const delay = Math.min(reconnectBaseDelay * Math.pow(2, attempts), 30000); // Max 30 seconds
    console.log(`Scheduling reconnection attempt ${attempts + 1} in ${delay}ms`);
    
    clearReconnectTimeout();
    reconnectTimeoutRef.current = setTimeout(() => {
      connectToOpenAI();
    }, delay);
  }, [clearReconnectTimeout]);

  // Connect to OpenAI Realtime API via our FastAPI proxy
  const connectToOpenAI = useCallback(async () => {
    try {
      // Don't attempt if already connected or connecting
      if (state.connectionStatus === 'connected' || state.connectionStatus === 'connecting') {
        return;
      }
      
      const token = localStorage.getItem('access_token');
      console.log('Retrieved token from localStorage:', token ? `${token.substring(0, 20)}...` : 'null');
      if (!token) {
        updateState({ error: 'Authentication required', connectionStatus: 'failed' });
        return;
      }
      
      updateState({ connectionStatus: 'connecting', error: null });

      // Connect to our WebSocket proxy which handles OpenAI auth
      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
      const wsUrl = apiBaseUrl.replace('http', 'ws') + '/api/v1/voice-assistant/realtime';
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log('Connected to Voice Assistant');
        
        // Send authentication first
        ws.send(JSON.stringify({
          type: 'auth',
          token: token
        }));
        
        // Don't mark as connected yet - wait for auth success
        updateState({ 
          connectionStatus: 'connecting',
          error: null
        });
        
        // Send session configuration after auth (with state check)
        setTimeout(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
              type: 'session.update',
            session: {
              modalities: ['text', 'audio'],
              instructions: `You are a voice assistant for StorytimeTTS, an AI-powered audiobook platform. 
                You can help users search their audiobook library, find specific content within books, 
              and answer questions about their audiobooks. 
              When users ask about their audiobooks or want to search for specific content, 
              use the provided tools to access their library.`,
            voice: 'alloy',
            input_audio_format: 'pcm16',
            output_audio_format: 'pcm16',
            input_audio_transcription: {
              model: 'whisper-1'
            },
            turn_detection: {
              type: 'server_vad',
              threshold: 0.5,
              prefix_padding_ms: 300,
              silence_duration_ms: 200
            },
            tools: [
              {
                type: 'function',
                name: 'search_library',
                description: 'Search across user\'s entire audiobook library using the provided query string and returns matching results with excerpts.',
                parameters: {
                  type: 'object',
                  properties: {
                    query: {
                      type: 'string',
                      description: 'Search query to find content across all audiobooks'
                    },
                    max_results: {
                      type: 'integer',
                      default: 10,
                      description: 'Maximum number of results to return'
                    }
                  },
                  required: ['query']
                }
              },
              {
                type: 'function',
                name: 'search_job',
                description: 'Search within specific audiobook content by job ID and returns relevant excerpts from that specific book.',
                parameters: {
                  type: 'object',
                  properties: {
                    job_id: {
                      type: 'string',
                      description: 'The job ID of the specific audiobook to search within'
                    },
                    query: {
                      type: 'string',
                      description: 'Search query to find content within the specific audiobook'
                    },
                    max_results: {
                      type: 'integer',
                      default: 5,
                      description: 'Maximum number of results to return'
                    }
                  },
                  required: ['job_id', 'query']
                }
              },
              {
                type: 'function',
                name: 'ask_job_question',
                description: 'Ask a specific question about an audiobook\'s content and get an AI-generated answer based on the book\'s content.',
                parameters: {
                  type: 'object',
                  properties: {
                    job_id: {
                      type: 'string',
                      description: 'The job ID of the audiobook to ask about'
                    },
                    question: {
                      type: 'string',
                      description: 'The question to ask about the audiobook\'s content'
                    }
                  },
                  required: ['job_id', 'question']
                }
              }
            ],
            tool_choice: 'auto',
            temperature: 0.8,
            max_response_output_tokens: 4096
            }
          }));
          }
        }, 500);
      };

      ws.onmessage = async (event) => {
        try {
          const message = JSON.parse(event.data);
          await handleOpenAIMessage(message);
        } catch (error) {
          console.error('Error handling OpenAI message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        updateState({ 
          error: 'Connection to OpenAI failed',
          connectionStatus: 'failed'
        });
      };

      ws.onclose = (event) => {
        console.log('Disconnected from OpenAI:', event.code, event.reason);
        updateState(prev => ({ 
          isConnected: false,
          connectionStatus: 'disconnected',
          reconnectAttempts: prev.reconnectAttempts + 1
        }));
        
        // Don't reconnect if:
        // - Connection was closed cleanly (code 1000)
        // - Max attempts reached
        // - Auth failure (code 1008 - Invalid token)
        const currentAttempts = state.reconnectAttempts + 1;
        const shouldReconnect = event.code !== 1000 && 
                               event.code !== 1008 && 
                               currentAttempts < maxReconnectAttempts;
        
        if (shouldReconnect) {
          scheduleReconnect(currentAttempts);
        } else if (event.code === 1008) {
          updateState(prev => ({
            ...prev,
            error: 'Authentication failed. Please check your login status.',
            connectionStatus: 'failed'
          }));
        }
      };

      wsRef.current = ws;
    } catch (error) {
      console.error('Failed to connect to OpenAI:', error);
      updateState(prev => ({ 
        error: 'Failed to connect to OpenAI Realtime API',
        connectionStatus: 'failed',
        reconnectAttempts: prev.reconnectAttempts + 1
      }));
      
      const currentAttempts = state.reconnectAttempts + 1;
      if (currentAttempts < maxReconnectAttempts) {
        scheduleReconnect(currentAttempts);
      }
    }
  }, [updateState, scheduleReconnect, state.connectionStatus]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    clearReconnectTimeout();
    if (wsRef.current) {
      wsRef.current.close(1000, 'User requested disconnect');
      wsRef.current = null;
    }
    updateState({ 
      isConnected: false, 
      connectionStatus: 'disconnected',
      reconnectAttempts: 0 
    });
  }, [clearReconnectTimeout, updateState]);

  // Handle messages from OpenAI
  const handleOpenAIMessage = useCallback(async (message: any) => {
    const messageType = message.type;
    console.log('OpenAI message:', messageType, message);
    
    switch (messageType) {
      case 'auth.success':
        console.log('Authentication successful');
        updateState({ 
          isConnected: true, 
          connectionStatus: 'connected',
          reconnectAttempts: 0 
        });
        break;
        
      case 'session.created':
        console.log('Session created:', message.session?.id);
        break;
        
      case 'conversation.item.input_audio_transcription.completed':
        const transcript = message.transcript || '';
        updateState({ transcript });
        console.log('Transcript:', transcript);
        break;
        
      case 'response.audio.delta':
        const audioData = message.delta;
        if (audioData) {
          console.log('Received audio delta, length:', audioData.length);
          // Queue audio chunk instead of playing immediately
          audioQueueRef.current.push(audioData);
          if (!isPlayingAudioRef.current) {
            playNextAudioChunk();
          }
        }
        break;
        
      case 'response.text.delta':
        const textDelta = message.delta || '';
        updateState(prev => ({ 
          response: prev.response + textDelta 
        }));
        break;
        
      case 'response.output_item.done':
        const item = message.item;
        if (item?.type === 'function_call') {
          console.log('Tool call completed:', item.name, '- handled by server');
          if (item.error) {
            updateState({ error: `Tool execution failed: ${item.error}` });
          }
        }
        break;
        
      case 'response.function_call_arguments.done':
        // Function call is being executed by server
        console.log('Function call sent to server for execution');
        break;
        
      case 'error':
        console.error('OpenAI error:', message.error);
        const errorMsg = message.error?.message || message.error || 'Unknown error';
        updateState({ error: `Error: ${errorMsg}` });
        
        // If auth error, disconnect and clear token
        if (errorMsg.toLowerCase().includes('auth') || errorMsg.toLowerCase().includes('unauthorized')) {
          disconnect();
          updateState({ 
            error: 'Authentication failed. Please log in again.',
            connectionStatus: 'failed'
          });
        }
        break;
        
      case 'auth.error':
        console.error('Auth error:', message.error);
        disconnect();
        updateState({ 
          error: 'Authentication failed. Please log in again.',
          connectionStatus: 'failed'
        });
        break;
        
      case 'tool.error':
        console.error('Tool error:', message.error);
        updateState({ error: `Tool error: ${message.error}` });
        break;
    }
  }, [updateState]);

  // Play next audio chunk from queue
  const playNextAudioChunk = useCallback(() => {
    if (audioQueueRef.current.length === 0) {
      isPlayingAudioRef.current = false;
      updateState({ isPlaying: false });
      return;
    }
    
    const audioData = audioQueueRef.current.shift()!;
    isPlayingAudioRef.current = true;
    updateState({ isPlaying: true });
    
    try {
      if (!audioContextRef.current) return;
      
      const audioBytes = Uint8Array.from(atob(audioData), c => c.charCodeAt(0));
      const audioBuffer = audioContextRef.current.createBuffer(1, audioBytes.length / 2, 24000);
      const channelData = audioBuffer.getChannelData(0);
      
      // Convert PCM16 to float32
      for (let i = 0; i < channelData.length; i++) {
        const sample = (audioBytes[i * 2] | (audioBytes[i * 2 + 1] << 8));
        channelData[i] = sample < 32768 ? sample / 32768 : (sample - 65536) / 32768;
      }
      
      const source = audioContextRef.current.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContextRef.current.destination);
      
      source.start();
      
      source.onended = () => {
        // Play next chunk when this one ends
        playNextAudioChunk();
      };
      
    } catch (error) {
      console.error('Audio playback error:', error);
      isPlayingAudioRef.current = false;
      updateState({ 
        isPlaying: false,
        error: 'Failed to play audio response'
      });
      // Clear the queue to prevent further errors
      audioQueueRef.current = [];
    }
  }, [updateState]);

  // Start recording audio (based on WorkAdventure implementation)
  const startRecording = useCallback(async () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      updateState({ error: 'Not connected to OpenAI' });
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: { 
          echoCancellation: false,
          noiseSuppression: false,
          sampleRate: 24000
        } 
      });
      mediaStreamRef.current = stream;
      updateState({ isRecording: true, error: null, transcript: '', response: '' });
      
      console.log('Recording started...');
      
      // Create AudioContext at 24kHz (OpenAI requirement)
      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContext({ sampleRate: 24000 });
      }
      
      const audioContext = audioContextRef.current;
      
      // Resume audio context if suspended
      if (audioContext.state === 'suspended') {
        await audioContext.resume();
        console.log('AudioContext resumed');
      }
      
      console.log('AudioContext state:', audioContext.state);
      const source = audioContext.createMediaStreamSource(stream);
      const processor = audioContext.createScriptProcessor(1024, 1, 1);
      
      let processCount = 0;
      processor.onaudioprocess = (event) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
        
        processCount++;
        const inputBuffer = event.inputBuffer;
        const inputData = inputBuffer.getChannelData(0);
        
        // Convert to PCM16 using OpenAI's recommended method
        const pcm16Data = floatTo16BitPCM(inputData);
        
        // Convert to base64
        const uint8Array = new Uint8Array(pcm16Data.buffer);
        let binaryString = '';
        for (let i = 0; i < uint8Array.length; i++) {
          binaryString += String.fromCharCode(uint8Array[i]);
        }
        const base64Audio = btoa(binaryString);
        
        // Send to OpenAI immediately (real-time streaming)
        wsRef.current.send(JSON.stringify({
          type: 'input_audio_buffer.append',
          audio: base64Audio
        }));
        
        if (processCount % 100 === 0) {
          console.log(`Sent ${processCount} audio chunks`);
        }
      };
      
      source.connect(processor);
      // Connect to a muted destination to keep processor alive
      const gainNode = audioContext.createGain();
      gainNode.gain.value = 0;
      processor.connect(gainNode);
      gainNode.connect(audioContext.destination);
      
      // Store references for cleanup
      audioProcessorRef.current = processor;
      
    } catch (error) {
      console.error('Failed to start recording:', error);
      updateState({ error: 'Failed to access microphone' });
    }
  }, [updateState, floatTo16BitPCM]);

  // Stop recording audio
  const stopRecording = useCallback(() => {
    updateState({ isRecording: false });
    console.log('Recording stopped...');
    
    // Disconnect audio processor
    if (audioProcessorRef.current) {
      try {
        audioProcessorRef.current.disconnect();
      } catch (e) {
        console.log('Error disconnecting processor:', e);
      }
      audioProcessorRef.current = null;
    }
    
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop());
      mediaStreamRef.current = null;
    }
    
    // With server VAD, no need to manually commit - the server handles it
    console.log('Recording stopped, server VAD will handle response generation');
  }, [updateState]);

  // Toggle recording
  const toggleRecording = useCallback(() => {
    if (state.isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }, [state.isRecording, startRecording, stopRecording]);

  // Send text message
  const sendTextMessage = useCallback((text: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      updateState({ error: 'Not connected. Please connect first.' });
      return;
    }

    // Clear previous response
    updateState({ response: '', transcript: '' });

    wsRef.current.send(JSON.stringify({
      type: 'conversation.item.create',
      item: {
        type: 'message',
        role: 'user',
        content: [{
          type: 'input_text',
          text: text
        }]
      }
    }));

    // Trigger response
    wsRef.current.send(JSON.stringify({
      type: 'response.create',
      response: {
        modalities: ['text', 'audio']
      }
    }));
  }, [updateState]);

  // Initialize on mount
  useEffect(() => {
    initializeAudio();
    return () => {
      // Cleanup
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (audioProcessorRef.current) {
        try {
          audioProcessorRef.current.disconnect();
        } catch (e) {
          console.log('Error disconnecting processor:', e);
        }
      }
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach(track => track.stop());
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
      clearReconnectTimeout();
    };
  }, [initializeAudio, clearReconnectTimeout]);

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Voice Assistant</h1>
          <p className="mt-2 text-gray-600">
            Talk to your audiobook library using voice commands
          </p>
        </div>

        {/* Connection Status */}
        <Card className="mb-6 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className={`w-3 h-3 rounded-full ${
                state.connectionStatus === 'connected' ? 'bg-green-500' : 
                state.connectionStatus === 'connecting' ? 'bg-yellow-500 animate-pulse' :
                state.connectionStatus === 'failed' ? 'bg-red-500' : 'bg-gray-500'
              }`} />
              <span className={`${
                state.connectionStatus === 'connected' ? 'text-green-700' : 
                state.connectionStatus === 'connecting' ? 'text-yellow-700' :
                state.connectionStatus === 'failed' ? 'text-red-700' : 'text-gray-700'
              }`}>
                {state.connectionStatus === 'connected' ? 'Connected to OpenAI' : 
                 state.connectionStatus === 'connecting' ? 'Connecting...' :
                 state.connectionStatus === 'failed' ? `Failed (${state.reconnectAttempts}/${maxReconnectAttempts} attempts)` : 
                 'Disconnected'}
              </span>
            </div>
            <div className="flex space-x-2">
              <Button 
                onClick={state.isConnected ? disconnect : connectToOpenAI}
                disabled={state.connectionStatus === 'connecting'}
                variant={state.isConnected ? 'secondary' : 'primary'}
              >
                {state.isConnected ? 'Disconnect' : 
                 state.connectionStatus === 'connecting' ? 'Connecting...' : 'Connect'}
              </Button>
              <Button 
                onClick={testToken}
                variant="outline"
                size="sm"
              >
                Test Token
              </Button>
            </div>
          </div>
          {state.error && (
            <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-600 flex items-center justify-between">
              <span>{state.error}</span>
              <button 
                onClick={() => updateState({ error: null })}
                className="ml-2 text-red-500 hover:text-red-700"
              >
                ✕
              </button>
            </div>
          )}
        </Card>

        {/* Voice Controls */}
        <Card className="mb-6 p-6">
          <h2 className="text-xl font-semibold mb-4">Voice Controls</h2>
          <div className="flex items-center space-x-4 mb-4">
            <Button
              size="lg"
              onClick={toggleRecording}
              className={`${state.isRecording ? 'bg-red-500 hover:bg-red-600' : ''}`}
              disabled={!state.isConnected}
            >
              {state.isRecording ? (
                <StopIcon className="h-6 w-6 mr-2" />
              ) : (
                <MicrophoneIcon className="h-6 w-6 mr-2" />
              )}
              {state.isRecording ? 'Stop Recording' : 'Start Recording'}
            </Button>
            
            <div className="flex items-center space-x-2">
              {state.isPlaying && <SpeakerWaveIcon className="h-5 w-5 text-blue-500" />}
              {state.isPlaying && <span className="text-sm text-blue-600">Playing audio...</span>}
            </div>
          </div>

          {/* Text Input for Testing */}
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Test with Text Message
              </label>
              <div className="flex space-x-2">
                <Input
                  value={testMessage}
                  onChange={(e) => setTestMessage(e.target.value)}
                  placeholder="Type a message..."
                  className="flex-1"
                />
                <Button 
                  onClick={() => sendTextMessage(testMessage)}
                  disabled={!state.isConnected}
                >
                  Send
                </Button>
              </div>
            </div>

            {/* Job ID for specific searches */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Job ID (for specific book searches)
              </label>
              <Input
                value={jobId}
                onChange={(e) => setJobId(e.target.value)}
                placeholder="Enter job ID for book-specific queries"
              />
            </div>
          </div>
        </Card>

        {/* Conversation Display */}
        <div className="grid md:grid-cols-2 gap-6">
          {/* User Input */}
          <Card className="p-4">
            <h3 className="font-semibold text-gray-900 mb-2">You said:</h3>
            <div className="bg-gray-50 rounded p-3 min-h-[100px]">
              {state.transcript || 'Your speech will appear here...'}
            </div>
          </Card>

          {/* Assistant Response */}
          <Card className="p-4">
            <h3 className="font-semibold text-gray-900 mb-2">Assistant response:</h3>
            <div className="bg-blue-50 rounded p-3 min-h-[100px]">
              {state.response || 'Assistant response will appear here...'}
            </div>
          </Card>
        </div>

        {/* Quick Actions */}
        <Card className="mt-6 p-4">
          <h3 className="font-semibold text-gray-900 mb-3">Quick Actions</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <Button 
              variant="outline" 
              onClick={() => sendTextMessage("What's in my library about luck?")}
              disabled={!state.isConnected}
              className="text-left"
            >
              Search for "luck"
            </Button>
            <Button 
              variant="outline" 
              onClick={() => sendTextMessage("Tell me about my audiobook collection")}
              disabled={!state.isConnected}
              className="text-left"
            >
              Describe my library
            </Button>
            <Button 
              variant="outline" 
              onClick={() => jobId ? sendTextMessage(`What are the main themes in job ${jobId}?`) : alert('Please enter a Job ID first')}
              disabled={!state.isConnected || !jobId}
              className="text-left"
            >
              Ask about specific book
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default VoiceAssistant;