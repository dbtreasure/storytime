export interface EnvironmentInfo {
  environment: 'dev' | 'docker' | 'production';
  features: {
    signup_enabled: boolean;
    debug_mode: boolean;
    demo_mode: boolean;
  };
}

// Cache the environment info
let cachedEnvironment: EnvironmentInfo | null = null;

export async function getEnvironment(): Promise<EnvironmentInfo> {
  if (cachedEnvironment) {
    return cachedEnvironment;
  }

  try {
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
    const response = await fetch(`${apiBaseUrl}/api/v1/environment`);
    if (!response.ok) {
      throw new Error('Failed to fetch environment info');
    }
    cachedEnvironment = await response.json();
    return cachedEnvironment!;
  } catch (error) {
    console.error('Failed to fetch environment info:', error);
    // Default fallback based on URL
    const isProd = window.location.hostname === 'plinytheai.com';
    cachedEnvironment = {
      environment: isProd ? 'production' : 'dev',
      features: {
        signup_enabled: !isProd,
        debug_mode: !isProd,
        demo_mode: false,
      },
    };
    return cachedEnvironment;
  }
}

export function clearEnvironmentCache(): void {
  cachedEnvironment = null;
}