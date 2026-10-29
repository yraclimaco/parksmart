import { describe, expect, it } from 'vitest';
import { DEFAULT_API_BASE_URL, resolveApiBaseUrl } from './config.ts';

describe('resolveApiBaseUrl', () => {
  it('uses the local FastAPI backend when nothing is configured', () => {
    expect(resolveApiBaseUrl(undefined)).toBe(DEFAULT_API_BASE_URL);
    expect(resolveApiBaseUrl('   ')).toBe(DEFAULT_API_BASE_URL);
  });

  it('uses the configured URL without trailing slashes', () => {
    expect(resolveApiBaseUrl(' http://localhost:9000/ ')).toBe('http://localhost:9000');
    expect(resolveApiBaseUrl('https://api.example.test//')).toBe('https://api.example.test');
  });
});
