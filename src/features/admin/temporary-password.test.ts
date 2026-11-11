import { afterEach, describe, expect, it, vi } from 'vitest';
import { generateTemporaryPassword } from './temporary-password';

describe('generateTemporaryPassword', () => {
  afterEach(() => vi.restoreAllMocks());

  it('generates eight digits and preserves leading zeros', () => {
    vi.spyOn(crypto, 'getRandomValues').mockImplementation((values) => {
      (values as Uint32Array).fill(12345);
      return values;
    });

    const password = generateTemporaryPassword();

    expect(password).toBe('00012345');
  });

  it('rejects values outside the uniform range and draws fresh randomness each time', () => {
    const random = vi.spyOn(crypto, 'getRandomValues').mockImplementation((values) => {
      (values as Uint32Array)[0] = random.mock.calls.length === 1 ? 4_294_967_295 : 87654321;
      return values;
    });
    expect(generateTemporaryPassword()).toBe('87654321');
    expect(random).toHaveBeenCalledTimes(2);
    generateTemporaryPassword();
    expect(random).toHaveBeenCalledTimes(3);
  });
});
