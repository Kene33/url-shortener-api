import "@testing-library/jest-dom";
import { cleanup } from "@testing-library/react";
import i18n from "@/i18n";

function createStorage(): Storage {
  const store = new Map<string, string>();
  return {
    get length() {
      return store.size;
    },
    clear() {
      store.clear();
    },
    getItem(key) {
      return store.get(key) ?? null;
    },
    key(index) {
      return Array.from(store.keys())[index] ?? null;
    },
    removeItem(key) {
      store.delete(key);
    },
    setItem(key, value) {
      store.set(key, value);
    },
  };
}

const storage = createStorage();
function installMatchMedia() {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query.includes("dark"),
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

Object.defineProperty(window, "localStorage", {
  value: storage,
  configurable: true,
});
Object.defineProperty(globalThis, "localStorage", {
  value: storage,
  configurable: true,
});
installMatchMedia();

afterEach(async () => {
  cleanup();
  window.localStorage.clear();
  vi.restoreAllMocks();
  installMatchMedia();
  await i18n.changeLanguage("ru");
});
