import React, { useMemo } from 'react';
import {
  IndustryPatternsManagement,
  IndustryPatternsApiClient,
} from '../../components/IndustryPatternsManagement';

const pendingProposals = [
  {
    id: 'proposal-beauty-1',
    industry_key: 'beauty',
    pattern_type: 'service',
    proposed_pattern: 'Для beauty-услуг сохранять зону, длину, пол, возраст, препарат, объём и число сеансов.',
    confidence: 0.91,
    risk_level: 'low',
    status: 'pending_review',
    created_at: '2026-05-01T09:00:00Z',
  },
  {
    id: 'proposal-food-1',
    industry_key: 'food',
    pattern_type: 'news',
    proposed_pattern: 'Для пекарен писать новости вокруг продукта дня, свежей выпечки и локального повода точки.',
    confidence: 0.84,
    risk_level: 'medium',
    status: 'pending_review',
    created_at: '2026-05-01T09:10:00Z',
  },
];

const revisionProposals = [
  {
    id: 'proposal-medical-revision',
    industry_key: 'medical',
    pattern_type: 'review_reply',
    proposed_pattern: 'Ответы медицинских карточек должны благодарить за доверие без обещаний результата.',
    confidence: 0.72,
    risk_level: 'high',
    status: 'needs_revision',
    decision_comment: 'Уточнить запрет на медицинские гарантии.',
    created_at: '2026-05-01T10:20:00Z',
  },
];

const activeVersions = [
  {
    version_id: 'v-beauty-service-active',
    industry_key: 'beauty',
    pattern_type: 'service',
    pattern_text: 'Beauty service pattern: короткое название услуги плюс подтверждённые атрибуты без рекламной воды.',
    version: '2026.05.1',
    status: 'active',
    activated_by: 'superadmin',
    activated_at: '2026-05-01T12:00:00Z',
  },
  {
    version_id: 'v-food-news-active',
    industry_key: 'food',
    pattern_type: 'news',
    pattern_text: 'Food news pattern: конкретный продукт, свежесть, локальный контекст и без выдуманных скидок.',
    version: '2026.05.1',
    status: 'active',
    activated_by: 'superadmin',
    activated_at: '2026-05-01T12:30:00Z',
  },
];

const versionHealth = [
  {
    version_id: 'v-beauty-service-active',
    industry_key: 'beauty',
    pattern_type: 'service',
    applied_count: 42,
    result_count: 38,
    good: 31,
    needs_review: 7,
    bad_rate: 0.18,
    recommendation: 'revise_candidate',
    business_effect_score: 14,
    business_effect_status: 'positive',
    seo_score_delta: 9,
    keyword_found_delta: 6,
    manual_edits: 3,
    accepted: 28,
  },
  {
    version_id: 'v-food-news-active',
    industry_key: 'food',
    pattern_type: 'news',
    applied_count: 25,
    result_count: 25,
    good: 21,
    needs_review: 4,
    bad_rate: 0.12,
    recommendation: 'keep',
    business_effect_score: 11,
    business_effect_status: 'positive',
    seo_score_delta: 4,
    keyword_found_delta: 2,
    manual_edits: 1,
    accepted: 19,
  },
];

const versionDetail = {
  version: activeVersions[0],
  health: versionHealth[0],
  recent_reasons: ['только слабое совпадение ключа', 'ручная правка описания'],
  decisions: [
    {
      decision: 'accept',
      decided_by: 'superadmin',
      decision_comment: 'Принято после ручной проверки',
      created_at: '2026-05-01T12:00:00Z',
    },
  ],
  version_candidates: [
    {
      version_id: 'v-beauty-service-previous',
      industry_key: 'beauty',
      pattern_type: 'service',
      pattern_text: 'Beauty service pattern previous: название услуги и важные атрибуты, без обещаний результата.',
      version: '2026.04.1',
      status: 'disabled',
    },
  ],
  bad_examples: [
    {
      sample_text: 'Биоревитализация Belarti lift 1 ml превратилась в общее описание ухода без объёма.',
      result_status: 'needs_review',
      source: 'service',
      reasons: ['потерян объём'],
    },
  ],
  good_examples: [
    {
      sample_text: 'Биозавивка афрокудри на экстра длинные волосы сохранила длину и тип услуги.',
      result_status: 'good',
      source: 'service',
      reasons: ['атрибуты сохранены'],
    },
  ],
};

const rollbackPreview = {
  current: activeVersions[0],
  target: versionDetail.version_candidates[0],
  current_health: versionHealth[0],
  target_health: {
    version_id: 'v-beauty-service-previous',
    industry_key: 'beauty',
    pattern_type: 'service',
    applied_count: 33,
    result_count: 31,
    good: 27,
    needs_review: 4,
    bad_rate: 0.13,
    business_effect_score: 9,
    business_effect_status: 'positive',
  },
  text_diff: {
    current_length: 96,
    target_length: 88,
    length_delta: -8,
    similarity: 0.74,
    added_terms: ['предыдущая версия'],
    removed_terms: ['рекламная вода'],
  },
  warnings: ['rollback требует подтверждения суперадмина'],
  can_confirm: false,
  confirmation_token: '',
};

const createMockApi = (): IndustryPatternsApiClient => ({
  makeRequest: async (endpoint: string) => {
    await new Promise((resolve) => {
      window.setTimeout(resolve, 40);
    });

    if (endpoint === '/admin/industry-patterns/summary') {
      return {
        proposal_counts: {
          pending_review: pendingProposals.length,
          needs_revision: revisionProposals.length,
        },
        version_counts: {
          active: activeVersions.length,
        },
        safety: {
          superadmin_only: true,
          rollback_requires_preview: true,
          destructive_actions_require_confirmation: true,
          active_patterns: activeVersions.length,
          pending_proposals: pendingProposals.length,
          needs_revision: revisionProposals.length,
          last_proposal_at: '2026-05-01T10:20:00Z',
          last_admin_action_at: '2026-05-01T12:00:00Z',
          destructive_actions: 0,
        },
        impact: {
          totals: {
            needs_review: 7,
            business_effect_score: 25,
            business_effect_positive: 2,
            business_effect_neutral: 0,
            business_effect_negative: 0,
            seo_score_delta: 13,
            keyword_found_delta: 8,
            manual_edits: 4,
            accepted: 47,
          },
          effective: versionHealth,
          questionable: [versionHealth[0]],
        },
      };
    }

    if (endpoint === '/admin/industry-patterns/admin-events?limit=8') {
      return {
        events: [
          {
            id: 'event-1',
            action: 'pattern_version_activated',
            target_type: 'industry_pattern_version',
            target_id: 'v-beauty-service-active',
            created_at: '2026-05-01T12:00:00Z',
          },
          {
            id: 'event-2',
            action: 'proposal_sent_to_revision',
            target_type: 'industry_pattern_proposal',
            target_id: 'proposal-medical-revision',
            created_at: '2026-05-01T10:20:00Z',
          },
        ],
      };
    }

    if (endpoint.startsWith('/admin/industry-patterns/publication-matrix')) {
      return {
        industries: [
          { value: 'beauty', label: 'Beauty / салон / косметология' },
          { value: 'culture', label: 'Культурный центр / события' },
        ],
        objectives: [
          { value: 'announcement', label: 'Анонс' },
          { value: 'faq', label: 'FAQ' },
        ],
        rows: [
          {
            industry_key: 'culture',
            industry_label: 'Культурный центр / события',
            objective_key: 'announcement',
            objective_label: 'Анонс',
            prompt_type: 'content_matrix.culture.announcement',
            default_prompt: 'Тип публикации: Анонс\nПиши только про одно событие.\nНе описывай культурный центр.',
            effective_prompt: 'Тип публикации: Анонс\nПиши только про одно событие.\nНе описывай культурный центр.',
            has_override: false,
            learned_techniques: [
              {
                industry_key: 'culture',
                pattern_type: 'news',
                pattern_text: 'Для культурных событий сохранять название, дату, время и формат события.',
                version: '2026.06.1',
              },
            ],
          },
        ],
      };
    }

    if (endpoint.includes('/rollback-preview/')) {
      return { preview: rollbackPreview };
    }

    if (endpoint === '/admin/industry-patterns/versions/v-beauty-service-active') {
      return { detail: versionDetail };
    }

    if (endpoint.startsWith('/admin/industry-patterns/proposals?')) {
      const params = new URLSearchParams(endpoint.split('?')[1] || '');
      const status = params.get('status');
      return {
        proposals: status === 'needs_revision' ? revisionProposals : pendingProposals,
      };
    }

    if (endpoint.startsWith('/admin/industry-patterns/versions?')) {
      return {
        versions: activeVersions,
        health: versionHealth,
      };
    }

    return { ok: true };
  },
});

const IndustryPatternsE2EPage: React.FC = () => {
  const apiClient = useMemo(() => createMockApi(), []);

  return (
    <main className="min-h-screen bg-slate-100 p-4 md:p-6">
      <div className="mx-auto max-w-7xl space-y-4">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">E2E smoke harness</div>
          <h1 className="text-2xl font-semibold text-slate-950">Industry patterns admin</h1>
        </div>
        <IndustryPatternsManagement apiClient={apiClient} />
      </div>
    </main>
  );
};

export default IndustryPatternsE2EPage;
