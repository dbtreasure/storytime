import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useAppDispatch } from '../hooks/redux';
import { createJob } from '../store/slices/jobsSlice';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Card } from '../components/ui/Card';
import { Alert } from '../components/ui/Alert';
import { Select } from '../components/ui/Select';
import {
  CloudArrowUpIcon,
  DocumentTextIcon,
  XMarkIcon,
  LinkIcon,
} from '@heroicons/react/24/outline';

const uploadSchema = z.object({
  title: z.string().min(1, 'Title is required'),
  ttsProvider: z.enum(['openai', 'elevenlabs'], {
    required_error: 'Please select a TTS provider',
  }),
  textContent: z.string().optional(),
  url: z.string().url().optional(),
}).refine(
  (data) => {
    const hasText = data.textContent && data.textContent.length >= 100;
    const hasUrl = data.url && data.url.length > 0;
    return hasText || hasUrl;
  },
  {
    message: "Either provide text content (min 100 characters) or a valid URL",
    path: ["textContent"],
  }
);

type UploadFormData = z.infer<typeof uploadSchema>;

const Upload: React.FC = () => {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [inputMethod, setInputMethod] = useState<'text' | 'file' | 'url'>('text');

  const {
    register,
    handleSubmit,
    control,
    setValue,
    watch,
    formState: { errors },
  } = useForm<UploadFormData>({
    resolver: zodResolver(uploadSchema),
    defaultValues: {
      ttsProvider: 'openai',
    },
  });

  const textContent = watch('textContent');
  const url = watch('url');

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleFiles = useCallback(async (files: File[]) => {
    const textFile = files.find(file =>
      file.type === 'text/plain' || file.name.endsWith('.txt')
    );

    if (!textFile) {
      setError('Please upload a .txt file');
      return;
    }

    try {
      const text = await textFile.text();
      setValue('textContent', text);
      setUploadedFile(textFile);
      setError(null);

      // Auto-fill title if not set
      if (!watch('title')) {
        const title = textFile.name.replace(/\.[^/.]+$/, '');
        setValue('title', title);
      }
    } catch {
      setError('Failed to read file content');
    }

  }, [setValue, watch]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const files = Array.from(e.dataTransfer.files);
    handleFiles(files);
  }, [handleFiles]);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    handleFiles(files);
  };

  const removeFile = () => {
    setUploadedFile(null);
    setValue('textContent', '');
  };

  const onSubmit = async (data: UploadFormData) => {
    setIsLoading(true);
    setError(null);

    try {
      // Prepare job payload based on input method
      const jobPayload: {
        title: string;
        voice_config: { provider: string; voice_id: string };
        content?: string;
        url?: string;
      } = {
        title: data.title,
        voice_config: {
          provider: data.ttsProvider,
          voice_id: data.ttsProvider === 'openai' ? 'alloy' : 'adam', // Default voices
        }
      };

      // Add content based on input method
      if (inputMethod === 'url' && data.url) {
        jobPayload.url = data.url;
      } else if (data.textContent) {
        jobPayload.content = data.textContent;
      }

      const result = await dispatch(createJob(jobPayload)).unwrap();

      navigate(`/jobs/${result.id}`);
    } catch (err: unknown) {
      setError((err as Error).message || 'Failed to create job. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Upload Story</h1>
        <p className="text-gray-600 mt-2">
          Transform your text into an immersive audiobook with AI-generated voices.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {error && (
          <Alert variant="error" className="mb-4">
            {error}
          </Alert>
        )}

        {/* Job Configuration */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Job Configuration
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label htmlFor="title" className="block text-sm font-medium text-gray-700 mb-2">
                Title
              </label>
              <Input
                id="title"
                {...register('title')}
                error={errors.title?.message}
                placeholder="Enter a title for your audiobook"
                disabled={isLoading}
              />
            </div>

            <div>
              <label htmlFor="ttsProvider" className="block text-sm font-medium text-gray-700 mb-2">
                Voice Provider
              </label>
              <Controller
                name="ttsProvider"
                control={control}
                render={({ field }) => (
                  <Select
                    {...field}
                    error={errors.ttsProvider?.message}
                    disabled={isLoading}
                    options={[
                      { value: 'openai', label: 'OpenAI' },
                      { value: 'elevenlabs', label: 'ElevenLabs' }
                    ]}
                  />
                )}
              />
            </div>
          </div>
        </Card>

        {/* Content Input */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Content Source
          </h2>

          {/* Input Method Tabs */}
          <div className="flex space-x-1 bg-gray-100 p-1 rounded-lg mb-6">
            <button
              type="button"
              onClick={() => {
                setInputMethod('text');
                setValue('url', '');
              }}
              className={`flex-1 flex items-center justify-center px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                inputMethod === 'text'
                  ? 'bg-white text-blue-600 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
              disabled={isLoading}
            >
              <DocumentTextIcon className="h-4 w-4 mr-2" />
              Text Input
            </button>
            <button
              type="button"
              onClick={() => {
                setInputMethod('file');
                setValue('url', '');
              }}
              className={`flex-1 flex items-center justify-center px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                inputMethod === 'file'
                  ? 'bg-white text-blue-600 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
              disabled={isLoading}
            >
              <CloudArrowUpIcon className="h-4 w-4 mr-2" />
              File Upload
            </button>
            <button
              type="button"
              onClick={() => {
                setInputMethod('url');
                setValue('textContent', '');
                removeFile();
              }}
              className={`flex-1 flex items-center justify-center px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                inputMethod === 'url'
                  ? 'bg-white text-blue-600 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
              disabled={isLoading}
            >
              <LinkIcon className="h-4 w-4 mr-2" />
              URL
            </button>
          </div>

          {/* URL Input */}
          {inputMethod === 'url' && (
            <div>
              <label htmlFor="url" className="block text-sm font-medium text-gray-700 mb-2">
                Website URL
              </label>
              <Controller
                name="url"
                control={control}
                render={({ field }) => (
                  <Input
                    {...field}
                    id="url"
                    type="url"
                    placeholder="https://example.com/article"
                    error={errors.url?.message}
                    disabled={isLoading}
                  />
                )}
              />
              <p className="mt-2 text-sm text-gray-500">
                Enter a URL to automatically extract and convert web content to audio.
                Works with articles, blog posts, and other text-based web pages.
              </p>
            </div>
          )}

          {/* File Upload */}
          {inputMethod === 'file' && (
            <div>
              {!uploadedFile ? (
                <div
                  className={`relative border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                    dragActive
                      ? 'border-blue-400 bg-blue-50'
                      : 'border-gray-300 hover:border-gray-400'
                  }`}
                  onDragEnter={handleDrag}
                  onDragLeave={handleDrag}
                  onDragOver={handleDrag}
                  onDrop={handleDrop}
                >
                  <CloudArrowUpIcon className="mx-auto h-12 w-12 text-gray-400" />
                  <div className="mt-4">
                    <label htmlFor="file-upload" className="cursor-pointer">
                      <span className="mt-2 block text-sm font-medium text-gray-900">
                        Drop your .txt file here, or{' '}
                        <span className="text-blue-600 hover:text-blue-500">
                          browse
                        </span>
                      </span>
                      <input
                        id="file-upload"
                        name="file-upload"
                        type="file"
                        accept=".txt,text/plain"
                        className="sr-only"
                        onChange={handleFileInput}
                        disabled={isLoading}
                      />
                    </label>
                    <p className="mt-1 text-xs text-gray-500">
                      TXT files up to 10MB
                    </p>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-between p-4 bg-blue-50 rounded-lg">
                  <div className="flex items-center space-x-3">
                    <DocumentTextIcon className="h-8 w-8 text-blue-600" />
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {uploadedFile.name}
                      </p>
                      <p className="text-xs text-gray-500">
                        {(uploadedFile.size / 1024).toFixed(1)} KB
                      </p>
                    </div>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={removeFile}
                    disabled={isLoading}
                  >
                    <XMarkIcon className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </div>
          )}

          {/* Text Input */}
          {inputMethod === 'text' && (
            <div>
              <label htmlFor="textContent" className="block text-sm font-medium text-gray-700 mb-2">
                Text Content
              </label>
              <Controller
                name="textContent"
                control={control}
                render={({ field }) => (
                  <textarea
                    {...field}
                    id="textContent"
                    rows={12}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    placeholder="Paste your story text here..."
                    disabled={isLoading}
                  />
                )}
              />
              {errors.textContent && (
                <p className="mt-1 text-sm text-red-600">
                  {errors.textContent.message}
                </p>
              )}
              <p className="mt-1 text-xs text-gray-500">
                {textContent?.length || 0} characters (minimum 100)
              </p>
            </div>
          )}
        </Card>

        {/* Submit */}
        <div className="flex justify-end space-x-4">
          <Button
            type="button"
            variant="outline"
            onClick={() => navigate('/dashboard')}
            disabled={isLoading}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={isLoading || (!textContent && !url)}
            loading={isLoading}
          >
            Create Audiobook
          </Button>
        </div>
      </form>
    </div>
  );
};

export default Upload;
