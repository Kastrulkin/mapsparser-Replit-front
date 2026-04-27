import { ReactNode } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { ContactPresenceBadges, StatusSummaryCard } from '@/components/prospecting/LeadWorkflowBlocks';
import { LeadDetailChipList, LeadDetailMetaList, LeadDetailSection } from '@/components/prospecting/LeadDetailSections';

type PartnershipLead = {
  id: string;
  name?: string;
  city?: string;
  category?: string;
  partnership_stage?: string;
  source_provider?: string;
  source_kind?: string;
  external_source_id?: string;
  external_place_id?: string;
  lat?: number;
  lon?: number;
  matched_sources_json?: string[] | null;
  website?: string;
  phone?: string;
  email?: string;
  telegram_url?: string;
  whatsapp_url?: string;
  selected_channel?: string;
  parse_status?: string;
  pilot_cohort?: string;
  next_best_action?: {
    label?: string;
    hint?: string;
  };
  enrich_payload_json?: {
    provider?: string;
    found_fields?: string[];
    confidence?: Record<string, number>;
  } | null;
};

type LeadEditState = {
  name: string;
  city: string;
  category: string;
  address: string;
  phone: string;
  email: string;
  website: string;
  telegram_url: string;
  whatsapp_url: string;
};

type FlowStatus = {
  draftsTotal?: number;
  draftsApproved?: number;
  sentTotal?: number;
  outcomeFinal?: string | null;
};

type AuditPresentation = {
  label: string;
  variant?: 'default' | 'secondary' | 'outline' | 'destructive';
  tone?: 'default' | 'success' | 'warning' | 'info' | 'danger';
  primary: string;
  secondary?: string;
};

type StagePresentation = {
  label: string;
  variant?: 'default' | 'secondary' | 'outline' | 'destructive';
  tone?: 'default' | 'success' | 'warning' | 'info' | 'danger';
};

type MatchData = {
  match_score?: number;
  overlap?: string[];
  complement?: {
    partner_strength_tokens?: string[];
  };
  offer_angles?: string[];
  score_explanation?: string;
  reason_codes?: string[];
};

type AuditData = {
  services_preview?: unknown[];
};

type CohortOption = {
  value: string;
  label: string;
};

type PartnershipLeadDetailDrawerProps = {
  selectedLead: PartnershipLead;
  selectedLeadFlowStatus?: FlowStatus | null;
  stagePresentation: StagePresentation;
  auditPresentation: AuditPresentation;
  onClose: () => void;
  auditData?: AuditData | null;
  matchData?: MatchData | null;
  draftText?: string;
  selectedLeadLogo?: string | null;
  selectedLeadPhotos: string[];
  leadEdit: LeadEditState;
  setLeadEdit: (updater: (previous: LeadEditState) => LeadEditState) => void;
  loading?: boolean;
  onSaveLeadContacts: () => void;
  currentBusinessId?: string | null;
  pilotCohortOptions: CohortOption[];
  onPilotCohortChange: (value: string) => void | Promise<void>;
};

function DrawerSection({ children }: { children: ReactNode }) {
  return <div className="space-y-4 px-5 py-5">{children}</div>;
}

export default function PartnershipLeadDetailDrawer({
  selectedLead,
  selectedLeadFlowStatus,
  stagePresentation,
  auditPresentation,
  onClose,
  auditData,
  matchData,
  draftText,
  selectedLeadLogo,
  selectedLeadPhotos,
  leadEdit,
  setLeadEdit,
  loading,
  onSaveLeadContacts,
  currentBusinessId,
  pilotCohortOptions,
  onPilotCohortChange,
}: PartnershipLeadDetailDrawerProps) {
  return (
    <div className="fixed inset-0 z-50 bg-black/25 backdrop-blur-sm" onClick={onClose}>
      <div
        className="absolute inset-y-0 right-0 w-full max-w-3xl overflow-y-auto border-l border-border bg-background shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur">
          <div className="flex items-start justify-between gap-3 px-5 py-4">
            <div>
              <h2 className="text-xl font-semibold text-foreground">{selectedLead.name || 'Карточка лида'}</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                {selectedLead.city || '—'} · {selectedLead.category || '—'} · этап: {selectedLead.partnership_stage || 'imported'}
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={onClose}>
              Закрыть
            </Button>
          </div>
        </div>

        <DrawerSection>
          {selectedLead.next_best_action ? (
            <StatusSummaryCard
              title="Следующий шаг"
              statusLabel="В работе"
              statusVariant="secondary"
              tone="info"
              primaryText={selectedLead.next_best_action.label || '—'}
              secondaryText={selectedLead.next_best_action.hint || '—'}
            />
          ) : null}

          <div className="grid gap-4 lg:grid-cols-2">
            <StatusSummaryCard
              title="Поток"
              statusLabel={stagePresentation.label}
              statusVariant={stagePresentation.variant}
              tone={stagePresentation.tone}
              primaryText={`stage: ${selectedLead.partnership_stage || 'imported'} · parse: ${selectedLead.parse_status || '—'} · channel: ${selectedLead.selected_channel || '—'}`}
              secondaryText={`drafts: ${selectedLeadFlowStatus?.draftsTotal ?? 0} · approved: ${selectedLeadFlowStatus?.draftsApproved ?? 0} · sent: ${selectedLeadFlowStatus?.sentTotal ?? 0} · outcome: ${selectedLeadFlowStatus?.outcomeFinal || '—'}`}
            />
            <StatusSummaryCard
              title="Аудит"
              statusLabel={auditPresentation.label}
              statusVariant={auditPresentation.variant}
              tone={auditPresentation.tone}
              primaryText={auditPresentation.primary}
              secondaryText={auditPresentation.secondary}
            />
          </div>

          <LeadDetailSection title="Источник и контакты">
            <LeadDetailMetaList
              columns={2}
              items={[
                { label: 'Provider', value: selectedLead.source_provider || '—' },
                { label: 'Source', value: selectedLead.source_kind || '—' },
                { label: 'External source id', value: selectedLead.external_source_id || '—' },
                { label: 'External place id', value: selectedLead.external_place_id || '—' },
                { label: 'Координаты', value: `${selectedLead.lat ?? '—'}, ${selectedLead.lon ?? '—'}` },
                {
                  label: 'Matched sources',
                  value: Array.isArray(selectedLead.matched_sources_json) && selectedLead.matched_sources_json.length
                    ? selectedLead.matched_sources_json.join(', ')
                    : '—',
                },
              ]}
            />
            <ContactPresenceBadges
              website={selectedLead.website}
              phone={selectedLead.phone}
              email={selectedLead.email}
              telegramUrl={selectedLead.telegram_url}
              whatsappUrl={selectedLead.whatsapp_url}
              hasMessenger={Boolean(selectedLead.telegram_url || selectedLead.whatsapp_url)}
            />
          </LeadDetailSection>

          <LeadDetailSection title="Результат enrich" tone="muted">
            <LeadDetailMetaList
              items={[
                { label: 'Provider', value: selectedLead.enrich_payload_json?.provider || '—' },
                {
                  label: 'Found fields',
                  value: Array.isArray(selectedLead.enrich_payload_json?.found_fields) && selectedLead.enrich_payload_json.found_fields.length
                    ? selectedLead.enrich_payload_json.found_fields.join(', ')
                    : '—',
                },
                {
                  label: 'Confidence',
                  value: selectedLead.enrich_payload_json?.confidence && Object.keys(selectedLead.enrich_payload_json.confidence).length
                    ? Object.entries(selectedLead.enrich_payload_json.confidence)
                        .map(([key, value]) => `${key} ${Math.round(Number(value || 0) * 100)}%`)
                        .join(' · ')
                    : '—',
                },
              ]}
            />
          </LeadDetailSection>

          {auditData ? (
            <LeadDetailSection title="Аудит карточки" tone="success">
              <LeadDetailMetaList items={[{ label: 'Услуг в превью', value: (auditData.services_preview || []).length || 0 }]} />
              {(selectedLeadLogo || selectedLeadPhotos.length > 0) ? (
                <div className="space-y-2">
                  {selectedLeadLogo ? (
                    <div>
                      <div className="mb-1 text-xs text-muted-foreground">Логотип</div>
                      <img
                        src={selectedLeadLogo}
                        alt="Логотип лида"
                        className="h-16 w-16 rounded-md border border-gray-200 bg-white object-cover"
                      />
                    </div>
                  ) : null}
                  {selectedLeadPhotos.length > 0 ? (
                    <div>
                      <div className="mb-1 text-xs text-muted-foreground">Фото</div>
                      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                        {selectedLeadPhotos.map((photo, index) => (
                          <img
                            key={`${photo}-${index}`}
                            src={photo}
                            alt={`Фото лида ${index + 1}`}
                            className="h-20 w-full rounded-md border border-gray-200 bg-white object-cover"
                          />
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </LeadDetailSection>
          ) : null}

          {matchData ? (
            <LeadDetailSection title="Матчинг услуг">
              <LeadDetailMetaList
                items={[
                  { label: 'Match score', value: `${matchData.match_score ?? 0}%` },
                  { label: 'Пересечения', value: (matchData.overlap || []).slice(0, 8).join(', ') || '—' },
                  {
                    label: 'Комплементарные направления',
                    value: ((matchData.complement || {}).partner_strength_tokens || []).slice(0, 6).join(', ') || '—',
                  },
                  { label: 'Углы оффера', value: (matchData.offer_angles || []).slice(0, 3).join(' · ') || '—' },
                ]}
              />
              {matchData.score_explanation ? <p className="text-sm text-foreground">{String(matchData.score_explanation)}</p> : null}
              <LeadDetailChipList items={Array.isArray(matchData.reason_codes) ? matchData.reason_codes : []} emptyText="Reason codes пока нет." />
            </LeadDetailSection>
          ) : null}

          {draftText ? (
            <LeadDetailSection title="Первое письмо" tone="info">
              <Textarea value={draftText} rows={8} readOnly />
            </LeadDetailSection>
          ) : null}

          <LeadDetailSection title="Ручное редактирование лида">
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              <Input value={leadEdit.name} onChange={(event) => setLeadEdit((previous) => ({ ...previous, name: event.target.value }))} placeholder="Название" />
              <Input value={leadEdit.category} onChange={(event) => setLeadEdit((previous) => ({ ...previous, category: event.target.value }))} placeholder="Категория" />
              <Input value={leadEdit.city} onChange={(event) => setLeadEdit((previous) => ({ ...previous, city: event.target.value }))} placeholder="Город" />
              <Input value={leadEdit.address} onChange={(event) => setLeadEdit((previous) => ({ ...previous, address: event.target.value }))} placeholder="Адрес" />
              <Input value={leadEdit.phone} onChange={(event) => setLeadEdit((previous) => ({ ...previous, phone: event.target.value }))} placeholder="Телефон" />
              <Input value={leadEdit.email} onChange={(event) => setLeadEdit((previous) => ({ ...previous, email: event.target.value }))} placeholder="Email" />
              <Input value={leadEdit.website} onChange={(event) => setLeadEdit((previous) => ({ ...previous, website: event.target.value }))} placeholder="Сайт" />
              <Input value={leadEdit.telegram_url} onChange={(event) => setLeadEdit((previous) => ({ ...previous, telegram_url: event.target.value }))} placeholder="Telegram URL" />
              <Input value={leadEdit.whatsapp_url} onChange={(event) => setLeadEdit((previous) => ({ ...previous, whatsapp_url: event.target.value }))} placeholder="WhatsApp URL" />
            </div>
            <div className="flex flex-wrap justify-end gap-2">
              <Button variant="outline" onClick={onSaveLeadContacts} disabled={loading}>
                Сохранить данные лида
              </Button>
              <Select
                value={selectedLead.pilot_cohort || 'backlog'}
                onValueChange={(value) => {
                  if (!currentBusinessId) return;
                  void onPilotCohortChange(value);
                }}
              >
                <SelectTrigger className="w-[180px] bg-white">
                  <SelectValue placeholder="Когорта" />
                </SelectTrigger>
                <SelectContent>
                  {pilotCohortOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </LeadDetailSection>
        </DrawerSection>
      </div>
    </div>
  );
}
