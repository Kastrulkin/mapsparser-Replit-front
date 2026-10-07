import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { installDomOwnershipGuard } from '@/lib/domOwnershipGuard';
import { ErrorBoundary } from './ErrorBoundary';

const TranslatedNavigationHarness = () => {
  const [showLanding, setShowLanding] = useState(false);

  return (
    <div>
      <button type="button" onClick={() => setShowLanding(true)}>
        Open agents
      </button>
      <div data-testid="route-content">
        {!showLanding ? 'Technical documentation' : null}
        <span>{showLanding ? 'What owners can delegate' : 'Open the section'}</span>
      </div>
    </div>
  );
};

describe('ErrorBoundary with externally translated DOM', () => {
  it('keeps the React tree usable when translated text is replaced during navigation', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const root = document.createElement('div');
    document.body.appendChild(root);
    const uninstallGuard = installDomOwnershipGuard(root);

    try {
      render(
        <ErrorBoundary>
          <TranslatedNavigationHarness />
        </ErrorBoundary>,
        { container: root },
      );

      const routeContent = screen.getByTestId('route-content');
      const textNode = routeContent.firstChild;
      const translationWrapper = document.createElement('font');

      expect(textNode).not.toBeNull();
      translationWrapper.setAttribute('data-external-translation', 'true');
      routeContent.appendChild(translationWrapper);
      translationWrapper.appendChild(textNode!);

      fireEvent.click(screen.getByRole('button', { name: 'Open agents' }));

      expect(screen.queryByText('Что-то пошло не так')).not.toBeInTheDocument();
      expect(screen.getByText('What owners can delegate')).toBeInTheDocument();
      expect(consoleWarn).toHaveBeenCalledWith(
        '[LocalOS] Recovered external DOM ownership conflict during removeChild.',
      );
    } finally {
      uninstallGuard();
      root.remove();
      consoleError.mockRestore();
      consoleWarn.mockRestore();
    }
  });

  it('recovers insertBefore against a translated descendant', () => {
    const consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const root = document.createElement('div');
    const parent = document.createElement('div');
    const reference = document.createTextNode('Translated reference');
    const translationWrapper = document.createElement('font');
    document.body.appendChild(root);
    root.appendChild(parent);
    parent.appendChild(translationWrapper);
    translationWrapper.appendChild(reference);
    const uninstallGuard = installDomOwnershipGuard(root);

    try {
      const inserted = document.createElement('span');
      inserted.textContent = 'Inserted';
      parent.insertBefore(inserted, reference);

      expect(parent.firstChild).toBe(inserted);
      expect(parent.lastChild).toBe(translationWrapper);
      expect(consoleWarn).toHaveBeenCalledWith(
        '[LocalOS] Recovered external DOM ownership conflict during insertBefore.',
      );
    } finally {
      uninstallGuard();
      root.remove();
      consoleWarn.mockRestore();
    }
  });

  it('preserves native NotFoundError behavior outside the LocalOS root', () => {
    const root = document.createElement('div');
    const parent = document.createElement('div');
    const unrelatedChild = document.createElement('span');
    document.body.appendChild(root);
    const uninstallGuard = installDomOwnershipGuard(root);

    try {
      expect(() => parent.removeChild(unrelatedChild)).toThrow(/not a child|child can not be found/i);
    } finally {
      uninstallGuard();
      root.remove();
    }
  });
});
