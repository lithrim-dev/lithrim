/* setup.js — Vitest global setup. Extends expect with jest-dom matchers, clears
   mocks between tests, and polyfills the browser APIs Radix primitives use that
   jsdom lacks (ResizeObserver, matchMedia, pointer-capture, scrollIntoView).
   Referenced by vite.config.js `test.setupFiles`. */
import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = globalThis.ResizeObserver || ResizeObserverStub;

if (!globalThis.matchMedia) {
  globalThis.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} });
}

// UI-LOGIN-1: this jsdom build exposes `localStorage` as a bare empty object with NO Storage
// methods (setItem/getItem/removeItem/clear are undefined), so the runtime BFF token helpers
// (bff.js) would silently no-op under test. Polyfill a minimal in-memory Storage so the token
// round-trip is genuinely exercised (same spirit as the ResizeObserver/matchMedia shims above).
if (typeof localStorage === "undefined" || typeof localStorage.setItem !== "function") {
  const store = new Map();
  const ls = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => { store.set(String(k), String(v)); },
    removeItem: (k) => { store.delete(k); },
    clear: () => { store.clear(); },
    key: (i) => Array.from(store.keys())[i] ?? null,
    get length() { return store.size; },
  };
  Object.defineProperty(globalThis, "localStorage", { value: ls, configurable: true, writable: true });
  if (typeof window !== "undefined") Object.defineProperty(window, "localStorage", { value: ls, configurable: true, writable: true });
}

// Radix Select/Slider call these; jsdom has no layout engine.
if (typeof Element !== "undefined") {
  Element.prototype.hasPointerCapture = Element.prototype.hasPointerCapture || (() => false);
  Element.prototype.setPointerCapture = Element.prototype.setPointerCapture || (() => {});
  Element.prototype.releasePointerCapture = Element.prototype.releasePointerCapture || (() => {});
  Element.prototype.scrollIntoView = Element.prototype.scrollIntoView || (() => {});
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
