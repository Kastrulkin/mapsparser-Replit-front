import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';

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
  it('reproduces the removeChild crash when translated text is replaced during navigation', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);

    render(
      <ErrorBoundary>
        <TranslatedNavigationHarness />
      </ErrorBoundary>,
    );

    const routeContent = screen.getByTestId('route-content');
    const textNode = routeContent.firstChild;
    const translationWrapper = document.createElement('font');

    expect(textNode).not.toBeNull();
    translationWrapper.setAttribute('data-external-translation', 'true');
    routeContent.appendChild(translationWrapper);
    translationWrapper.appendChild(textNode!);

    fireEvent.click(screen.getByRole('button', { name: 'Open agents' }));

    expect(screen.getByText('Что-то пошло не так')).toBeInTheDocument();
    expect(screen.getByText(/NotFoundError.*node to be removed/i)).toBeInTheDocument();
    consoleError.mockRestore();
  });
});
