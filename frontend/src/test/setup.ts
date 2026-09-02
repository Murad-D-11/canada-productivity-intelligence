import '@testing-library/jest-dom/vitest';

// Recharts' ResponsiveContainer relies on element sizing which jsdom does not
// implement; provide a deterministic size so charts render in tests.
class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;

Object.defineProperty(HTMLElement.prototype, 'offsetWidth', { configurable: true, value: 640 });
Object.defineProperty(HTMLElement.prototype, 'offsetHeight', { configurable: true, value: 320 });
