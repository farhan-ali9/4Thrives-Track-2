Object.defineProperty(window, "scrollTo", {
  value: () => undefined,
  writable: true,
});
