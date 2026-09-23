import { useContext, useEffect, useRef } from 'react';
import { UNSAFE_NavigationContext, useLocation } from 'react-router-dom';

export const discardMessage = '有未保存的成绩修改，确定放弃修改并离开吗？';

/** Declarative BrowserRouter has no useBlocker support. Guard its navigator,
 * browser POP events, and document unload while the editor has drafts. */
export function useUnsavedScores(dirty: boolean) {
  const { navigator } = useContext(UNSAFE_NavigationContext);
  const location = useLocation();
  const latestDirty = useRef(dirty); latestDirty.current = dirty;
  const index = useRef<number | null>(window.history.state?.idx ?? null);
  useEffect(() => { index.current = window.history.state?.idx ?? null; }, [location]);
  useEffect(() => {
    const push = navigator.push.bind(navigator); const replace = navigator.replace.bind(navigator); const go = navigator.go.bind(navigator);
    const allowed = () => !latestDirty.current || window.confirm(discardMessage);
    navigator.push = (...args) => { if (allowed()) { latestDirty.current = false; push(...args); } };
    navigator.replace = (...args) => { if (allowed()) { latestDirty.current = false; replace(...args); } };
    navigator.go = (...args) => { if (allowed()) { latestDirty.current = false; go(...args); } };
    let restoring = false;
    function onPop(event: PopStateEvent) {
      if (restoring) { restoring = false; event.stopImmediatePropagation(); return; }
      if (!latestDirty.current) return;
      const nextIndex = event.state?.idx;
      if (typeof nextIndex !== 'number' || index.current === null) return;
      if (!window.confirm(discardMessage)) {
        event.stopImmediatePropagation(); restoring = true; window.history.go(index.current - nextIndex);
      } else latestDirty.current = false;
    }
    function unload(event: BeforeUnloadEvent) { if (latestDirty.current) { event.preventDefault(); event.returnValue = ''; } }
    window.addEventListener('beforeunload', unload); window.addEventListener('popstate', onPop, true);
    return () => { navigator.push = push; navigator.replace = replace; navigator.go = go; window.removeEventListener('beforeunload', unload); window.removeEventListener('popstate', onPop, true); };
  }, [navigator]);
  return () => { latestDirty.current = false; };
}
