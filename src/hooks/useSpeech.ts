import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

const DEFAULT_RATE = 0.9;
const MIN_RATE = 0.5;
const MAX_RATE = 2;

function readRate() {
  if (typeof window === 'undefined') return DEFAULT_RATE;
  const value = Number(window.localStorage.getItem('attendance.speech.rate'));
  return Number.isFinite(value) ? Math.min(MAX_RATE, Math.max(MIN_RATE, value)) : DEFAULT_RATE;
}

export function useSpeech() {
  const [muted, setMuted] = useState(false);
  const [rate, setRateState] = useState(readRate);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [voiceName, setVoiceNameState] = useState(() => typeof window === 'undefined' ? '' : window.localStorage.getItem('attendance.speech.voice') || '');
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const requestId = useRef(0);
  const supported = typeof window !== 'undefined' && 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;

  useEffect(() => {
    if (!supported) return;
    const synthesis = window.speechSynthesis;
    const refresh = () => setVoices(typeof synthesis.getVoices === 'function' ? synthesis.getVoices() : []);
    refresh();
    synthesis.addEventListener?.('voiceschanged', refresh);
    return () => synthesis.removeEventListener?.('voiceschanged', refresh);
  }, [supported]);

  useEffect(() => () => {
    if (retryTimer.current) clearTimeout(retryTimer.current);
  }, []);

  const voice = useMemo(() => voices.find((item) => item.voiceURI === voiceName || item.name === voiceName) ?? null, [voiceName, voices]);
  const setRate = useCallback((value: number) => {
    const next = Math.min(MAX_RATE, Math.max(MIN_RATE, value));
    setRateState(next);
    window.localStorage?.setItem('attendance.speech.rate', String(next));
  }, []);
  const setVoice = useCallback((value: string) => {
    setVoiceNameState(value);
    window.localStorage?.setItem('attendance.speech.voice', value);
  }, []);
  const speak = useCallback((text: string) => {
    if (muted || !supported || !text.trim()) return false;
    const synthesis = window.speechSynthesis;
    const currentRequest = ++requestId.current;
    if (retryTimer.current) {
      clearTimeout(retryTimer.current);
      retryTimer.current = null;
    }
    synthesis.cancel();
    let retried = false;
    const start = () => {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = voice?.lang || 'zh-CN';
      utterance.rate = rate;
      utterance.volume = 1;
      if (voice) utterance.voice = voice;
      let started = false;
      utterance.onstart = () => {
        started = true;
        if (currentRequest === requestId.current && retryTimer.current) {
          clearTimeout(retryTimer.current);
          retryTimer.current = null;
        }
      };
      synthesis.resume?.();
      synthesis.speak(utterance);
      // Chromium can silently drop an utterance immediately after cancel().
      // Retry once when no start event arrives, while keeping the latest call authoritative.
      if (!retried) {
        retryTimer.current = setTimeout(() => {
          retryTimer.current = null;
          if (currentRequest !== requestId.current || started) return;
          retried = true;
          synthesis.cancel();
          start();
        }, 250);
      }
    };
    start();
    return true;
  }, [muted, rate, supported, voice]);
  const toggleMuted = useCallback(() => setMuted((value) => !value), []);

  return { muted, supported, speak, toggleMuted, rate, setRate, voices, voiceName, setVoice };
}
