import { useEffect } from "react";

/**
 * Bind real function keys to screen actions, the way a 5250 operator expects.
 * Pass a map like { F3: fn, F5: fn, F12: fn, Enter: fn }.
 *
 * Enter is ignored while focus is in a textarea so multi-line entry still works.
 */
export default function useFKeys(handlers) {
  useEffect(() => {
    function onKey(e) {
      const name = e.key === "Enter" ? "Enter" : e.key;
      const fn = handlers[name];
      if (!fn) return;
      if (name === "Enter" && e.target?.tagName === "TEXTAREA") return;
      e.preventDefault();
      fn(e);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handlers]);
}
