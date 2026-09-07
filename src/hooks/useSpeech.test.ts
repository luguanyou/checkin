import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useSpeech } from './useSpeech';

describe('useSpeech', () => {
  const speak = vi.fn();
  const cancel = vi.fn();
  const resume = vi.fn();
  const voices = [
    { name: '普通话女声', lang: 'zh-CN', voiceURI: 'female' },
    { name: 'English', lang: 'en-US', voiceURI: 'english' },
  ] as SpeechSynthesisVoice[];

  beforeEach(() => {
    vi.restoreAllMocks();
    Object.defineProperty(window, 'speechSynthesis', {
      configurable: true,
      value: { speak, cancel, resume, getVoices: () => voices, addEventListener: vi.fn(), removeEventListener: vi.fn() },
    });
    Object.defineProperty(window, 'SpeechSynthesisUtterance', {
      configurable: true,
      value: class {
        text: string;
        rate = 1;
        volume = 1;
        lang = '';
        voice?: SpeechSynthesisVoice;
        constructor(text: string) { this.text = text; }
      },
    });
    speak.mockClear(); cancel.mockClear(); resume.mockClear();
  });

  it('speaks with the selected rate and voice', () => {
    const { result } = renderHook(() => useSpeech());
    act(() => result.current.setRate(1.35));
    act(() => result.current.setVoice('female'));
    act(() => result.current.speak('张敏'));

    expect(cancel).toHaveBeenCalledTimes(1);
    expect(resume).toHaveBeenCalledTimes(1);
    expect(speak).toHaveBeenCalledTimes(1);
    expect(speak.mock.calls[0][0]).toMatchObject({ text: '张敏', rate: 1.35, voice: voices[0], lang: 'zh-CN' });
  });
});
