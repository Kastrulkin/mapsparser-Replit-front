import { useMemo } from 'react';
import {
  Background,
  Controls,
  MarkerType,
  ReactFlow,
  type Edge,
  type Node,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { cn } from '@/lib/utils';
import type { AgentExecutionContractStep } from './types';

type WorkflowGraphProps = {
  steps: AgentExecutionContractStep[];
};

const stepTone = (step: AgentExecutionContractStep) => {
  if (step.requires_approval || step.step_type === 'approval') {
    return 'bg-amber-50 text-amber-950 ring-amber-200';
  }
  if (step.step_type === 'capability') {
    return 'bg-sky-50 text-sky-950 ring-sky-200';
  }
  return 'bg-white text-slate-950 ring-slate-200';
};

const stepKind = (step: AgentExecutionContractStep) => {
  if (step.requires_approval || step.step_type === 'approval') return 'Решение человека';
  if (step.step_type === 'capability') return 'Действие';
  return 'Подготовка результата';
};

const WorkflowStepNode = ({ step, index }: { step: AgentExecutionContractStep; index: number }) => (
  <div className={cn('w-56 rounded-2xl p-3 shadow-[0_12px_28px_rgba(15,23,42,0.08)] ring-1', stepTone(step))}>
    <div className="flex items-center justify-between gap-3">
      <span className="text-[11px] font-semibold uppercase tracking-wide opacity-60">Шаг {index + 1}</span>
      <span className="rounded-full bg-white/80 px-2 py-0.5 text-[10px] font-medium ring-1 ring-current/10">
        {stepKind(step)}
      </span>
    </div>
    <div className="mt-2 text-sm font-semibold leading-5 [text-wrap:pretty]">{step.title || `Шаг ${index + 1}`}</div>
  </div>
);

export const AgentWorkflowGraph = ({ steps }: WorkflowGraphProps) => {
  const nodes = useMemo<Node[]>(
    () => steps.map((step, index) => ({
      id: step.key || `step-${index}`,
      position: { x: index * 280, y: index % 2 === 0 ? 24 : 138 },
      data: { label: <WorkflowStepNode step={step} index={index} /> },
      style: { width: 224, border: 0, padding: 0, background: 'transparent' },
      draggable: false,
      selectable: true,
    })),
    [steps],
  );
  const edges = useMemo<Edge[]>(
    () => steps.slice(0, -1).map((step, index) => ({
      id: `${step.key || index}-${steps[index + 1].key || index + 1}`,
      source: step.key || `step-${index}`,
      target: steps[index + 1].key || `step-${index + 1}`,
      markerEnd: { type: MarkerType.ArrowClosed, color: '#64748b' },
      style: { stroke: '#94a3b8', strokeWidth: 2 },
      animated: false,
    })),
    [steps],
  );

  if (!steps.length) return null;

  return (
    <div className="overflow-hidden rounded-3xl bg-slate-50 p-2 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]">
      <div className="h-[360px] overflow-hidden rounded-2xl bg-white">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          fitViewOptions={{ padding: 0.18 }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable
          minZoom={0.35}
          maxZoom={1.4}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={24} size={1} color="#e2e8f0" />
          <Controls showInteractive={false} position="bottom-right" />
        </ReactFlow>
      </div>
      <div className="flex flex-wrap gap-3 px-3 py-2 text-xs text-slate-600">
        <span>Перетащите фон, чтобы осмотреть процесс</span>
        <span className="text-slate-300">•</span>
        <span>Колесо мыши меняет масштаб</span>
      </div>
    </div>
  );
};
