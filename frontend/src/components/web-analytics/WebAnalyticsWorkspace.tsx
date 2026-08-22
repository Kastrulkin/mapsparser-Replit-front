import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clipboard,
  Code2,
  KeyRound,
  Megaphone,
  Plus,
  RefreshCw,
  Target,
  Trash2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { newAuth } from "@/lib/auth_new";
import { cn } from "@/lib/utils";

type WorkspaceMode = "setup" | "changes" | "integration";
type PageGroup = {
  id: string;
  name: string;
  group_type: string;
  match_type: string;
  include_patterns: string[];
  exclude_patterns: string[];
  status: string;
  matched_paths: number;
  matched_sessions: number;
};
type Goal = {
  id: string;
  name: string;
  goal_type: string;
  matcher: Record<string, string>;
  status: string;
  count: number;
};
type Annotation = {
  id: string;
  occurred_at: string;
  change_type: string;
  title: string;
  description: string;
  page_path: string;
  expected_impact: string;
  source?: string;
};
type CampaignCost = {
  id: string;
  source: string;
  campaign: string;
  content?: string;
  period_start: string;
  period_end: string;
  cost: number | string;
  currency: string;
};
type Configuration = {
  page_groups: PageGroup[];
  goals: Goal[];
  annotations: Annotation[];
  campaign_costs: CampaignCost[];
  conversion_key: { configured: boolean; created_at?: string | null };
};
type Preview = {
  matched_paths: number;
  matched_sessions: number;
  available_paths: number;
  sample: Array<{ path: string; title?: string | null; sessions: number }>;
};

const fieldClass =
  "min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none transition-[border-color,box-shadow] duration-150 focus:border-slate-400 focus:ring-2 focus:ring-slate-200";

const statusCopy: Record<string, { label: string; className: string }> = {
  draft: {
    label: "Черновик",
    className: "bg-amber-50 text-amber-800 ring-amber-200",
  },
  configured: {
    label: "Настроено",
    className: "bg-blue-50 text-blue-800 ring-blue-200",
  },
  receiving: {
    label: "Получает данные",
    className: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  },
  no_data: {
    label: "Данные не обнаружены",
    className: "bg-slate-100 text-slate-700 ring-slate-200",
  },
  disabled: {
    label: "Отключено",
    className: "bg-slate-100 text-slate-500 ring-slate-200",
  },
};

const StatusBadge = ({ status }: { status: string }) => {
  const item = statusCopy[status] || statusCopy.configured;
  return (
    <span
      className={cn(
        "inline-flex min-h-7 items-center rounded-lg px-2 text-xs font-semibold ring-1",
        item.className,
      )}
    >
      {item.label}
    </span>
  );
};

const EmptyStart = ({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action: ReactNode;
}) => (
  <div className="rounded-2xl bg-slate-50 px-5 py-8 text-center shadow-[inset_0_0_0_1px_rgba(15,23,42,0.06)]">
    <Target className="mx-auto h-8 w-8 text-slate-400" />
    <h3 className="mt-3 text-balance text-base font-semibold text-slate-900">
      {title}
    </h3>
    <p className="mx-auto mt-2 max-w-lg text-pretty text-sm leading-6 text-slate-600">
      {description}
    </p>
    <div className="mt-4">{action}</div>
  </div>
);

export const WebAnalyticsWorkspace = ({
  businessId,
  mode,
  onChanged,
}: {
  businessId: string;
  mode: WorkspaceMode;
  onChanged: () => void;
}) => {
  const [configuration, setConfiguration] = useState<Configuration | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [groupOpen, setGroupOpen] = useState(false);
  const [goalOpen, setGoalOpen] = useState(false);
  const [annotationOpen, setAnnotationOpen] = useState(false);
  const [costOpen, setCostOpen] = useState(false);
  const [groupName, setGroupName] = useState("");
  const [groupType, setGroupType] = useState("service");
  const [matchType, setMatchType] = useState("prefix");
  const [includes, setIncludes] = useState("");
  const [excludes, setExcludes] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [goalName, setGoalName] = useState("");
  const [goalType, setGoalType] = useState("page_view");
  const [goalMatcher, setGoalMatcher] = useState("");
  const [annotationType, setAnnotationType] = useState("page");
  const [annotationTitle, setAnnotationTitle] = useState("");
  const [annotationDescription, setAnnotationDescription] = useState("");
  const [annotationPath, setAnnotationPath] = useState("");
  const [annotationImpact, setAnnotationImpact] = useState("");
  const [costSource, setCostSource] = useState("");
  const [costCampaign, setCostCampaign] = useState("");
  const [costContent, setCostContent] = useState("");
  const [costMedium, setCostMedium] = useState("");
  const [costTerm, setCostTerm] = useState("");
  const [costValue, setCostValue] = useState("");
  const [costCurrency, setCostCurrency] = useState("RUB");
  const [costStart, setCostStart] = useState("");
  const [costEnd, setCostEnd] = useState("");
  const [revealedKey, setRevealedKey] = useState("");
  const [copied, setCopied] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<{
    endpoint: string;
    label: string;
  } | null>(null);
  const [keyConfirmOpen, setKeyConfirmOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await newAuth.makeRequest(
        `/business/${businessId}/web-analytics/configuration`,
      );
      setConfiguration(response);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Не удалось загрузить настройки аналитики",
      );
    } finally {
      setLoading(false);
    }
  }, [businessId]);

  useEffect(() => {
    void load();
  }, [load]);

  const groupPayload = useMemo(
    () => ({
      name: groupName,
      group_type: groupType,
      match_type: matchType,
      include_patterns: includes
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean),
      exclude_patterns: excludes
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean),
    }),
    [excludes, groupName, groupType, includes, matchType],
  );

  const runPreview = async () => {
    setSaving(true);
    setError("");
    try {
      const response = await newAuth.makeRequest(
        `/business/${businessId}/web-page-groups/preview`,
        {
          method: "POST",
          body: JSON.stringify(groupPayload),
        },
      );
      setPreview(response.preview || null);
    } catch (previewError) {
      setError(
        previewError instanceof Error
          ? previewError.message
          : "Не удалось проверить правило",
      );
    } finally {
      setSaving(false);
    }
  };

  const saveGroup = async () => {
    setSaving(true);
    setError("");
    try {
      await newAuth.makeRequest(`/business/${businessId}/web-page-groups`, {
        method: "POST",
        body: JSON.stringify(groupPayload),
      });
      setGroupOpen(false);
      setPreview(null);
      setGroupName("");
      setIncludes("");
      setExcludes("");
      await load();
      onChanged();
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "Не удалось сохранить группу",
      );
    } finally {
      setSaving(false);
    }
  };

  const saveGoal = async () => {
    const matcherKey =
      goalType === "page_view"
        ? "page_group_id"
        : goalType === "section_view"
          ? "section_key"
          : goalType === "cta_click"
            ? "cta_id"
            : goalType === "form_submit"
              ? "form_id"
              : "";
    setSaving(true);
    setError("");
    try {
      await newAuth.makeRequest(`/business/${businessId}/web-goals`, {
        method: "POST",
        body: JSON.stringify({
          name: goalName,
          goal_type: goalType,
          matcher: matcherKey ? { [matcherKey]: goalMatcher } : {},
        }),
      });
      setGoalOpen(false);
      setGoalName("");
      setGoalMatcher("");
      await load();
      onChanged();
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "Не удалось сохранить цель",
      );
    } finally {
      setSaving(false);
    }
  };

  const remove = async (endpoint: string) => {
    setError("");
    try {
      await newAuth.makeRequest(endpoint, { method: "DELETE" });
      await load();
      onChanged();
    } catch (removeError) {
      setError(
        removeError instanceof Error
          ? removeError.message
          : "Не удалось удалить запись",
      );
    }
  };

  const saveAnnotation = async () => {
    setSaving(true);
    try {
      await newAuth.makeRequest(
        `/business/${businessId}/web-change-annotations`,
        {
          method: "POST",
          body: JSON.stringify({
            change_type: annotationType,
            title: annotationTitle,
            description: annotationDescription,
            page_path: annotationPath,
            expected_impact: annotationImpact,
            occurred_at: new Date().toISOString(),
          }),
        },
      );
      setAnnotationOpen(false);
      setAnnotationTitle("");
      setAnnotationDescription("");
      setAnnotationPath("");
      setAnnotationImpact("");
      await load();
      onChanged();
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "Не удалось записать изменение",
      );
    } finally {
      setSaving(false);
    }
  };

  const saveCost = async () => {
    setSaving(true);
    try {
      await newAuth.makeRequest(`/business/${businessId}/web-campaign-costs`, {
        method: "POST",
        body: JSON.stringify({
          source: costSource,
          medium: costMedium,
          campaign: costCampaign,
          content: costContent,
          term: costTerm,
          cost: costValue,
          currency: costCurrency,
          period_start: costStart,
          period_end: costEnd,
        }),
      });
      setCostOpen(false);
      setCostSource("");
      setCostCampaign("");
      setCostContent("");
      setCostMedium("");
      setCostTerm("");
      setCostValue("");
      await load();
      onChanged();
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "Не удалось сохранить расходы",
      );
    } finally {
      setSaving(false);
    }
  };

  const rotateKey = async () => {
    setSaving(true);
    setError("");
    try {
      const response = await newAuth.makeRequest(
        `/business/${businessId}/web-conversion-key`,
        { method: "POST" },
      );
      setRevealedKey(response.conversion_key?.key || "");
      await load();
    } catch (keyError) {
      setError(
        keyError instanceof Error
          ? keyError.message
          : "Не удалось создать ключ",
      );
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    await remove(pendingDelete.endpoint);
    setPendingDelete(null);
  };

  const copyKey = async () => {
    if (!revealedKey) return;
    await navigator.clipboard.writeText(revealedKey);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  };

  if (loading)
    return (
      <div className="flex min-h-56 items-center justify-center text-sm text-slate-500">
        <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
        Загружаем настройки…
      </div>
    );

  const alert = error ? (
    <div
      role="alert"
      className="mb-4 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-800 ring-1 ring-rose-200"
    >
      {error}
    </div>
  ) : null;

  if (mode === "setup") {
    return (
      <div className="space-y-6">
        {alert}
        <section className="rounded-3xl bg-white p-5 shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_1px_2px_-1px_rgba(15,23,42,0.06),0_6px_20px_rgba(15,23,42,0.04)] sm:p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-balance text-lg font-semibold text-slate-950">
                1. Объедините страницы по смыслу
              </h2>
              <p className="mt-1 text-pretty text-sm leading-6 text-slate-600">
                Задайте страницы услуг, цен и контактов. Перед сохранением
                LocalOS покажет, какие URL попадут в группу.
              </p>
            </div>
            <Button
              onClick={() => setGroupOpen(true)}
              className="min-h-11 shrink-0 transition-transform active:scale-[0.96]"
            >
              <Plus />
              Добавить группу
            </Button>
          </div>
          <div className="mt-5 space-y-2">
            {configuration?.page_groups?.map((group) => (
              <div
                key={group.id}
                className="flex flex-col gap-3 rounded-2xl bg-slate-50 px-4 py-3 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.06)] sm:flex-row sm:items-center"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-slate-900">
                      {group.name}
                    </span>
                    <StatusBadge status={group.status} />
                  </div>
                  <div className="mt-1 text-sm text-slate-500 tabular-nums">
                    {group.matched_paths} страниц · {group.matched_sessions}{" "}
                    сессий за 30 дней
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Удалить группу ${group.name}`}
                  className="min-h-10 min-w-10 self-end text-slate-400 hover:text-rose-700 sm:self-auto"
                  onClick={() =>
                    void remove(
                      `/business/${businessId}/web-page-groups/${group.id}`,
                    )
                  }
                >
                  <Trash2 />
                </Button>
              </div>
            ))}
            {!configuration?.page_groups?.length ? (
              <EmptyStart
                title="Сначала создайте группу страниц"
                description="Например, объедините все страницы услуг, чтобы увидеть переход от услуги к цене и заявке."
                action={
                  <Button variant="outline" onClick={() => setGroupOpen(true)}>
                    Создать первую группу
                  </Button>
                }
              />
            ) : null}
          </div>
        </section>

        <section className="rounded-3xl bg-white p-5 shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_1px_2px_-1px_rgba(15,23,42,0.06),0_6px_20px_rgba(15,23,42,0.04)] sm:p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-balance text-lg font-semibold text-slate-950">
                2. Укажите, что считать результатом
              </h2>
              <p className="mt-1 text-pretty text-sm leading-6 text-slate-600">
                Цель может быть просмотром важной страницы, кнопкой, успешной
                формой или подтверждённой записью.
              </p>
            </div>
            <Button
              onClick={() => setGoalOpen(true)}
              className="min-h-11 shrink-0 transition-transform active:scale-[0.96]"
              disabled={!configuration?.page_groups?.length}
            >
              <Plus />
              Добавить цель
            </Button>
          </div>
          <div className="mt-5 space-y-2">
            {configuration?.goals?.map((goal) => (
              <div
                key={goal.id}
                className="flex flex-col gap-3 rounded-2xl bg-slate-50 px-4 py-3 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.06)] sm:flex-row sm:items-center"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-slate-900">
                      {goal.name}
                    </span>
                    <StatusBadge status={goal.status} />
                  </div>
                  <div className="mt-1 text-sm text-slate-500 tabular-nums">
                    Срабатываний: {goal.count || 0}
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Удалить цель ${goal.name}`}
                  className="min-h-10 min-w-10 self-end text-slate-400 hover:text-rose-700 sm:self-auto"
                  onClick={() =>
                    setPendingDelete({
                      endpoint: `/business/${businessId}/web-goals/${goal.id}`,
                      label: `цель «${goal.name}»`,
                    })
                  }
                >
                  <Trash2 />
                </Button>
              </div>
            ))}
            {!configuration?.goals?.length ? (
              <EmptyStart
                title="Цели ещё не настроены"
                description="После первой цели LocalOS построит воронку и начнёт показывать, на каком шаге теряются посетители."
                action={
                  <Button
                    variant="outline"
                    onClick={() => setGoalOpen(true)}
                    disabled={!configuration?.page_groups?.length}
                  >
                    Настроить цель
                  </Button>
                }
              />
            ) : null}
          </div>
        </section>

        <Dialog open={groupOpen} onOpenChange={setGroupOpen}>
          <DialogContent className="max-w-2xl rounded-3xl">
            <DialogHeader>
              <DialogTitle className="text-balance">
                Новая группа страниц
              </DialogTitle>
              <DialogDescription className="text-pretty">
                Укажите правило и проверьте его на уже накопленных URL до
                сохранения.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-2 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <Label htmlFor="group-name">Название</Label>
                <Input
                  id="group-name"
                  className="mt-2 min-h-11"
                  value={groupName}
                  onChange={(event) => setGroupName(event.target.value)}
                  placeholder="Страницы услуг"
                />
              </div>
              <div>
                <Label htmlFor="group-type">Назначение</Label>
                <select
                  id="group-type"
                  className={cn(fieldClass, "mt-2")}
                  value={groupType}
                  onChange={(event) => setGroupType(event.target.value)}
                >
                  <option value="service">Услуги</option>
                  <option value="pricing">Цены</option>
                  <option value="contact">Контакты</option>
                  <option value="success">Успешная заявка</option>
                  <option value="custom">Другое</option>
                </select>
              </div>
              <div>
                <Label htmlFor="match-type">Как сравнивать URL</Label>
                <select
                  id="match-type"
                  className={cn(fieldClass, "mt-2")}
                  value={matchType}
                  onChange={(event) => setMatchType(event.target.value)}
                >
                  <option value="prefix">Начинается с</option>
                  <option value="exact">Точное совпадение</option>
                  <option value="contains">Содержит</option>
                  <option value="list">Список URL</option>
                </select>
              </div>
              <div>
                <Label htmlFor="includes">URL — по одному на строку</Label>
                <Textarea
                  id="includes"
                  className="mt-2 min-h-28"
                  value={includes}
                  onChange={(event) => setIncludes(event.target.value)}
                  placeholder={"/services\n/haircuts"}
                />
              </div>
              <div>
                <Label htmlFor="excludes">Исключения</Label>
                <Textarea
                  id="excludes"
                  className="mt-2 min-h-28"
                  value={excludes}
                  onChange={(event) => setExcludes(event.target.value)}
                  placeholder={"/services/archive"}
                />
              </div>
            </div>
            {preview ? (
              <div className="rounded-2xl bg-emerald-50 p-4 ring-1 ring-emerald-200">
                <div className="flex items-center gap-2 font-semibold text-emerald-900">
                  <CheckCircle2 className="h-4 w-4" />
                  Найдено {preview.matched_paths} из {preview.available_paths}{" "}
                  страниц
                </div>
                <div className="mt-2 space-y-1 text-sm text-emerald-800">
                  {preview.sample.slice(0, 5).map((item) => (
                    <div key={item.path} className="truncate">
                      {item.path} · {item.sessions} сессий
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
            <DialogFooter className="gap-2">
              <Button
                variant="outline"
                onClick={() => void runPreview()}
                disabled={saving || !groupName || !includes}
              >
                {saving ? <RefreshCw className="animate-spin" /> : null}
                Проверить правило
              </Button>
              <Button
                onClick={() => void saveGroup()}
                disabled={saving || !preview}
              >
                Сохранить группу
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <Dialog open={goalOpen} onOpenChange={setGoalOpen}>
          <DialogContent className="rounded-3xl">
            <DialogHeader>
              <DialogTitle>Новая цель</DialogTitle>
              <DialogDescription>
                Выберите результат и укажите его постоянный идентификатор.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div>
                <Label htmlFor="goal-name">Понятное название</Label>
                <Input
                  id="goal-name"
                  className="mt-2 min-h-11"
                  value={goalName}
                  onChange={(event) => setGoalName(event.target.value)}
                  placeholder="Запись после просмотра цен"
                />
              </div>
              <div>
                <Label htmlFor="goal-type">Событие</Label>
                <select
                  id="goal-type"
                  className={cn(fieldClass, "mt-2")}
                  value={goalType}
                  onChange={(event) => {
                    setGoalType(event.target.value);
                    setGoalMatcher("");
                  }}
                >
                  <option value="page_view">Просмотр группы страниц</option>
                  <option value="section_view">Просмотр секции</option>
                  <option value="cta_click">Нажатие кнопки</option>
                  <option value="form_submit">Успешная форма</option>
                  <option value="booking_click">Переход к записи</option>
                  <option value="lead_created">Подтверждённая заявка</option>
                  <option value="message_lead">Заявка из мессенджера</option>
                  <option value="call_answered">Принятый звонок</option>
                  <option value="call_qualified">Целевой звонок</option>
                  <option value="booking_confirmed">
                    Подтверждённая запись
                  </option>
                  <option value="payment_completed">Оплата</option>
                </select>
              </div>
              {goalType === "page_view" ? (
                <div>
                  <Label htmlFor="goal-matcher">Группа страниц</Label>
                  <select
                    id="goal-matcher"
                    className={cn(fieldClass, "mt-2")}
                    value={goalMatcher}
                    onChange={(event) => setGoalMatcher(event.target.value)}
                  >
                    <option value="">Выберите группу</option>
                    {configuration?.page_groups?.map((group) => (
                      <option key={group.id} value={group.id}>
                        {group.name}
                      </option>
                    ))}
                  </select>
                </div>
              ) : ["section_view", "cta_click", "form_submit"].includes(
                  goalType,
                ) ? (
                <div>
                  <Label htmlFor="goal-matcher">Постоянный ID</Label>
                  <Input
                    id="goal-matcher"
                    className="mt-2 min-h-11"
                    value={goalMatcher}
                    onChange={(event) => setGoalMatcher(event.target.value)}
                    placeholder={
                      goalType === "cta_click"
                        ? "booking_hero"
                        : goalType === "form_submit"
                          ? "main_booking"
                          : "prices"
                    }
                  />
                </div>
              ) : null}
            </div>
            <DialogFooter>
              <Button
                onClick={() => void saveGoal()}
                disabled={
                  saving ||
                  !goalName ||
                  ([
                    "page_view",
                    "section_view",
                    "cta_click",
                    "form_submit",
                  ].includes(goalType) &&
                    !goalMatcher)
                }
              >
                {saving ? <RefreshCw className="animate-spin" /> : null}
                Сохранить цель
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        <AlertDialog
          open={Boolean(pendingDelete)}
          onOpenChange={(open) => {
            if (!open) setPendingDelete(null);
          }}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>
                Удалить {pendingDelete?.label}?
              </AlertDialogTitle>
              <AlertDialogDescription>
                Исторические события останутся, но эта настройка исчезнет из
                будущих отчётов.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Отмена</AlertDialogCancel>
              <AlertDialogAction
                onClick={() => void confirmDelete()}
                className="bg-rose-700 hover:bg-rose-800"
              >
                Удалить
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    );
  }

  if (mode === "changes") {
    return (
      <div className="space-y-5">
        {alert}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-balance text-xl font-semibold text-slate-950">
              Что менялось на сайте
            </h2>
            <p className="mt-1 text-pretty text-sm leading-6 text-slate-600">
              Отметки объясняют рост и падение показателей. Добавляйте цены,
              заголовки, формы, кампании и технические сбои.
            </p>
          </div>
          <Button
            onClick={() => setAnnotationOpen(true)}
            className="min-h-11 shrink-0 transition-transform active:scale-[0.96]"
          >
            <Plus />
            Записать изменение
          </Button>
        </div>
        <div className="relative space-y-3 before:absolute before:bottom-4 before:left-5 before:top-4 before:w-px before:bg-slate-200">
          {configuration?.annotations?.map((item) => (
            <div
              key={item.id}
              className="relative ml-10 rounded-2xl bg-white p-4 shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_1px_2px_-1px_rgba(15,23,42,0.06)]"
            >
              <span className="absolute -left-[27px] top-5 h-3 w-3 rounded-full bg-slate-900 ring-4 ring-slate-100" />
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
                    {new Date(item.occurred_at).toLocaleString("ru-RU")}
                  </div>
                  <h3 className="mt-1 font-semibold text-slate-900">
                    {item.title}
                  </h3>
                  {item.description ? (
                    <p className="mt-1 text-pretty text-sm leading-6 text-slate-600">
                      {item.description}
                    </p>
                  ) : null}
                  {item.page_path ? (
                    <code className="mt-2 inline-block rounded-lg bg-slate-100 px-2 py-1 text-xs text-slate-600">
                      {item.page_path}
                    </code>
                  ) : null}
                </div>
                {item.source !== "system" ? (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="min-h-10 min-w-10 self-end text-slate-400 hover:text-rose-700 sm:self-auto"
                    aria-label={`Удалить изменение ${item.title}`}
                    onClick={() =>
                      setPendingDelete({
                        endpoint: `/business/${businessId}/web-change-annotations/${item.id}`,
                        label: `отметку «${item.title}»`,
                      })
                    }
                  >
                    <Trash2 />
                  </Button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
        {!configuration?.annotations?.length ? (
          <EmptyStart
            title="История изменений пока пуста"
            description="Добавьте первое изменение перед правкой сайта — тогда будущие графики можно будет объяснить."
            action={
              <Button variant="outline" onClick={() => setAnnotationOpen(true)}>
                Добавить отметку
              </Button>
            }
          />
        ) : null}
        <Dialog open={annotationOpen} onOpenChange={setAnnotationOpen}>
          <DialogContent className="rounded-3xl">
            <DialogHeader>
              <DialogTitle>Записать изменение сайта</DialogTitle>
              <DialogDescription>
                Опишите факт и ожидаемый результат. Эта отметка появится рядом с
                аналитикой.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div>
                <Label htmlFor="change-type">Тип изменения</Label>
                <select
                  id="change-type"
                  className={cn(fieldClass, "mt-2")}
                  value={annotationType}
                  onChange={(event) => setAnnotationType(event.target.value)}
                >
                  <option value="page">Страница</option>
                  <option value="price">Цена</option>
                  <option value="headline">Заголовок</option>
                  <option value="cta">Кнопка</option>
                  <option value="form">Форма</option>
                  <option value="campaign">Реклама</option>
                  <option value="promotion">Акция</option>
                  <option value="incident">Ошибка</option>
                  <option value="tracker">Трекер</option>
                  <option value="other">Другое</option>
                </select>
              </div>
              <div>
                <Label htmlFor="change-title">Что изменили</Label>
                <Input
                  id="change-title"
                  className="mt-2 min-h-11"
                  value={annotationTitle}
                  onChange={(event) => setAnnotationTitle(event.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="change-description">Подробности</Label>
                <Textarea
                  id="change-description"
                  className="mt-2"
                  value={annotationDescription}
                  onChange={(event) =>
                    setAnnotationDescription(event.target.value)
                  }
                />
              </div>
              <div>
                <Label htmlFor="change-path">Страница</Label>
                <Input
                  id="change-path"
                  className="mt-2 min-h-11"
                  value={annotationPath}
                  onChange={(event) => setAnnotationPath(event.target.value)}
                  placeholder="/services/haircuts"
                />
              </div>
              <div>
                <Label htmlFor="change-impact">Что ожидаем</Label>
                <Input
                  id="change-impact"
                  className="mt-2 min-h-11"
                  value={annotationImpact}
                  onChange={(event) => setAnnotationImpact(event.target.value)}
                  placeholder="Больше переходов к записи"
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                onClick={() => void saveAnnotation()}
                disabled={saving || !annotationTitle}
              >
                Сохранить отметку
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        <AlertDialog
          open={Boolean(pendingDelete)}
          onOpenChange={(open) => {
            if (!open) setPendingDelete(null);
          }}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>
                Удалить {pendingDelete?.label}?
              </AlertDialogTitle>
              <AlertDialogDescription>
                Отметка исчезнет из истории изменений и с графика.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Отмена</AlertDialogCancel>
              <AlertDialogAction
                onClick={() => void confirmDelete()}
                className="bg-rose-700 hover:bg-rose-800"
              >
                Удалить
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    );
  }

  const integrationExample = `curl -X POST https://localos.pro/api/web-tracking/conversions \\\n+  -H "Authorization: Bearer YOUR_KEY" \\\n+  -H "Content-Type: application/json" \\\n+  -d '{"source":"yclients","external_id":"ORDER-123","event_type":"booking_confirmed","attribution_session_id":"s_..."}'`;

  return (
    <div className="space-y-6">
      {alert}
      <section className="rounded-3xl bg-white p-5 shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_1px_2px_-1px_rgba(15,23,42,0.06),0_6px_20px_rgba(15,23,42,0.04)] sm:p-6">
        <div className="flex items-start gap-3">
          <div className="rounded-xl bg-slate-950 p-2 text-white">
            <Code2 className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-balance text-lg font-semibold text-slate-950">
              Разметка кнопок и форм
            </h2>
            <p className="mt-1 text-pretty text-sm leading-6 text-slate-600">
              Добавьте постоянные ID на сайт. LocalOS посчитает показы, клики и
              успешные формы без значений полей.
            </p>
          </div>
        </div>
        <div className="mt-5 grid gap-3 lg:grid-cols-2">
          <pre className="overflow-x-auto rounded-2xl bg-slate-950 p-4 text-xs leading-6 text-slate-100">
            <code>
              {
                '<a data-localos-cta="booking_hero"\n   data-localos-cta-label="Записаться">\n  Записаться\n</a>'
              }
            </code>
          </pre>
          <pre className="overflow-x-auto rounded-2xl bg-slate-950 p-4 text-xs leading-6 text-slate-100">
            <code>
              {
                '<form data-localos-form="main_booking">\n  ...\n</form>\n\nLocalOSTracker.trackFormResult(\n  "success", form\n);'
              }
            </code>
          </pre>
        </div>
      </section>

      <section className="rounded-3xl bg-white p-5 shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_1px_2px_-1px_rgba(15,23,42,0.06),0_6px_20px_rgba(15,23,42,0.04)] sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="rounded-xl bg-emerald-100 p-2 text-emerald-800">
              <KeyRound className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-balance text-lg font-semibold text-slate-950">
                Подтверждённые заявки и оплаты
              </h2>
              <p className="mt-1 text-pretty text-sm leading-6 text-slate-600">
                Ключ нужен CRM, телефонии или системе записи. Он показывается
                один раз и не передаёт персональные данные.
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            onClick={() =>
              configuration?.conversion_key?.configured
                ? setKeyConfirmOpen(true)
                : void rotateKey()
            }
            disabled={saving}
            className="min-h-11 shrink-0 transition-transform active:scale-[0.96]"
          >
            {saving ? <RefreshCw className="animate-spin" /> : <KeyRound />}
            {configuration?.conversion_key?.configured
              ? "Заменить ключ"
              : "Создать ключ"}
          </Button>
        </div>
        {revealedKey ? (
          <div className="mt-5 rounded-2xl bg-amber-50 p-4 ring-1 ring-amber-200">
            <div className="flex items-center gap-2 font-semibold text-amber-900">
              <AlertCircle className="h-4 w-4" />
              Скопируйте сейчас — позже ключ не показывается
            </div>
            <div className="mt-3 flex gap-2">
              <code className="min-w-0 flex-1 overflow-x-auto rounded-xl bg-white px-3 py-2 text-sm text-slate-800 ring-1 ring-amber-200">
                {revealedKey}
              </code>
              <Button variant="outline" onClick={() => void copyKey()}>
                {copied ? <CheckCircle2 /> : <Clipboard />}
                {copied ? "Скопировано" : "Копировать"}
              </Button>
            </div>
          </div>
        ) : null}
        <pre className="mt-5 overflow-x-auto rounded-2xl bg-slate-950 p-4 text-xs leading-6 text-slate-100">
          <code>{integrationExample}</code>
        </pre>
      </section>

      <section className="rounded-3xl bg-white p-5 shadow-[0_0_0_1px_rgba(15,23,42,0.06),0_1px_2px_-1px_rgba(15,23,42,0.06),0_6px_20px_rgba(15,23,42,0.04)] sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="rounded-xl bg-blue-100 p-2 text-blue-800">
              <Megaphone className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-balance text-lg font-semibold text-slate-950">
                Расходы на рекламу
              </h2>
              <p className="mt-1 text-pretty text-sm leading-6 text-slate-600">
                Добавьте расходы вручную сейчас; API рекламных кабинетов можно
                подключить позже.
              </p>
            </div>
          </div>
          <Button
            onClick={() => setCostOpen(true)}
            className="min-h-11 shrink-0 transition-transform active:scale-[0.96]"
          >
            <Plus />
            Добавить расходы
          </Button>
        </div>
        <div className="mt-5 divide-y divide-slate-100">
          {configuration?.campaign_costs?.map((item) => (
            <div
              key={item.id}
              className="flex min-h-14 items-center gap-3 py-2"
            >
              <div className="min-w-0 flex-1">
                <div className="font-medium text-slate-900">
                  {item.source}
                  {item.campaign ? ` · ${item.campaign}` : ""}
                  {item.content ? ` · ${item.content}` : ""}
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  {item.period_start} — {item.period_end}
                </div>
              </div>
              <strong className="tabular-nums text-slate-900">
                {item.cost} {item.currency}
              </strong>
              <Button
                variant="ghost"
                size="icon"
                className="min-h-10 min-w-10 text-slate-400 hover:text-rose-700"
                aria-label={`Удалить расходы ${item.source}`}
                onClick={() =>
                  void remove(
                    `/business/${businessId}/web-campaign-costs/${item.id}`,
                  )
                }
              >
                <Trash2 />
              </Button>
            </div>
          ))}
        </div>
        {!configuration?.campaign_costs?.length ? (
          <p className="mt-5 rounded-xl bg-slate-50 px-4 py-5 text-center text-sm text-slate-500">
            Расходы ещё не добавлены.
          </p>
        ) : null}
      </section>

      <Dialog open={costOpen} onOpenChange={setCostOpen}>
        <DialogContent className="max-w-2xl rounded-3xl">
          <DialogHeader>
            <DialogTitle>Добавить расходы кампании</DialogTitle>
            <DialogDescription>
              Используйте те же UTM-значения, что стоят в рекламной ссылке.
              Объявление — это utm_content.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2 sm:grid-cols-2">
            <div>
              <Label htmlFor="cost-source">utm_source</Label>
              <Input
                id="cost-source"
                className="mt-2 min-h-11"
                value={costSource}
                onChange={(event) => setCostSource(event.target.value)}
                placeholder="yandex"
              />
            </div>
            <div>
              <Label htmlFor="cost-medium">utm_medium</Label>
              <Input
                id="cost-medium"
                className="mt-2 min-h-11"
                value={costMedium}
                onChange={(event) => setCostMedium(event.target.value)}
                placeholder="cpc"
              />
            </div>
            <div>
              <Label htmlFor="cost-campaign">utm_campaign</Label>
              <Input
                id="cost-campaign"
                className="mt-2 min-h-11"
                value={costCampaign}
                onChange={(event) => setCostCampaign(event.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="cost-content">utm_content — объявление</Label>
              <Input
                id="cost-content"
                className="mt-2 min-h-11"
                value={costContent}
                onChange={(event) => setCostContent(event.target.value)}
              />
            </div>
            <div className="sm:col-span-2">
              <Label htmlFor="cost-term">utm_term</Label>
              <Input
                id="cost-term"
                className="mt-2 min-h-11"
                value={costTerm}
                onChange={(event) => setCostTerm(event.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="cost-start">Начало</Label>
              <Input
                id="cost-start"
                type="date"
                className="mt-2 min-h-11"
                value={costStart}
                onChange={(event) => setCostStart(event.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="cost-end">Конец</Label>
              <Input
                id="cost-end"
                type="date"
                className="mt-2 min-h-11"
                value={costEnd}
                onChange={(event) => setCostEnd(event.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="cost-value">Расходы</Label>
              <Input
                id="cost-value"
                inputMode="decimal"
                className="mt-2 min-h-11"
                value={costValue}
                onChange={(event) => setCostValue(event.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="cost-currency">Валюта</Label>
              <Input
                id="cost-currency"
                maxLength={3}
                className="mt-2 min-h-11 uppercase"
                value={costCurrency}
                onChange={(event) =>
                  setCostCurrency(event.target.value.toUpperCase())
                }
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              onClick={() => void saveCost()}
              disabled={
                saving || !costSource || !costValue || !costStart || !costEnd
              }
            >
              Сохранить расходы
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <AlertDialog open={keyConfirmOpen} onOpenChange={setKeyConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Заменить ключ интеграции?</AlertDialogTitle>
            <AlertDialogDescription>
              Текущий ключ сразу перестанет принимать события. Сначала
              подготовьте обновление во всех CRM, телефонии и
              webhook-интеграциях.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Отмена</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                setKeyConfirmOpen(false);
                void rotateKey();
              }}
            >
              Заменить ключ
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};
