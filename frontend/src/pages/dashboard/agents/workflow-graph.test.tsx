import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@xyflow/react', () => ({
  Background: () => null,
  Controls: () => null,
  MarkerType: { ArrowClosed: 'arrowclosed' },
  ReactFlow: ({ nodes }: { nodes: Array<{ id: string; data: { label: ReactNode } }> }) => <div>{nodes.map((node) => <div key={node.id}>{node.data.label}</div>)}</div>,
}));

import { AgentWorkflowGraph } from './workflow-graph';

describe('AgentWorkflowGraph status labels', () => {
  it('keeps the approval label readable while preserving the amber approval state', () => {
    render(<AgentWorkflowGraph steps={[{ key: 'approval', title: 'Подтвердить', step_type: 'approval', requires_approval: true }]} />);
    const label = screen.getByText('Шаг 1');
    expect(label).toHaveClass('opacity-80');
    expect(label).not.toHaveClass('opacity-60');
    expect(label.parentElement?.parentElement).toHaveClass('bg-amber-50', 'text-amber-950');
    expect(screen.getByText('Решение человека')).toBeVisible();
  });

  it('keeps normal and capability workflow states distinct from approval', () => {
    render(<AgentWorkflowGraph steps={[{ key: 'normal', title: 'Подготовить', step_type: 'draft' }, { key: 'capability', title: 'Выполнить', step_type: 'capability' }]} />);
    const normal = screen.getByText('Подготовить').parentElement;
    const capability = screen.getByText('Выполнить').parentElement;
    expect(normal).toHaveClass('bg-white', 'text-slate-950');
    expect(normal).not.toHaveClass('bg-amber-50');
    expect(capability).toHaveClass('bg-sky-50', 'text-sky-950');
    expect(screen.getByText('Подготовка результата')).toBeVisible();
    expect(screen.getByText('Действие')).toBeVisible();
  });
});
