"use client";

import { type CSSProperties, useCallback, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";

type GlassSelectOption = {
  value: string;
  label: string;
};

type GlassSelectProps = {
  value: string;
  options: GlassSelectOption[];
  onChange: (value: string) => void;
  ariaLabel: string;
  className?: string;
};

export function GlassSelect({ value, options, onChange, ariaLabel, className = "" }: GlassSelectProps) {
  const id = useId();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const [open, setOpen] = useState(false);
  const [menuStyle, setMenuStyle] = useState<CSSProperties | null>(null);
  const selectedIndex = Math.max(0, options.findIndex((option) => option.value === value));
  const selectedOption = options[selectedIndex] ?? options[0];

  const updateMenuPosition = useCallback(() => {
    const button = buttonRef.current;
    if (!button) {
      return;
    }

    const rect = button.getBoundingClientRect();
    const estimatedHeight = Math.min(256, options.length * 40 + 8);
    const belowSpace = window.innerHeight - rect.bottom - 12;
    const aboveSpace = rect.top - 12;
    const openAbove = belowSpace < estimatedHeight && aboveSpace > belowSpace;
    const maxHeight = Math.max(120, Math.min(256, openAbove ? aboveSpace - 8 : belowSpace - 8));
    const top = openAbove ? Math.max(12, rect.top - maxHeight - 8) : rect.bottom + 8;
    const left = Math.min(Math.max(12, rect.left), window.innerWidth - rect.width - 12);

    setMenuStyle({
      left,
      maxHeight,
      position: "fixed",
      top,
      width: rect.width,
      zIndex: 9999,
    });
  }, [options.length]);

  useEffect(() => {
    if (!open) {
      return;
    }

    function closeOnOutsideClick(event: MouseEvent) {
      const target = event.target as Node;
      if (!containerRef.current?.contains(target) && !menuRef.current?.contains(target)) {
        setOpen(false);
      }
    }

    function closeOnScroll() {
      setOpen(false);
    }

    function repositionMenu() {
      updateMenuPosition();
    }

    updateMenuPosition();
    document.addEventListener("mousedown", closeOnOutsideClick);
    window.addEventListener("resize", repositionMenu);
    window.addEventListener("scroll", closeOnScroll, true);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      window.removeEventListener("resize", repositionMenu);
      window.removeEventListener("scroll", closeOnScroll, true);
    };
  }, [open, updateMenuPosition]);

  function selectOption(nextValue: string) {
    onChange(nextValue);
    setOpen(false);
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "Escape") {
      setOpen(false);
      return;
    }

    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setOpen((current) => !current);
      return;
    }

    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") {
      return;
    }

    event.preventDefault();
    const direction = event.key === "ArrowDown" ? 1 : -1;
    const nextIndex = (selectedIndex + direction + options.length) % options.length;
    onChange(options[nextIndex]?.value ?? value);
  }

  return (
    <div className={`relative ${className}`} ref={containerRef}>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-label={ariaLabel}
        className="ea-input w-full px-2 py-2 text-sm md:hidden"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>

      <div className="hidden md:block">
        <button
          ref={buttonRef}
          type="button"
          aria-label={ariaLabel}
          aria-expanded={open}
          aria-controls={`${id}-listbox`}
          className="ea-input flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm"
          onClick={() => setOpen((current) => !current)}
          onKeyDown={onKeyDown}
        >
          <span className="truncate">{selectedOption?.label}</span>
          <ChevronIcon className={`h-4 w-4 shrink-0 text-brand-signal transition-transform ${open ? "rotate-180" : ""}`} />
        </button>

        {open && menuStyle && typeof document !== "undefined" ? createPortal(
          <div
            ref={menuRef}
            id={`${id}-listbox`}
            role="listbox"
            style={menuStyle}
            className="ea-select-menu"
          >
            {options.map((option) => {
              const selected = option.value === value;
              return (
                <button
                  key={option.value}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  onClick={() => selectOption(option.value)}
                  className={selected ? "ea-select-option ea-select-option-active" : "ea-select-option"}
                >
                  <span>{option.label}</span>
                  {selected ? <span className="h-1.5 w-1.5 rounded-full bg-white" /> : null}
                </button>
              );
            })}
          </div>,
          document.body,
        ) : null}
      </div>
    </div>
  );
}

function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}
