import { X } from 'lucide-react';
import { useEffect, useRef, type ReactNode } from 'react';

export function Dialog({ title, description, children, footer, onClose }: { title: string; description?: string; children: ReactNode; footer?: ReactNode; onClose(): void }) {
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    panel.current?.querySelector<HTMLElement>('input,select,button')?.focus();
    function keydown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose();
      if (event.key !== 'Tab' || !panel.current) return;
      const items = [...panel.current.querySelectorAll<HTMLElement>('button,input,select,textarea,a[href]')].filter((item) => !item.hasAttribute('disabled'));
      if (!items.length) return;
      const first = items[0]; const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
    document.addEventListener('keydown', keydown);
    return () => { document.removeEventListener('keydown', keydown); previous?.focus(); };
  }, [onClose]);
  return <div className="dialog-backdrop" onMouseDown={(event) => { if (event.currentTarget === event.target) onClose(); }}><div className="dialog" role="dialog" aria-modal="true" aria-labelledby="dialog-title" ref={panel}><header><div><h2 id="dialog-title">{title}</h2>{description && <p>{description}</p>}</div><button className="icon-btn" onClick={onClose} aria-label="关闭对话框" title="关闭"><X aria-hidden="true" /></button></header><div className="dialog-body">{children}</div>{footer && <footer>{footer}</footer>}</div></div>;
}
