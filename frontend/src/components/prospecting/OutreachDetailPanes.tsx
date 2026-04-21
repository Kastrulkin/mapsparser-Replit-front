import { ReactNode } from 'react';
import { Button } from '@/components/ui/button';
import { ContactPresenceBadges, StatusSummaryCard, WorkflowActionRow } from '@/components/prospecting/LeadWorkflowBlocks';
import {
  ChannelWarning,
  FollowUpEditor,
  LeadDetailPane,
  LeadStatusBadge,
  ReviewChecklist,
  SendReviewPanel,
} from '@/components/prospecting/OutreachWorkspaceBlocks';

type LeadContactShape = {
  id?: string;
  website?: string;
  phone?: string;
  email?: string;
  telegram_url?: string;
  whatsapp_url?: string;
};

type DetailAction = {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  variant?: 'default' | 'outline' | 'ghost' | 'destructive' | 'secondary';
};

type DetailChecklistItem = {
  id: string;
  label: string;
  checked: boolean;
  hint?: string;
};

type DetailHistoryRow = {
  label: string;
  value: string;
};

type DetailTone = 'default' | 'success' | 'warning' | 'danger' | 'info';

type DraftDetailPaneProps = {
  title?: string;
  description: string;
  statusLabel?: string;
  statusTone?: 'default' | 'success' | 'warning' | 'danger';
  warning?: string;
  canOpenLeadCard: boolean;
  onOpenLeadCard: () => void;
  onFixChannel: () => void;
  leadContacts?: LeadContactShape | null;
  hasMessenger: boolean;
  selectedChannelLabel: string;
  selectedChannelValue: string;
  selectedChannelTone: DetailTone;
  auditStatusLabel: string;
  auditPrimaryText: string;
  auditSecondaryText: string;
  auditTone: DetailTone;
  channelSelector?: ReactNode;
  auditLinks?: ReactNode;
  primaryAction?: DetailAction;
  secondaryActions?: DetailAction[];
  editorValue: string;
  onEditorChange: (value: string) => void;
  reviewDescription: string;
  checklistItems: DetailChecklistItem[];
  historyRows: DetailHistoryRow[];
};

type QueueDetailPaneProps = {
  title?: string;
  description: string;
  statusLabel?: string;
  statusTone?: DetailTone;
  warning?: string;
  canOpenLeadCard: boolean;
  onOpenLeadCard: () => void;
  onFixChannel?: () => void;
  leadContacts?: LeadContactShape | null;
  hasMessenger: boolean;
  channelStatusLabel: string;
  channelPrimaryText: string;
  channelSecondaryText: string;
  channelTone: DetailTone;
  queueStatusLabel: string;
  queuePrimaryText: string;
  queueSecondaryText: string;
  queueTone: DetailTone;
  topErrorSummary?: ReactNode;
  contextLinks?: ReactNode;
  primaryAction?: DetailAction;
  secondaryActions?: DetailAction[];
  message: string;
  reviewDescription: string;
  checklistItems: DetailChecklistItem[];
  reviewActions?: ReactNode;
  noteValue: string;
  onNoteChange: (value: string) => void;
  noteHint: string;
  historyRows: DetailHistoryRow[];
};

type SentDetailPaneProps = {
  title?: string;
  description: string;
  statusLabel?: string;
  statusTone?: DetailTone;
  warning?: string;
  canOpenLeadCard: boolean;
  onOpenLeadCard: () => void;
  onFixChannel?: () => void;
  leadContacts?: LeadContactShape | null;
  hasMessenger: boolean;
  channelStatusLabel: string;
  channelPrimaryText: string;
  channelSecondaryText: string;
  channelTone: DetailTone;
  responseStatusLabel: string;
  responsePrimaryText: string;
  responseSecondaryText: string;
  responseTone: DetailTone;
  contextLinks?: ReactNode;
  primaryAction?: DetailAction;
  secondaryActions?: DetailAction[];
  editorValue: string;
  onEditorChange: (value: string) => void;
  reviewDescription: string;
  checklistItems: DetailChecklistItem[];
  historyRows: DetailHistoryRow[];
  rawReply?: string;
};

const toWorkflowAction = (action?: DetailAction) =>
  action
    ? {
        label: action.label,
        onClick: action.onClick,
        disabled: action.disabled,
        variant: action.variant,
      }
    : null;

const toWorkflowActions = (actions?: DetailAction[]) =>
  (actions || []).map((action) => ({
    label: action.label,
    onClick: action.onClick,
    disabled: action.disabled,
    variant: action.variant,
  }));

const DetailContextSection = ({ children }: { children: ReactNode }) => (
  <div className="rounded-xl border p-4">
    <div className="text-sm font-semibold">Ссылки и контекст</div>
    <div className="mt-3 flex flex-wrap gap-2">{children}</div>
  </div>
);

const DetailHistorySection = ({
  title,
  rows,
  trailingContent,
}: {
  title: string;
  rows: DetailHistoryRow[];
  trailingContent?: ReactNode;
}) => (
  <div className="rounded-xl border p-4">
    <div className="text-sm font-semibold">{title}</div>
    <div className="mt-3 space-y-2 text-sm text-muted-foreground">
      {rows.map((row) => (
        <div key={row.label}>{row.label}: {row.value}</div>
      ))}
      {trailingContent}
    </div>
  </div>
);

const DetailWarningActions = ({
  canOpenLeadCard,
  onOpenLeadCard,
  onFixChannel,
}: {
  canOpenLeadCard: boolean;
  onOpenLeadCard: () => void;
  onFixChannel?: () => void;
}) => (
  <div className="flex flex-wrap gap-2">
    {onFixChannel ? <Button size="sm" onClick={onFixChannel}>Сменить канал</Button> : null}
    <Button size="sm" variant="outline" onClick={onOpenLeadCard} disabled={!canOpenLeadCard}>Открыть карточку лида</Button>
  </div>
);

const DetailStatusCards = ({
  leftTitle,
  leftStatusLabel,
  leftPrimaryText,
  leftSecondaryText,
  leftTone,
  rightTitle,
  rightStatusLabel,
  rightPrimaryText,
  rightSecondaryText,
  rightTone,
}: {
  leftTitle: string;
  leftStatusLabel: string;
  leftPrimaryText: string;
  leftSecondaryText: string;
  leftTone: DetailTone;
  rightTitle: string;
  rightStatusLabel: string;
  rightPrimaryText: string;
  rightSecondaryText: string;
  rightTone: DetailTone;
}) => (
  <div className="grid gap-3 md:grid-cols-2">
    <StatusSummaryCard
      title={leftTitle}
      statusLabel={leftStatusLabel}
      primaryText={leftPrimaryText}
      secondaryText={leftSecondaryText}
      tone={leftTone}
    />
    <StatusSummaryCard
      title={rightTitle}
      statusLabel={rightStatusLabel}
      primaryText={rightPrimaryText}
      secondaryText={rightSecondaryText}
      tone={rightTone}
    />
  </div>
);

export function DraftDetailPanel(props: DraftDetailPaneProps) {
  const primary = toWorkflowAction(props.primaryAction);
  const secondary = toWorkflowActions(props.secondaryActions);

  return (
    <LeadDetailPane
      title={props.title}
      description={props.description}
      statusBadge={props.statusLabel ? <LeadStatusBadge label={props.statusLabel} tone={props.statusTone} /> : null}
      warning={props.warning ? (
        <ChannelWarning
          description={props.warning}
          action={<DetailWarningActions canOpenLeadCard={props.canOpenLeadCard} onOpenLeadCard={props.onOpenLeadCard} onFixChannel={props.onFixChannel} />}
        />
      ) : null}
      topMeta={props.leadContacts ? (
        <>
          <ContactPresenceBadges
            title="Доступные каналы"
            website={props.leadContacts.website}
            phone={props.leadContacts.phone}
            email={props.leadContacts.email}
            telegramUrl={props.leadContacts.telegram_url}
            whatsappUrl={props.leadContacts.whatsapp_url}
            hasMessenger={props.hasMessenger}
          />
          <DetailStatusCards
            leftTitle="Выбранный канал"
            leftStatusLabel={props.selectedChannelLabel}
            leftPrimaryText={props.selectedChannelValue}
            leftSecondaryText="Проверьте контакт до отправки или смените канал прямо здесь."
            leftTone={props.selectedChannelTone}
            rightTitle="Аудит"
            rightStatusLabel={props.auditStatusLabel}
            rightPrimaryText={props.auditPrimaryText}
            rightSecondaryText={props.auditSecondaryText}
            rightTone={props.auditTone}
          />
        </>
      ) : null}
      channelSection={
        props.channelSelector || props.auditLinks ? (
          <div className="rounded-xl border p-4">
            <div className="text-sm font-semibold">Канал и контекст</div>
            {props.channelSelector ? <div className="mt-3">{props.channelSelector}</div> : null}
            {props.auditLinks ? <div className="mt-3 flex flex-wrap gap-2">{props.auditLinks}</div> : null}
          </div>
        ) : null
      }
      actions={primary ? <WorkflowActionRow primary={primary} secondary={secondary} /> : null}
      editor={
        <FollowUpEditor
          label="Текст сообщения"
          value={props.editorValue}
          onChange={props.onEditorChange}
          hint="Сначала проверьте тон и канал, потом утвердите сообщение."
        />
      }
      review={
        <div className="space-y-3">
          <ReviewChecklist items={props.checklistItems} />
          <SendReviewPanel
            title="Проверка перед следующим шагом"
            description={props.reviewDescription}
            message={props.editorValue}
          />
        </div>
      }
      history={
        <DetailHistorySection title="Короткая история" rows={props.historyRows} />
      }
    />
  );
}

export function QueueDetailPanel(props: QueueDetailPaneProps) {
  const primary = toWorkflowAction(props.primaryAction);
  const secondary = toWorkflowActions(props.secondaryActions);

  return (
    <LeadDetailPane
      title={props.title}
      description={props.description}
      statusBadge={props.statusLabel ? <LeadStatusBadge label={props.statusLabel} tone={props.statusTone} /> : null}
      warning={props.warning ? (
        <ChannelWarning
          description={props.warning}
          action={<DetailWarningActions canOpenLeadCard={props.canOpenLeadCard} onOpenLeadCard={props.onOpenLeadCard} onFixChannel={props.onFixChannel} />}
        />
      ) : null}
      errorSummary={props.topErrorSummary}
      topMeta={props.leadContacts ? (
        <>
          <ContactPresenceBadges
            title="Доступные каналы"
            website={props.leadContacts.website}
            phone={props.leadContacts.phone}
            email={props.leadContacts.email}
            telegramUrl={props.leadContacts.telegram_url}
            whatsappUrl={props.leadContacts.whatsapp_url}
            hasMessenger={props.hasMessenger}
          />
          <DetailStatusCards
            leftTitle="Канал"
            leftStatusLabel={props.channelStatusLabel}
            leftPrimaryText={props.channelPrimaryText}
            leftSecondaryText={props.channelSecondaryText}
            leftTone={props.channelTone}
            rightTitle="Статус отправки"
            rightStatusLabel={props.queueStatusLabel}
            rightPrimaryText={props.queuePrimaryText}
            rightSecondaryText={props.queueSecondaryText}
            rightTone={props.queueTone}
          />
        </>
      ) : null}
      channelSection={
        props.contextLinks ? (
          <DetailContextSection>{props.contextLinks}</DetailContextSection>
        ) : null
      }
      actions={primary ? <WorkflowActionRow primary={primary} secondary={secondary} /> : null}
      review={
        <div className="space-y-3">
          <ReviewChecklist items={props.checklistItems} />
          <SendReviewPanel
            title="Проверка перед действием"
            description={props.reviewDescription}
            message={props.message}
          >
            {props.reviewActions}
          </SendReviewPanel>
        </div>
      }
      editor={
        <FollowUpEditor
          label="Ответ клиента / заметка"
          value={props.noteValue}
          onChange={props.onNoteChange}
          hint={props.noteHint}
        />
      }
      history={
        <DetailHistorySection title="История" rows={props.historyRows} />
      }
    />
  );
}

export function SentDetailPanel(props: SentDetailPaneProps) {
  const primary = toWorkflowAction(props.primaryAction);
  const secondary = toWorkflowActions(props.secondaryActions);

  return (
    <LeadDetailPane
      title={props.title}
      description={props.description}
      statusBadge={props.statusLabel ? <LeadStatusBadge label={props.statusLabel} tone={props.statusTone} /> : null}
      warning={props.warning ? (
        <ChannelWarning
          description={props.warning}
          action={<DetailWarningActions canOpenLeadCard={props.canOpenLeadCard} onOpenLeadCard={props.onOpenLeadCard} onFixChannel={props.onFixChannel} />}
        />
      ) : null}
      topMeta={props.leadContacts ? (
        <>
          <ContactPresenceBadges
            title="Доступные каналы"
            website={props.leadContacts.website}
            phone={props.leadContacts.phone}
            email={props.leadContacts.email}
            telegramUrl={props.leadContacts.telegram_url}
            whatsappUrl={props.leadContacts.whatsapp_url}
            hasMessenger={props.hasMessenger}
          />
          <DetailStatusCards
            leftTitle="Выбранный канал"
            leftStatusLabel={props.channelStatusLabel}
            leftPrimaryText={props.channelPrimaryText}
            leftSecondaryText={props.channelSecondaryText}
            leftTone={props.channelTone}
            rightTitle="Ответ"
            rightStatusLabel={props.responseStatusLabel}
            rightPrimaryText={props.responsePrimaryText}
            rightSecondaryText={props.responseSecondaryText}
            rightTone={props.responseTone}
          />
        </>
      ) : null}
      channelSection={
        props.contextLinks ? (
          <DetailContextSection>{props.contextLinks}</DetailContextSection>
        ) : null
      }
      actions={primary ? <WorkflowActionRow primary={primary} secondary={secondary} /> : null}
      editor={
        <FollowUpEditor
          label="Follow-up сообщение"
          value={props.editorValue}
          onChange={props.onEditorChange}
          hint="Редактирование follow-up держим в одном рабочем месте."
        />
      }
      review={
        <div className="space-y-3">
          <ReviewChecklist title="Проверка перед follow-up" items={props.checklistItems} />
          <SendReviewPanel
            title="Проверка follow-up"
            description={props.reviewDescription}
            message={props.editorValue}
          />
        </div>
      }
      history={
        <DetailHistorySection
          title="Компактная история"
          rows={props.historyRows}
          trailingContent={props.rawReply ? <div className="whitespace-pre-wrap text-slate-900">{props.rawReply}</div> : null}
        />
      }
    />
  );
}
