import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  generateTemporaryPassword,
  TEMPORARY_PASSWORD_ALPHABET,
} from './temporary-password';

describe('generateTemporaryPassword', () => {
  afterEach(() => vi.restoreAllMocks());

  it('generates a 16-character password from the approved alphabet', () => {
    vi.spyOn(crypto, 'getRandomValues').mockImplementation((values) => {
      (values as Uint8Array).fill(0);
      return values;
    });

    const password = generateTemporaryPassword();

    expect(password).toBe(TEMPORARY_PASSWORD_ALPHABET[0].repeat(16));
    expect(password).toHaveLength(16);
  });

  it('requests one cryptographic random byte per character', () => {
    const random = vi.spyOn(crypto, 'getRandomValues');

    generateTemporaryPassword();

    expect(random).toHaveBeenCalledOnce();
    expect((random.mock.calls[0]?.[0] as Uint8Array).length).toBe(16);
  });
});
