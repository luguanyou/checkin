import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

const DEFAULT_RATE = 0.9;
const MIN_RATE = 0.5;
const MAX_RATE = 2;
/** 同一次 speak 最多尝试次数（引擎偶发丢 utterance/瞬时报错时重试一次） */
const MAX_ATTEMPTS = 2;

const NO_VOICE_MESSAGE =
  '未检测到可用的中文语音引擎：请在电脑端使用 Chrome/Edge 并保持联网（浏览器需要下载中文语音），或检查系统是否已安装中文语音后再试。';

function readRate() {
  if (typeof window === 'undefined') return DEFAULT_RATE;
  const value = Number(window.localStorage.getItem('attendance.speech.rate'));
  return Number.isFinite(value) ? Math.min(MAX_RATE, Math.max(MIN_RATE, value)) : DEFAULT_RATE;
}

function readVoiceName() {
  if (typeof window === 'undefined') return '';
  return window.localStorage.getItem('attendance.speech.voice') || '';
}

export function useSpeech() {
  const [muted, setMuted] = useState(false);
  const [rate, setRateState] = useState(readRate);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [voiceName, setVoiceNameState] = useState(readVoiceName);
  /** 最近一次播报失败的原因（无声音时给教师明确指引），成功播报后自动清空 */
  const [error, setError] = useState('');
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const requestId = useRef(0);
  const supported = typeof window !== 'undefined' && 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;

  const clearTimers = useCallback(() => {
    timers.current.forEach((timer) => clearTimeout(timer));
    timers.current = [];
  }, []);

  useEffect(() => {
    if (!supported) return;
    const synthesis = window.speechSynthesis;
    const refresh = () => setVoices(typeof synthesis.getVoices === 'function' ? synthesis.getVoices() : []);
    refresh();
    synthesis.addEventListener?.('voiceschanged', refresh);
    return () => {
      synthesis.removeEventListener?.('voiceschanged', refresh);
      clearTimers();
    };
  }, [supported, clearTimers]);

  useEffect(() => () => clearTimers(), [clearTimers]);

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
    clearTimers();
    setError('');
    const hasVoices = voices.length > 0;

    const fail = (message: string) => {
      if (currentRequest === requestId.current) {
        clearTimers();
        setError(message);
      }
    };
    const retry = (reason: string, attempt: number) => {
      if (currentRequest !== requestId.current) return;
      clearTimers(); // 作废上一轮 attempt 遗留的看门狗
      // 先停掉当前队列，稍作间隔再重试：
      // Chromium 在 cancel() 同一执行周期内调 speak() 会静默丢弃新 utterance。
      const timer = setTimeout(() => {
        if (currentRequest !== requestId.current) return;
        if (synthesis.speaking || synthesis.pending) synthesis.cancel();
        const next = setTimeout(() => fire(attempt + 1), 80);
        timers.current.push(next);
      }, 200);
      timers.current.push(timer);
    };
    const fire = (attempt: number) => {
      if (currentRequest !== requestId.current) return;
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = voice?.lang || 'zh-CN';
      utterance.rate = rate;
      utterance.volume = 1;
      if (voice) utterance.voice = voice;
      let started = false;
      const settle = () => {
        if (currentRequest === requestId.current) clearTimers();
      };
      utterance.onstart = () => {
        started = true;
        setError('');
        settle();
      };
      utterance.onend = settle;
      utterance.onerror = (event) => {
        // interrupted/canceled 由“新请求替换旧请求”或静音引起，属正常路径
        if (currentRequest !== requestId.current) return;
        if (event.error === 'interrupted' || event.error === 'canceled') {
          settle();
          return;
        }
        if (event.error === 'not-allowed') {
          fail('浏览器拦截了自动语音播报：请先点击页面任意位置（触发一次用户操作）再试。');
          return;
        }
        if (attempt < MAX_ATTEMPTS) retry(`语音引擎报错（${event.error}）`, attempt);
        else fail(hasVoices
          ? `语音播报失败（${event.error}）。请点击“重新播报”再试；仍无声请改用电脑版 Edge/Chrome 并联网。`
          : NO_VOICE_MESSAGE);
      };
      synthesis.resume?.();
      synthesis.speak(utterance);
      // 兜底看门狗：部分环境会静默吞掉 utterance，不触发任何事件
      const watchdog = setTimeout(() => {
        if (currentRequest !== requestId.current || started) return;
        if (attempt < MAX_ATTEMPTS) retry('浏览器没有开始播报', attempt);
        else fail(hasVoices
          ? '语音播报没有声音。请点击“重新播报”再试；仍无声请改用电脑版 Edge/Chrome 并联网。'
          : NO_VOICE_MESSAGE);
      }, 900);
      timers.current.push(watchdog);
    };

    if (synthesis.speaking || synthesis.pending) synthesis.cancel();
    // 与 cancel() 错开一个执行周期再 speak，避免 Chromium 静默丢弃
    const start = setTimeout(() => fire(1), 60);
    timers.current.push(start);
    return true;
  }, [clearTimers, muted, rate, supported, voice, voices.length]);

  const toggleMuted = useCallback(() => setMuted((value) => !value), []);

  return { muted, supported, speak, toggleMuted, rate, setRate, voices, voiceName, setVoice, error };
}
