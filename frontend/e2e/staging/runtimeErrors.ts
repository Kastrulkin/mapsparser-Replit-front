interface ConsoleErrorMessage {
  type(): string;
  location(): { url: string };
  text(): string;
}

interface RuntimeErrorSource {
  on(event: 'pageerror', listener: (error: Error) => void): unknown;
  on(event: 'console', listener: (message: ConsoleErrorMessage) => void): unknown;
}

export const observeRuntimeErrors = (page: RuntimeErrorSource, baseURL: string | undefined) => {
  if (!baseURL) throw new Error('Runtime error observation requires a configured staging baseURL.');
  const target = new URL(baseURL);
  if (!['http:', 'https:'].includes(target.protocol)) {
    throw new Error('Runtime error observation requires an HTTP staging baseURL.');
  }
  const appOrigin = target.origin;
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => {
    if (message.type() !== 'error') return;
    const sourceUrl = message.location().url;
    if (sourceUrl) {
      try {
        const sourceOrigin = new URL(sourceUrl, appOrigin).origin;
        if (sourceOrigin !== appOrigin && sourceOrigin !== 'null') return;
      } catch {
        // Unknown sources must not silently hide a runtime error.
      }
    }
    errors.push(message.text());
  });
  return errors;
};
