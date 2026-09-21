import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Suspense } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  get: vi.fn(), post: vi.fn(),
  dashboardContext: { currentBusinessId: 'request-test-business', currentBusiness: { id: 'request-test-business', name: 'Request test' }, demoMode: false },
}));
const businessId = 'request-test-business';

type Response = { data: Record<string, unknown> };
type RequestOptions = { params?: { run_status?: string; business_id?: string } };
type HarnessScope = {
  selectedBlueprint: { id: string } | null;
  setSelectedBlueprintId: (id: string) => void;
  blueprintDetails: { blueprint?: { id?: string }; candidate_version_id?: string; runs?: { id: string }[] } | null;
  agentDetailsById: Record<string, { candidate_version_id?: string }>;
  selectedPendingApproval: { id: string } | null;
  agentReview: { summary?: string } | null;
  error: string | null;
  setRunStatusFilter: (filter: string) => void;
  loadBlueprintDetails: (id: string) => Promise<void>;
  loadBlueprints: () => Promise<void>;
  decideApproval: (decision: 'approve' | 'reject') => Promise<void>;
};

vi.mock('@/i18n/LanguageContext.logic', () => ({ useLanguage: () => ({ language: 'ru' }) }));
vi.mock('@/lib/auth_new', () => ({ newAuth: { getCurrentUserSync: () => null, getCurrentUser: async () => null, getToken: () => null } }));
vi.mock('@/lib/browserSessionFetch', () => ({ browserAuthenticationAvailable: () => false }));
vi.mock('@/services/api', () => ({ api: mocks }));
vi.mock('react-router-dom', () => ({
  useLocation: () => ({ search: '' }),
  useOutletContext: () => mocks.dashboardContext,
}));
vi.mock('./agents/useAgentRunAnimation', () => ({ useAgentRunAnimation: () => ({
  runAnimation: null, setRunAnimation: () => undefined, beginRunAnimation: () => undefined,
  finishRunAnimation: () => undefined, failRunAnimation: () => undefined, syncRunAnimation: () => undefined,
}) }));
vi.mock('./agents/useAgentRunTracking', () => ({ useAgentRunTracking: () => ({ waitForAgentRun: async () => undefined }) }));
vi.mock('./agents/view', () => ({
  AgentBlueprintsView: ({ scope }: { scope: HarnessScope }) => (
    <section>
      <button onClick={() => scope.setSelectedBlueprintId('agent-a')}>Select A</button>
      <button onClick={() => scope.setSelectedBlueprintId('agent-b')}>Select B</button>
      <button onClick={() => { scope.setSelectedBlueprintId('agent-b'); void scope.loadBlueprintDetails('agent-b'); }}>Select and load B</button>
      <button onClick={() => scope.selectedBlueprint && scope.loadBlueprintDetails(scope.selectedBlueprint.id)}>Refresh details</button>
      <button onClick={() => scope.loadBlueprints()}>Refresh registry</button>
      <button onClick={() => scope.setRunStatusFilter('failed')}>Filter failed</button>
      <button disabled={!scope.selectedPendingApproval} onClick={() => scope.decideApproval('approve')}>Approve shown result</button>
      <output data-testid="selected">{scope.selectedBlueprint?.id || ''}</output>
      <output data-testid="details">{scope.blueprintDetails?.blueprint?.id || ''}</output>
      <output data-testid="version">{scope.blueprintDetails?.candidate_version_id || ''}</output>
      <output data-testid="runs">{scope.blueprintDetails?.runs?.map(run => run.id).join(',') || ''}</output>
      <output data-testid="approval">{scope.selectedPendingApproval?.id || ''}</output>
      <output data-testid="cached-a">{scope.agentDetailsById['agent-a']?.candidate_version_id || ''}</output>
      <output data-testid="review">{scope.agentReview?.summary || ''}</output>
      <output data-testid="error">{scope.error || ''}</output>
    </section>
  ),
}));

import { AgentBlueprintsWorkspace } from './AgentBlueprintsWorkspace';

function deferred() {
  let resolve: (response: Response) => void = () => { throw new Error('deferred not initialized'); };
  let reject: (error: Error) => void = () => { throw new Error('deferred not initialized'); };
  const promise = new Promise<Response>((accept, fail) => { resolve = accept; reject = fail; });
  return { promise, resolve, reject };
}

function details(id: string, version = `${id}-v1`, owner = businessId): Response {
  return { data: {
    blueprint: { id, business_id: owner }, candidate_version_id: version,
    versions: [], runs: [{ id: `${id}-run`, blueprint_id: id, status: 'waiting_approval' }],
    approval_queue: [{ id: `${id}-approval`, run_id: `${id}-run`, status: 'pending', approval_type: 'final_output', title: `${id} result`, payload_json: {} }],
  } };
}

function route(url: string, options?: RequestOptions): Promise<Response> {
  if (url === '/agent-blueprints') return Promise.resolve({ data: { blueprints: ['agent-a', 'agent-b'].map(id => ({ id, business_id: businessId, name: id, category: 'operations', status: 'draft', metadata_json: {} })) } });
  if (url.startsWith('/agent-runs/')) return new Promise(() => undefined);
  if (url.endsWith('/review')) return Promise.resolve({ data: { review: { summary: url.includes('agent-a') ? 'Review A' : 'Review B' } } });
  if (url === '/agent-blueprints/agent-a') return Promise.resolve(details('agent-a', options?.params?.run_status === 'failed' ? 'filtered-a' : 'agent-a-v1'));
  if (url === '/agent-blueprints/agent-b') return Promise.resolve(details('agent-b'));
  return Promise.resolve({ data: {} });
}

function mount() {
  return render(<Suspense fallback={<div>Loading</div>}><AgentBlueprintsWorkspace /></Suspense>);
}

async function settle(pending: ReturnType<typeof deferred>, response: Response) {
  await act(async () => { pending.resolve(response); await pending.promise; });
}

describe('Agent workspace selected-request integrity', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(() => { throw new Error('unexpected real network'); }));
    mocks.get.mockReset();
    mocks.get.mockImplementation(route);
    mocks.post.mockReset();
    mocks.post.mockImplementation(() => new Promise(() => undefined));
  });
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it('does not route a shown B approval to late A details while run loading is pending', async () => {
    const pendingA = deferred();
    mocks.get.mockImplementation((url: string, options?: RequestOptions) => url === '/agent-blueprints/agent-a' && options?.params?.run_status !== 'all' ? pendingA.promise : route(url, options));
    mount();
    await waitFor(() => expect(screen.getByTestId('selected')).toHaveTextContent('agent-a'));
    fireEvent.click(screen.getByText('Select B'));
    await waitFor(() => expect(screen.getByTestId('approval')).toHaveTextContent('agent-b-approval'));
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith('/agent-runs/agent-b-run'));
    await settle(pendingA, details('agent-a'));
    fireEvent.click(screen.getByText('Approve shown result'));
    expect(mocks.post).toHaveBeenCalledExactlyOnceWith('/agent-runs/agent-b-run/approvals/agent-b-approval/approve', { reason: 'Approved from dashboard' });
    expect(screen.getByTestId('details')).toHaveTextContent('agent-b');
    expect(screen.getByTestId('runs')).toHaveTextContent('agent-b-run');
  });

  it('ignores a rejected A request after B loads successfully', async () => {
    const pendingA = deferred();
    mocks.get.mockImplementation((url: string, options?: RequestOptions) => url === '/agent-blueprints/agent-a' && options?.params?.run_status !== 'all' ? pendingA.promise : route(url, options));
    mount();
    await waitFor(() => expect(screen.getByTestId('selected')).toHaveTextContent('agent-a'));
    fireEvent.click(screen.getByText('Select B'));
    await waitFor(() => expect(screen.getByTestId('details')).toHaveTextContent('agent-b'));
    await act(async () => { pendingA.reject(new Error('old A failure')); await pendingA.promise.catch(() => undefined); });
    expect(screen.getByTestId('error')).toBeEmptyDOMElement();
    expect(screen.getByTestId('details')).toHaveTextContent('agent-b');
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it('keeps the newest same-agent refresh in primary details and the registry cache', async () => {
    mount();
    await waitFor(() => expect(screen.getByTestId('version')).toHaveTextContent('agent-a-v1'));
    const older = deferred();
    let requests = 0;
    mocks.get.mockImplementation((url: string, options?: RequestOptions) => {
      if (url === '/agent-blueprints/agent-a' && options?.params?.run_status !== 'all') {
        requests += 1;
        return requests === 1 ? older.promise : Promise.resolve(details('agent-a', 'newest-a'));
      }
      return route(url, options);
    });
    fireEvent.click(screen.getByText('Refresh details'));
    fireEvent.click(screen.getByText('Refresh details'));
    await waitFor(() => expect(screen.getByTestId('version')).toHaveTextContent('newest-a'));
    await settle(older, details('agent-a', 'older-a'));
    expect(screen.getByTestId('version')).toHaveTextContent('newest-a');
    expect(screen.getByTestId('cached-a')).toHaveTextContent('newest-a');
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it('keeps the current history filter when an older unfiltered request finishes', async () => {
    mount();
    await waitFor(() => expect(screen.getByTestId('version')).toHaveTextContent('agent-a-v1'));
    const older = deferred();
    mocks.get.mockImplementation((url: string, options?: RequestOptions) => url === '/agent-blueprints/agent-a' && !options?.params?.run_status ? older.promise : route(url, options));
    fireEvent.click(screen.getByText('Refresh details'));
    fireEvent.click(screen.getByText('Filter failed'));
    await waitFor(() => expect(screen.getByTestId('version')).toHaveTextContent('filtered-a'));
    await settle(older, details('agent-a', 'old-unfiltered-a'));
    expect(screen.getByTestId('version')).toHaveTextContent('filtered-a');
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it.each([['agent-a', businessId], ['agent-b', 'another-business']])('rejects mismatched response identity %s / %s', async (id, owner) => {
    mount();
    await waitFor(() => expect(screen.getByTestId('version')).toHaveTextContent('agent-a-v1'));
    mocks.get.mockImplementation((url: string, options?: RequestOptions) => url === '/agent-blueprints/agent-b' ? Promise.resolve(details(id, 'invalid-version', owner)) : route(url, options));
    fireEvent.click(screen.getByText('Select B'));
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith('/agent-blueprints/agent-b', { params: {} }));
    await act(async () => { await Promise.resolve(); });
    expect(screen.getByTestId('details')).toBeEmptyDOMElement();
    expect(screen.getByTestId('approval')).toBeEmptyDOMElement();
    expect(screen.getByText('Approve shown result')).toBeDisabled();
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it('does not replace B review with a late A review', async () => {
    const pendingA = deferred();
    mocks.get.mockImplementation((url: string, options?: RequestOptions) => url === '/agent-blueprints/agent-a/review' ? pendingA.promise : route(url, options));
    mount();
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith('/agent-blueprints/agent-a/review'));
    fireEvent.click(screen.getByText('Select B'));
    await waitFor(() => expect(screen.getByTestId('details')).toHaveTextContent('agent-b'));
    await waitFor(() => expect(screen.getByTestId('review')).toHaveTextContent('Review B'));
    await settle(pendingA, { data: { review: { summary: 'Late review A' } } });
    expect(screen.getByTestId('review')).toHaveTextContent('Review B');
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it('allows a load started in the same event that selects its target', async () => {
    mount();
    await waitFor(() => expect(screen.getByTestId('version')).toHaveTextContent('agent-a-v1'));
    fireEvent.click(screen.getByText('Select and load B'));
    await waitFor(() => expect(screen.getByTestId('details')).toHaveTextContent('agent-b'));
    expect(screen.getByTestId('selected')).toHaveTextContent('agent-b');
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it('keeps loaded details and review when the already selected employee is opened again', async () => {
    mount();
    await waitFor(() => expect(screen.getByTestId('version')).toHaveTextContent('agent-a-v1'));
    await waitFor(() => expect(screen.getByTestId('review')).toHaveTextContent('Review A'));
    fireEvent.click(screen.getByText('Select A'));
    expect(screen.getByTestId('version')).toHaveTextContent('agent-a-v1');
    expect(screen.getByTestId('review')).toHaveTextContent('Review A');
    expect(screen.getByTestId('approval')).toHaveTextContent('agent-a-approval');
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it('hides the old review when a registry refresh removes the selected employee', async () => {
    mount();
    await waitFor(() => expect(screen.getByTestId('review')).toHaveTextContent('Review A'));
    const pendingB = deferred();
    mocks.get.mockImplementation((url: string, options?: RequestOptions) => {
      if (url === '/agent-blueprints') return Promise.resolve({ data: { blueprints: [{ id: 'agent-b', business_id: businessId, name: 'agent-b', category: 'operations', status: 'draft', metadata_json: {} }] } });
      if (url === '/agent-blueprints/agent-b/review') return pendingB.promise;
      return route(url, options);
    });
    fireEvent.click(screen.getByText('Refresh registry'));
    await waitFor(() => expect(screen.getByTestId('selected')).toHaveTextContent('agent-b'));
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith('/agent-blueprints/agent-b/review'));
    expect(screen.getByTestId('review')).toBeEmptyDOMElement();
    await settle(pendingB, { data: { review: { summary: 'Review B after registry refresh' } } });
    expect(screen.getByTestId('review')).toHaveTextContent('Review B after registry refresh');
    expect(mocks.post).not.toHaveBeenCalled();
  });
});
