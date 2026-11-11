const storageKey = 'kaoqing:remember-password';
export interface RememberedLogin { username: string; password: string }

// Opt-in device storage. Never send these values anywhere except the login API.
export function readRememberedLogin(): RememberedLogin | null {
  try {
    const raw = localStorage.getItem(storageKey);
    if (!raw) return null;
    const saved: unknown = JSON.parse(raw);
    if (typeof saved !== 'object' || saved === null || !('username' in saved) || !('password' in saved)) return null;
    if (typeof saved.username !== 'string' || !saved.username.trim() || typeof saved.password !== 'string' || !saved.password) return null;
    return { username: saved.username, password: saved.password };
  } catch { return null; }
}

export function saveRememberedLogin(username: string, password: string): boolean {
  try {
    localStorage.setItem(storageKey, JSON.stringify({ username, password }));
    return true;
  } catch { return false; }
}

export function clearRememberedLogin(): boolean {
  try { localStorage.removeItem(storageKey); return true; } catch { return false; }
}
