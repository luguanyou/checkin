import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useSpeech } from './useSpeech';

type UtteranceLike = {
  text: string;
  rate: number;
  volume: number;
  lang: string;
  voice?: SpeechSynthesisVoice;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onerror: ((event: { error: string }) => void) | null;
};

describe('useSpeech', () => {
  const speak = vi.fn<(utterance: UtteranceLike) => void>();
  const cancel = vi.fn();
  const resume = vi.fn();
  const voices = [
    { name: '普通话女声', lang: 'zh-CN', voiceURI: 'female' },
    { name: 'English', lang: 'en-US', voiceURI: 'english' },
  ] as SpeechSynthesisVoice[];

  beforeEach(() => {
    vi.useFakeTimers();
    vi.restoreAllMocks();
    Object.defineProperty(window, 'speechSynthesis', {
      configurable: true,
      value: {
        speak,
        cancel,
        resume,
        speaking: false,
        pending: false,
        getVoices: () => voices,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      },
    });
    Object.defineProperty(window, 'SpeechSynthesisUtterance', {
      configurable: true,
      value: class {
        text: string;
        rate = 1;
        volume = 1;
        lang = '';
        voice?: SpeechSynthesisVoice;
        onstart: UtteranceLike['onstart'] = null;
        onend: UtteranceLike['onend'] = null;
        onerror: UtteranceLike['onerror'] = null;
        constructor(text: string) { this.text = text; }
      },
    });
    speak.mockClear();
    cancel.mockClear();
    resume.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('speaks with the selected rate and voice when the engine accepts', () => {
    speak.mockImplementation((utterance) => { utterance.onstart?.(); utterance.onend?.(); });
    const { result } = renderHook(() => useSpeech());
    act(() => result.current.setRate(1.35));
    act(() => result.current.setVoice('female'));
    act(() => result.current.speak('张敏'));
    act(() => { vi.advanceTimersByTime(100); }); // flush the 60ms cancel-safe enqueue delay

    expect(cancel).not.toHaveBeenCalled();
    expect(resume).toHaveBeenCalledTimes(1);
    expect(speak).toHaveBeenCalledTimes(1);
    expect(speak.mock.calls[0][0]).toMatchObject({ text: '张敏', rate: 1.35, voice: voices[0], lang: 'zh-CN' });
    expect(result.current.error).toBe('');
  });

  it('cancels the running utterance and defers the new one when the engine is busy', () => {
    speak.mockImplementation((utterance) => { utterance.onstart?.(); utterance.onend?.(); });
    (window.speechSynthesis as unknown as { speaking: boolean }).speaking = true;
    const { result } = renderHook(() => useSpeech());
    act(() => result.current.speak('张敏'));
    expect(cancel).toHaveBeenCalledTimes(1);
    expect(speak).not.toHaveBeenCalled(); // not yet: waiting for cancel() to flush
    act(() => { vi.advanceTimersByTime(100); });
    expect(speak).toHaveBeenCalledTimes(1);
  });

  it('surfaces an actionable error when the engine swallows the utterance silently (e.g. no voices)', () => {
    // engine accepts nothing and fires no events — the "no sound and no hint" bug
    speak.mockImplementation(() => { /* silent engine */ });
    (window.speechSynthesis as unknown as { getVoices: () => SpeechSynthesisVoice[] }).getVoices = () => [];
    const { result } = renderHook(() => useSpeech());
    act(() => result.current.speak('张敏'));
    act(() => { vi.advanceTimersByTime(2200); }); // attempt1 + watchdog + retry + attempt2 + watchdog

    expect(speak).toHaveBeenCalledTimes(2); // retried exactly once
    expect(result.current.error).toContain('未检测到可用的中文语音引擎');
  });

  it('retries once on a transient engine error, then reports it', () => {
    speak.mockImplementation((utterance) => { utterance.onerror?.({ error: 'synthesis-failed' }); });
    const { result } = renderHook(() => useSpeech());
    act(() => result.current.speak('张敏'));
    act(() => { vi.advanceTimersByTime(60 + 200 + 100); }); // attempt1 errors -> retry -> attempt2
    expect(speak).toHaveBeenCalledTimes(2);
    // attempt2 also errors (mock always errors) -> final failure message
    act(() => { vi.advanceTimersByTime(0); });
    expect(result.current.error).toContain('语音播报失败');
  });

  it('falls back to server audio when the browser has no voices (e.g. Chrome in mainland China)', async () => {
    // 引擎就绪但语音列表为空 → 不再试探系统语音，直接服务器音频兜底
    speak.mockImplementation(() => { /* silent */ });
    (window.speechSynthesis as unknown as { getVoices: () => SpeechSynthesisVoice[] }).getVoices = () => [];
    const audioFallback = vi.fn<(text: string, rate: number) => Promise<Blob>>(async () => new Blob(['mp3'], { type: 'audio/mpeg' }));
    class FakeAudio { src = ''; async play() { /* noop */ } pause() { /* noop */ } load() { /* noop */ } removeAttribute() { /* noop */ } }
    vi.stubGlobal('Audio', FakeAudio);
    vi.stubGlobal('URL', { ...URL, createObjectURL: () => 'blob:mock', revokeObjectURL: () => undefined });
    const { result } = renderHook(() => useSpeech({ audioFallback }));
    act(() => result.current.speak('张敏'));
    await act(async () => { vi.advanceTimersByTime(500); await Promise.resolve(); });

    expect(speak).not.toHaveBeenCalled(); // 系统语音未被调用
    expect(audioFallback).toHaveBeenCalledTimes(1);
    expect(audioFallback.mock.calls[0][0]).toBe('张敏');
    expect(result.current.error).toBe('');
    vi.unstubAllGlobals();
  });
});
