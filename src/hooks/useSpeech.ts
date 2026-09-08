import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

const DEFAULT_RATE = 0.9;
const MIN_RATE = 0.5;
const MAX_RATE = 2;
/** 同一次系统语音最多尝试次数（引擎偶发丢 utterance/瞬时报错时重试一次） */
const MAX_ATTEMPTS = 2;
/** Chrome 等浏览器语音列表可能延迟加载，先等一个窗口再决定是否走服务器音频兜底 */
const VOICES_GRACE_MS = 400;

const NO_VOICE_MESSAGE =
  '未检测到可用的中文语音引擎：请在电脑端使用 Chrome/Edge 并保持联网（浏览器需要下载中文语音），或检查系统是否已安装中文语音后再试。';

export interface UseSpeechOptions {
  /**
   * 服务器 TTS 音频兜底：浏览器系统语音不可用/无声时（如国内 Chrome 拉不到
   * Google 语音包），改播服务器合成的 MP3，保证点名一定有声音。
   */
  audioFallback?: (text: string, rate: number) => Promise<Blob>;
}

function readRate() {
  if (typeof window === 'undefined') return DEFAULT_RATE;
  const value = Number(window.localStorage.getItem('attendance.speech.rate'));
  return Number.isFinite(value) ? Math.min(MAX_RATE, Math.max(MIN_RATE, value)) : DEFAULT_RATE;
}

function readVoiceName() {
  if (typeof window === 'undefined') return '';
  return window.localStorage.getItem('attendance.speech.voice') || '';
}

export function useSpeech(options: UseSpeechOptions = {}) {
  const { audioFallback } = options;
  const [muted, setMuted] = useState(false);
  const [rate, setRateState] = useState(readRate);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [voiceName, setVoiceNameState] = useState(readVoiceName);
  /** 最近一次播报失败的原因（无声音时给教师明确指引），成功播报后自动清空 */
  const [error, setError] = useState('');
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const requestId = useRef(0);
  const voicesRef = useRef<SpeechSynthesisVoice[]>([]);
  /** 本会话内是否已确认系统语音不可用 → 后续直接走服务器音频，避免反复试探 */
  const useAudioRef = useRef(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef('');
  const audioFallbackRef = useRef(audioFallback);
  audioFallbackRef.current = audioFallback;

  const supported = typeof window !== 'undefined' && 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;

  const clearTimers = useCallback(() => {
    timers.current.forEach((timer) => clearTimeout(timer));
    timers.current = [];
  }, []);

  useEffect(() => {
    if (!supported) return;
    const synthesis = window.speechSynthesis;
    const refresh = () => {
      const list = typeof synthesis.getVoices === 'function' ? synthesis.getVoices() : [];
      voicesRef.current = list;
      setVoices(list);
    };
    refresh();
    synthesis.addEventListener?.('voiceschanged', refresh);
    return () => {
      synthesis.removeEventListener?.('voiceschanged', refresh);
      clearTimers();
    };
  }, [supported, clearTimers]);

  useEffect(() => () => clearTimers(), [clearTimers]);

  /** 停止当前服务器音频（换人/静音/卸载时调用） */
  const stopAudio = useCallback(() => {
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.removeAttribute('src');
      audio.load?.();
    }
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = '';
    }
  }, []);

  useEffect(() => () => stopAudio(), [stopAudio]);

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

  /**
   * 服务器音频兜底：fetch MP3 → <audio> 播放。
   * 只要浏览器能放网页音频就有声音（不受系统 TTS / Google 语音包影响）。
   */
  const playAudioFallback = useCallback(async (text: string, currentRequest: number) => {
    const fallback = audioFallbackRef.current;
    if (!fallback) return;
    let blob: Blob;
    try {
      blob = await fallback(text, rate);
    } catch {
      if (currentRequest === requestId.current) {
        setError('服务器语音服务暂不可用，请稍后点击“重新播报”再试。');
      }
      return;
    }
    if (currentRequest !== requestId.current) return;
    try {
      stopAudio();
      const url = URL.createObjectURL(blob);
      audioUrlRef.current = url;
      const audio = audioRef.current ?? new Audio();
      audioRef.current = audio;
      audio.src = url;
      setError('');
      await audio.play();
    } catch {
      if (currentRequest === requestId.current) {
        setError('浏览器拦截了自动播放：请再点一次“重新播报”或页面上任意按钮后重试。');
      }
    }
  }, [rate, stopAudio]);

  const speak = useCallback((text: string) => {
    if (muted || !text.trim()) return false;
    const synthesis = window.speechSynthesis;
    const currentRequest = ++requestId.current;
    clearTimers();
    stopAudio();
    setError('');
    const hasFallback = Boolean(audioFallbackRef.current);

    const startAudio = () => {
      useAudioRef.current = true;
      void playAudioFallback(text, currentRequest);
    };

    /** 播报彻底失败：有兜底时转服务器音频；无兜底时给出针对性的操作指引 */
    const fail = (reason: string) => {
      if (currentRequest !== requestId.current) return;
      clearTimers();
      if (hasFallback) {
        startAudio();
      } else if (voicesRef.current.length > 0) {
        setError(`语音播报失败：${reason}。请点击“重新播报”再试；仍无声请改用电脑版 Edge/Chrome 并联网。`);
      } else {
        setError(NO_VOICE_MESSAGE);
      }
    };

    /** 系统语音单次播报（含一次重试），全部失败后交给 fail() */
    const startSystem = (attempt: number) => {
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
        if (currentRequest !== requestId.current) return;
        if (event.error === 'interrupted' || event.error === 'canceled') {
          settle();
          return;
        }
        if (event.error === 'not-allowed') {
          if (hasFallback) startAudio();
          else setError('浏览器拦截了自动语音播报：请先点击页面任意位置（触发一次用户操作）再试。');
          return;
        }
        if (attempt < MAX_ATTEMPTS) scheduleRetry(attempt);
        else fail(`语音引擎报错（${event.error}）`);
      };
      synthesis.resume?.();
      synthesis.speak(utterance);
      // 兜底看门狗：部分环境会静默吞掉 utterance，不触发任何事件
      const watchdog = setTimeout(() => {
        if (currentRequest !== requestId.current || started) return;
        if (attempt < MAX_ATTEMPTS) scheduleRetry(attempt);
        else fail('浏览器没有开始播报');
      }, 900);
      timers.current.push(watchdog);
    };

    const scheduleRetry = (attempt: number) => {
      if (currentRequest !== requestId.current) return;
      clearTimers(); // 作废上一轮 attempt 遗留的看门狗
      // 先停掉当前队列，稍作间隔再重试：
      // Chromium 在 cancel() 同一执行周期内调 speak() 会静默丢弃新 utterance。
      const timer = setTimeout(() => {
        if (currentRequest !== requestId.current) return;
        if (synthesis.speaking || synthesis.pending) synthesis.cancel();
        const next = setTimeout(() => startSystem(attempt + 1), 80);
        timers.current.push(next);
      }, 200);
      timers.current.push(timer);
    };

    const start = () => {
      if (!supported) {
        if (hasFallback) startAudio();
        else setError('当前浏览器不支持语音播报，手动点名不受影响。');
        return;
      }
      // 已确认系统语音不可用 → 直接音频兜底（本会话内不再反复试探）
      if (useAudioRef.current) {
        startAudio();
        return;
      }
      // 有兜底且引擎就绪但语音列表为空（典型：国内 Chrome 拉不到 Google 语音）
      // → 等一个 voiceschanged 窗口，仍为空就走服务器音频
      if (hasFallback && voicesRef.current.length === 0) {
        const grace = setTimeout(() => {
          if (currentRequest !== requestId.current) return;
          if (voicesRef.current.length > 0) {
            if (synthesis.speaking || synthesis.pending) synthesis.cancel();
            startSystem(1);
          } else {
            startAudio();
          }
        }, VOICES_GRACE_MS);
        timers.current.push(grace);
        return;
      }
      if (synthesis.speaking || synthesis.pending) synthesis.cancel();
      // 与 cancel() 错开一个执行周期再 speak，避免 Chromium 静默丢弃
      const t = setTimeout(() => {
        if (currentRequest !== requestId.current) return;
        startSystem(1);
      }, 60);
      timers.current.push(t);
    };

    start();
    return true;
  }, [clearTimers, muted, playAudioFallback, rate, stopAudio, supported, voice]);

  const toggleMuted = useCallback(() => {
    setMuted((value) => {
      const next = !value;
      if (next) {
        clearTimers();
        stopAudio();
        requestId.current += 1; // 作废进行中的播报
      }
      return next;
    });
  }, [clearTimers, stopAudio]);

  return { muted, supported, speak, toggleMuted, rate, setRate, voices, voiceName, setVoice, error };
}
