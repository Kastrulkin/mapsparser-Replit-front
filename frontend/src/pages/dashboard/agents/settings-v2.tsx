import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { DatahubCatalogList, AgentSourcesList, LearningHistoryPanel, VersionSummary, WizardTextArea } from './workspace';
import { getActiveVersionId, getActiveVersionNumber, getAgentVoiceName } from './model';
import { TimezoneSelect } from './timezone-select';
import { allowedExecutionModes, mapAgentKind, type AgentSettingsDraft, type ExecutionSettingsDraft } from './settings-v2.logic';
import type { AgentBlueprint, AgentBlueprintDetails, AgentReview, AgentSourceCatalogItem, AgentWorkspaceMode, AgentConnectionPlan, AgentIntegrationBindingStatus } from './types';

type SettingsScope = {
  selectedBlueprint: AgentBlueprint; blueprintDetails: AgentBlueprintDetails | null; agentReview: AgentReview | null;
  agentConnectionPlan: AgentConnectionPlan | null; agentBindingStatus: AgentIntegrationBindingStatus[];
  sourceCatalog: AgentSourceCatalogItem[]; actionLoading: boolean; error: string | null;
  selectedExecutionMode: ExecutionSettingsDraft['mode']; scheduleTime: string; scheduleTimezone: string;
  setupDataSources: string; setupExtractionRules: string; setupProcessingRules: string; setupOutputFormat: string; setupManualControl: string;
  saveExecutionMode: (draft?: ExecutionSettingsDraft, stayInSettings?: boolean) => Promise<boolean | undefined>;
  saveAgentSetup: (draft?: AgentSettingsDraft) => Promise<boolean | undefined>;
  addInternalSourceByKey: (key: string) => void; addTextSource: () => void; addFileSource: (file?: File | null) => void;
  sourceName: string; sourceText: string; setSourceName: (value: string) => void; setSourceText: (value: string) => void;
  setWorkspaceMode: (mode: AgentWorkspaceMode) => void; showAdvancedAgentTools: boolean;
  startRun: (blueprint: AgentBlueprint, versionId?: string) => void;
  activateVersion: (id: string, action: string) => void; deleteSelectedAgent: () => void;
};
const modeNames = { manual: 'По кнопке', one_off: 'Один раз', scheduled: 'По расписанию' };
const cardClass = 'space-y-4 rounded-2xl border border-border bg-background p-4 sm:p-5';

export const AgentSettingsPage = ({ scope: s, supportTools, onOpenResult }: { scope: SettingsScope; supportTools: ReactNode; onOpenResult: () => void }) => {
  const root = useRef<HTMLDivElement>(null);
  const kind = mapAgentKind(s.selectedBlueprint);
  const [editing, setEditing] = useState<'launch' | 'data' | 'result' | null>(null);
  const [execution, setExecution] = useState<ExecutionSettingsDraft>({ mode: s.selectedExecutionMode, time: s.scheduleTime, timezone: s.scheduleTimezone });
  const currentSetup = (): AgentSettingsDraft => ({ dataSources: s.setupDataSources, extractionRules: s.setupExtractionRules, processingRules: s.setupProcessingRules, outputFormat: s.setupOutputFormat, manualControl: s.setupManualControl });
  const [draft, setDraft] = useState(currentSetup);
  useEffect(() => {
    if (editing) root.current?.querySelector<HTMLElement>('form input:checked, form textarea, select')?.focus();
  }, [editing]);
  const [saveError, setSaveError] = useState(false);
  const launchButton = useRef<HTMLButtonElement>(null);
  const dataButton = useRef<HTMLButtonElement>(null);
  const resultButton = useRef<HTMLButtonElement>(null);
  const closeEditor = (section: 'launch' | 'data' | 'result') => {
    setEditing(null); setSaveError(false);
    window.requestAnimationFrame(() => (section === 'launch' ? launchButton : section === 'data' ? dataButton : resultButton).current?.focus());
  };
  const [sourceKind, setSourceKind] = useState('localos');
  const latestVersion = getActiveVersionNumber(s.selectedBlueprint, s.blueprintDetails);
  const connectedSources = s.agentReview?.sources || [];
  const hasConnections = Boolean(s.agentConnectionPlan?.items?.length || s.agentBindingStatus?.length);
  const voice = getAgentVoiceName(s.selectedBlueprint, s.blueprintDetails);
  const summaryMode = s.blueprintDetails?.execution_mode || s.selectedBlueprint.execution_mode || s.selectedExecutionMode;
  const executionDirty = execution.mode !== s.selectedExecutionMode || (execution.mode === 'scheduled' && (execution.time !== s.scheduleTime || execution.timezone !== s.scheduleTimezone));
  const errorMessage = saveError ? (s.error || 'Не удалось сохранить изменения. Повторите попытку.') : '';
  return (
    <div ref={root} className="space-y-4" aria-label={`Настройки: ${s.selectedBlueprint.name}`}>
      <header><h2 className="text-xl font-semibold">Настройки агента</h2><p className="mt-1 text-sm text-muted-foreground">{s.selectedBlueprint.name}. Выберите раздел, который нужно изменить.</p></header>
      <section aria-labelledby="agent-settings-launch" className={cardClass}>
        <div className="flex items-start justify-between gap-3"><div><h3 id="agent-settings-launch" className="font-semibold">Когда запускать</h3><p className="mt-1 text-sm text-muted-foreground">{modeNames[summaryMode]}{summaryMode === 'scheduled' ? ` · ${s.scheduleTime} · ${s.scheduleTimezone}` : ''}</p></div>
          {editing === null ? <Button ref={launchButton} variant="outline" aria-label="Изменить способ запуска" onClick={() => { setExecution({ mode: s.selectedExecutionMode, time: s.scheduleTime, timezone: s.scheduleTimezone }); setSaveError(false); setEditing('launch'); }}>Изменить</Button> : null}</div>
        {editing === 'launch' ? <form className="space-y-4" onSubmit={async (event) => { event.preventDefault(); if (!executionDirty) { closeEditor('launch'); return; } const saved = await s.saveExecutionMode(execution, true); if (saved) closeEditor('launch'); else setSaveError(true); }}><fieldset disabled={s.actionLoading} className="space-y-4">
          <fieldset disabled={s.actionLoading}><legend className="mb-2 text-sm font-medium">Способ запуска</legend><div className="flex flex-wrap gap-4">{allowedExecutionModes(s.selectedBlueprint).map((mode) => <label key={mode} className="flex min-h-10 items-center gap-2 text-sm"><input type="radio" name="agent-start-mode" checked={execution.mode === mode} onChange={() => setExecution({ ...execution, mode })} />{modeNames[mode]}</label>)}</div></fieldset>
          {kind === 'preparation' ? <p className="text-sm text-muted-foreground">Первичное оформление запускается вручную. Для регулярного контроля используйте агента проверки карточек.</p> : null}
          {execution.mode === 'scheduled' ? <div className="grid gap-3 sm:grid-cols-2"><label className="text-sm">Время<input autoFocus type="time" required value={execution.time} onChange={(event) => setExecution({ ...execution, time: event.target.value })} className="mt-1 block min-h-10 w-full rounded-md border border-input bg-background px-3" disabled={s.actionLoading} /></label><label className="text-sm">Часовой пояс<TimezoneSelect value={execution.timezone} onChange={(timezone) => setExecution({ ...execution, timezone })} className="mt-1" /></label></div> : null}
          <p className="text-sm text-muted-foreground">Сохранение меняет способ запуска. Проверка и включение агента выполняются отдельно.</p>
          {errorMessage ? <p role="alert" className="text-sm text-destructive">{errorMessage}</p> : null}
          <div className="flex gap-2"><Button type="submit" disabled={s.actionLoading || !executionDirty || !allowedExecutionModes(s.selectedBlueprint).includes(execution.mode)}>{s.actionLoading ? 'Сохраняем…' : 'Сохранить изменения'}</Button><Button type="button" variant="outline" disabled={s.actionLoading} onClick={() => closeEditor('launch')}>Отмена</Button></div>
        </fieldset></form> : null}
      </section>
      <section aria-labelledby="agent-settings-data" className={cardClass}>
        <div className="flex items-start justify-between gap-3"><div><h3 id="agent-settings-data" className="font-semibold">Данные и доступы</h3><p className="mt-1 text-sm text-muted-foreground">{kind ? 'Использует данные компании в LocalOS и сохранённые сведения карточек.' : `Добавленных источников: ${connectedSources.length}.`}</p></div>{!kind && editing === null ? <Button ref={dataButton} variant="outline" aria-label="Изменить источники данных" onClick={() => setEditing('data')}>Изменить</Button> : null}</div>
        {kind ? <><ul className="space-y-2 text-sm"><li><Link className="underline" to="/dashboard/profile">Профиль компании и постоянные знания</Link> — название, адрес, контакты и подтверждённые факты.</li><li><Link className="underline" to="/dashboard/card?tab=services">Услуги и цены</Link> — используются, если заполнены в компании.</li><li><Link className="underline" to="/dashboard/card">Карты и отзывы</Link> — ссылки на Google, Яндекс и 2ГИС и сохранённые сведения.</li>{kind === 'preparation' ? <li><Link className="underline" to="/dashboard/content?section=media">Материалы компании</Link> — фотографии для пакета оформления, если доступны.</li> : null}</ul><p className="text-sm text-muted-foreground">Источники заданы готовым сценарием. Пустые поля не считаются заполненными, а сохранённые сведения не подтверждают текущий внешний вид карточки.</p><div className="flex flex-wrap gap-2"><Button variant="outline" disabled={editing !== null} onClick={onOpenResult}>Посмотреть доступность данных в отчёте</Button><Button variant="outline" disabled={editing !== null} onClick={() => s.setWorkspaceMode('overview')}>Выбрать площадку перед запуском</Button></div></> : <>
          {editing === 'data' ? <div className="space-y-3"><label className="block text-sm">Добавить источник<select autoFocus className="mt-1 block min-h-10 w-full rounded-md border border-input bg-background px-3" value={sourceKind} onChange={(event) => setSourceKind(event.target.value)}><option value="localos">Данные LocalOS</option><option value="text">Текст</option><option value="file">Файл</option></select></label>
            {sourceKind === 'localos' ? <DatahubCatalogList catalog={s.sourceCatalog} actionLoading={s.actionLoading} onConnect={s.addInternalSourceByKey} /> : sourceKind === 'text' ? <div className="space-y-3"><label className="block text-sm">Название<input value={s.sourceName} onChange={(e) => s.setSourceName(e.target.value)} className="mt-1 block min-h-10 w-full rounded-md border border-input px-3" /></label><WizardTextArea label="Содержание источника" value={s.sourceText} onChange={s.setSourceText} placeholder="Подтверждённые сведения для работы агента" /><Button disabled={s.actionLoading || !s.sourceText.trim()} onClick={s.addTextSource}>Добавить текст</Button></div> : <label className="block text-sm">Загрузить файл<input type="file" disabled={s.actionLoading} className="mt-2 block max-w-full" onChange={(event) => { s.addFileSource(event.target.files?.[0]); event.target.value = ''; }} /></label>}
            <Button variant="outline" disabled={s.actionLoading} onClick={() => { s.setSourceName(''); s.setSourceText(''); closeEditor('data'); }}>Готово</Button></div> : <AgentSourcesList sources={connectedSources} compact />}
          {hasConnections ? <Button variant="outline" disabled={editing !== null} onClick={() => s.setWorkspaceMode('connections')}>Настроить необходимые подключения</Button> : <p className="text-sm text-muted-foreground">Дополнительные подключения не указаны в плане этого агента.</p>}
        </>}
      </section>
      <section aria-labelledby="agent-settings-result" className={cardClass}>
        <div className="flex items-start justify-between gap-3"><div><h3 id="agent-settings-result" className="font-semibold">Результат и согласование</h3><p className="mt-1 text-sm text-muted-foreground">{kind === 'preparation' ? 'Пакет оформления и пошаговый мастер переноса на карты.' : kind === 'check' ? 'Отчёт по площадкам: замечания, источники и ограничения проверки.' : s.setupOutputFormat || 'Формат результата задаётся сценарием агента.'}</p></div>{!kind && editing === null ? <Button ref={resultButton} variant="outline" aria-label="Изменить формат результата" onClick={() => { setDraft(currentSetup()); setSaveError(false); setEditing('result'); }}>Изменить</Button> : null}</div>
        {editing === 'result' ? <form className="space-y-3" onSubmit={async (event) => { event.preventDefault(); const saved = await s.saveAgentSetup(draft); if (saved) closeEditor('result'); else setSaveError(true); }}><fieldset disabled={s.actionLoading} className="space-y-4"><WizardTextArea label="Какой результат подготовить" value={draft.outputFormat} onChange={(outputFormat) => setDraft({ ...draft, outputFormat })} placeholder="Например: список замечаний и следующих действий" /><WizardTextArea label="Где нужен ручной контроль" value={draft.manualControl} onChange={(manualControl) => setDraft({ ...draft, manualControl })} placeholder="Перед внешними действиями" /><p className="text-sm text-muted-foreground">Изменения сохранятся как новая версия. Работающая версия не заменяется автоматически.</p>{errorMessage ? <p role="alert" className="text-sm text-destructive">{errorMessage}</p> : null}<div className="flex gap-2"><Button type="submit" disabled={s.actionLoading}>Сохранить изменения</Button><Button type="button" variant="outline" disabled={s.actionLoading} onClick={() => closeEditor('result')}>Отмена</Button></div></fieldset></form> : <><p className="text-sm">{kind === 'preparation' ? 'Google: название, телефон, сайт, описание и услуги можно отправить через мастер при подключении Google Business и после подтверждения правок. Адрес, часы и фото Google, а также Яндекс и 2ГИС — ручной перенос.' : kind === 'check' ? 'Проверка карточек не публикует изменения. Для оформления используйте отдельного агента первичного оформления.' : s.setupManualControl || 'Внешние действия требуют подтверждения человека.'}</p><p className="text-sm text-muted-foreground">{kind ? 'Пример: площадка → что известно → что уточнить → что сделать. Успешный запуск не означает, что карточка оформлена или визуально проверена.' : 'Подробные правила выполнения доступны во вкладке «Сценарий».'}</p><Button variant="outline" disabled={editing !== null} onClick={onOpenResult}>Открыть последний результат</Button></>}
      </section>
      <details className={cardClass}><summary className="min-h-10 cursor-pointer font-semibold">Дополнительно</summary><div className="space-y-4"><p className="text-sm text-muted-foreground">Версии, история изменений и инструменты поддержки. Обычно менять их не требуется.</p>
        <details><summary className="min-h-10 cursor-pointer text-sm font-medium">Версии и история изменений</summary><div className="space-y-3"><VersionSummary versions={s.blueprintDetails?.versions || []} latestVersionNumber={latestVersion} activeVersionId={getActiveVersionId(s.selectedBlueprint, s.blueprintDetails)} onStartVersionRun={(id) => s.startRun(s.selectedBlueprint, id)} onActivateVersion={(id) => s.activateVersion(id, 'activate')} onRollbackVersion={(id) => s.activateVersion(id, 'rollback')} /><LearningHistoryPanel learningEvents={s.blueprintDetails?.learning_events || []} versionEvents={s.blueprintDetails?.version_events || []} legacyMigration={s.blueprintDetails?.legacy_migration || {}} /></div></details>
        {voice ? <Button variant="outline" onClick={() => s.setWorkspaceMode('voice')}>Голос и стиль: {voice}</Button> : null}
        {s.showAdvancedAgentTools ? <Button variant="outline" onClick={() => s.setWorkspaceMode('advanced')}>Диагностика агента</Button> : null}
        {supportTools}
        <Button variant="outline" className="text-destructive" disabled={s.actionLoading} onClick={s.deleteSelectedAgent}>Архивировать агента</Button>
      </div></details>
    </div>
  );
};
