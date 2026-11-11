export function generateTemporaryPassword() {
  const range = 100_000_000;
  const limit = Math.floor(2 ** 32 / range) * range;
  const random = new Uint32Array(1);
  // Reject the incomplete range so every eight-digit value is equally likely.
  do {
    crypto.getRandomValues(random);
  } while (random[0] >= limit);
  return String(random[0] % range).padStart(8, '0');
}
