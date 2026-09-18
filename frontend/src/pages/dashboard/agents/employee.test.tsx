import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { EmployeeWorkspaceSection } from './employee';

describe('EmployeeWorkspaceSection status labels', () => {
  it('keeps the attention label readable while preserving the amber status boundary', () => {
    render(<EmployeeWorkspaceSection title="Готовность процесса" tone="attention">Проверьте шаги</EmployeeWorkspaceSection>);

    const title = screen.getByText('Готовность процесса');
    expect(title).toHaveClass('opacity-80');
    expect(title).not.toHaveClass('opacity-60');
    expect(title.parentElement).toHaveClass('bg-amber-50', 'text-amber-950');
    expect(screen.getByText('Проверьте шаги')).toBeVisible();
  });

  it('does not turn a normal workspace section into an attention state', () => {
    render(<EmployeeWorkspaceSection title="Цель агента">Подготовить безопасный результат</EmployeeWorkspaceSection>);

    const title = screen.getByText('Цель агента');
    expect(title).toHaveClass('opacity-80');
    expect(title.parentElement).toHaveClass('bg-white');
    expect(title.parentElement).not.toHaveClass('bg-amber-50', 'text-amber-950');
  });
});
