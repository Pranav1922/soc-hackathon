import { useEffect } from "react";
import type { RefObject } from "react";

const SELECTOR =
  'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])';

/** Keeps Tab focus cycling within `ref` while `active` — for modals/palettes. */
export function useFocusTrap(ref: RefObject<HTMLElement>, active: boolean): void {
  useEffect(() => {
    if (!active) return;
    const el = ref.current;
    if (!el) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;
      const nodes = Array.from(el.querySelectorAll<HTMLElement>(SELECTOR)).filter((n) => n.offsetParent !== null);
      if (nodes.length === 0) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    el.addEventListener("keydown", onKey);
    return () => el.removeEventListener("keydown", onKey);
  }, [ref, active]);
}
