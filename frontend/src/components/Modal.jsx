import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

// Otwarte okna, od najstarszego. Esc i blokada przewijania dotyczą tylko wierzchniego.
const stack = [];
const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

// Portal do <body>: okno nie dziedziczy pozycjonowania ani <label>/<form> rodzica.
// closeOnBackdrop=false dla formularzy, gdzie przypadkowy klik obok zgubiłby wpisane dane.
export default function Modal({ label, onClose, closeOnBackdrop = true, className = "", as: Tag = "div", children, ...rest }) {
  const ref = useRef(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    const node = ref.current;
    const previous = document.activeElement;
    stack.push(node);
    document.body.style.overflow = "hidden";
    (node.querySelector("[autofocus]") || node.querySelector(FOCUSABLE) || node).focus();

    const onKey = (e) => {
      if (stack[stack.length - 1] !== node) return;
      if (e.key === "Escape" && closeRef.current) {
        e.preventDefault();
        closeRef.current();
      } else if (e.key === "Tab") {
        const items = [...node.querySelectorAll(FOCUSABLE)];
        if (!items.length) return;
        const first = items[0];
        const last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      stack.splice(stack.indexOf(node), 1);
      if (!stack.length) document.body.style.overflow = "";
      previous?.focus?.();
    };
  }, []);

  return createPortal(
    <div className="modal-backdrop" onClick={() => closeOnBackdrop && closeRef.current?.()}>
      <Tag
        ref={ref}
        className={`modal ${className}`}
        role="dialog"
        aria-modal="true"
        aria-label={label}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        {...rest}
      >
        {children}
      </Tag>
    </div>,
    document.body,
  );
}
