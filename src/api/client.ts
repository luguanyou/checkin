import type { ErrorResponse, LoginResponse } from './types';

type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly details: Record<string, unknown> = {},
    public readonly requestId = '',
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export interface ApiClientOptions {
  baseUrl?: string;
  fetcher?: Fetcher;
  onSession?: (session: LoginResponse | null) => void;
}

function isJson(response: Response) {
  return response.headers.get('Content-Type')?.includes('application/json') ?? false;
}

export function parseDownloadFilename(disposition: string | null) {
  if (!disposition) return 'attendance-export';
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const plain = disposition.match(/filename="?([^";]+)"?/i)?.[1];
  let candidate = encoded ? decodeURIComponent(encoded) : plain;
  if (!candidate) return 'attendance-export';
  candidate = candidate.replace(/\\/g, '/').split('/').pop() || 'attendance-export';
  return candidate.replace(/[\x00-\x1f<>:"|?*]/g, '_');
}

export class ApiClient {
  private accessToken: string | null = null;
  private refreshPromise: Promise<LoginResponse> | null = null;
  private readonly baseUrl: string;
  private readonly fetcher: Fetcher;
  private readonly onSession?: (session: LoginResponse | null) => void;

  constructor(options: ApiClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? '/api/v1').replace(/\/$/, '');
    this.fetcher = options.fetcher ?? globalThis.fetch.bind(globalThis);
    this.onSession = options.onSession;
  }

  setAccessToken(token: string | null) {
    this.accessToken = token;
  }

  getAccessToken() {
    return this.accessToken;
  }

  private async send(path: string, init: RequestInit = {}) {
    const headers = new Headers(init.headers);
    if (this.accessToken && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${this.accessToken}`);
    }
    if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
    return this.fetcher(`${this.baseUrl}${path}`, {
      ...init,
      headers,
      credentials: 'include',
    });
  }

  private async toError(response: Response) {
    if (isJson(response)) {
      const body = await response.json() as Partial<ErrorResponse>;
      return new ApiError(
        response.status,
        body.code ?? 'REQUEST_FAILED',
        body.message ?? '请求失败，请稍后重试',
        body.details ?? {},
        body.request_id ?? response.headers.get('X-Request-ID') ?? '',
      );
    }
    return new ApiError(response.status, 'REQUEST_FAILED', '请求失败，请稍后重试');
  }

  private async refresh() {
    if (!this.refreshPromise) {
      this.refreshPromise = this.send('/auth/refresh', { method: 'POST' })
        .then(async (response) => {
          if (!response.ok) throw await this.toError(response);
          const session = await response.json() as LoginResponse;
          this.setAccessToken(session.access_token);
          this.onSession?.(session);
          return session;
        })
        .catch((error: unknown) => {
          this.setAccessToken(null);
          this.onSession?.(null);
          throw error;
        })
        .finally(() => {
          this.refreshPromise = null;
        });
    }
    return this.refreshPromise;
  }

  async request<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
    const response = await this.send(path, init);
    if (response.status === 401 && retry && path !== '/auth/login' && path !== '/auth/refresh') {
      await this.refresh();
      return this.request<T>(path, init, false);
    }
    if (!response.ok) throw await this.toError(response);
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }

  async download(path: string) {
    let response = await this.send(path);
    if (response.status === 401) {
      await this.refresh();
      response = await this.send(path);
    }
    if (!response.ok) throw await this.toError(response);
    return {
      blob: await response.blob(),
      filename: parseDownloadFilename(response.headers.get('Content-Disposition')),
    };
  }
}
