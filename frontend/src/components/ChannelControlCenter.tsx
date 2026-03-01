import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { newAuth } from "@/lib/auth_new";
import { useToast } from "@/components/ui/use-toast";
import { Loader2, MessageCircleMore, RefreshCcw, Send, ShieldCheck } from "lucide-react";

interface ChannelStatus {
  channel_id: string;
  label: string;
  provider: string;
  configured: boolean;
  testable: boolean;
  status: string;
  detail: string;
  target?: string | null;
}

interface RouteItem extends ChannelStatus {
  preferred?: boolean;
  fallback_order?: number;
  eligible?: boolean;
}

interface ChannelControlCenterProps {
  businessId: string | null;
}

export const ChannelControlCenter = ({ businessId }: ChannelControlCenterProps) => {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [sendingChannelId, setSendingChannelId] = useState<string | null>(null);
  const [channels, setChannels] = useState<ChannelStatus[]>([]);
  const [recommendedRoute, setRecommendedRoute] = useState<RouteItem[]>([]);
  const [businessName, setBusinessName] = useState("");

  const loadStatus = async () => {
    if (!businessId) {
      setChannels([]);
      setRecommendedRoute([]);
      setBusinessName("");
      return;
    }
    setLoading(true);
    try {
      const token = newAuth.getToken();
      if (!token) {
        return;
      }
      const res = await fetch(`/api/channels/status?business_id=${encodeURIComponent(businessId)}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || "Не удалось загрузить статус каналов");
      }
      setChannels(Array.isArray(data.channels) ? data.channels : []);
      setRecommendedRoute(Array.isArray(data.recommended_route) ? data.recommended_route : []);
      setBusinessName(data.business_name || "");
    } catch (e: any) {
      toast({
        title: "Ошибка",
        description: e.message || "Не удалось загрузить статус каналов",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [businessId]);

  const readyCount = useMemo(
    () => channels.filter((item) => item.status === "ready").length,
    [channels],
  );

  const handleTestSend = async (channelId: string) => {
    if (!businessId) {
      return;
    }
    setSendingChannelId(channelId);
    try {
      const token = newAuth.getToken();
      if (!token) {
        throw new Error("Нужна авторизация");
      }
      const res = await fetch("/api/channels/test-send", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          business_id: businessId,
          channel_id: channelId,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || "Тестовая отправка не удалась");
      }
      toast({
        title: "Тест отправлен",
        description: "Проверьте указанный канал. Сообщение уже ушло.",
      });
    } catch (e: any) {
      toast({
        title: "Тест не отправлен",
        description: e.message || "Не удалось выполнить тестовую отправку",
        variant: "destructive",
      });
    } finally {
      setSendingChannelId(null);
    }
  };

  const handleAutoRouteTest = async () => {
    if (!businessId) {
      return;
    }
    setSendingChannelId("auto");
    try {
      const token = newAuth.getToken();
      if (!token) {
        throw new Error("Нужна авторизация");
      }
      const res = await fetch("/api/channels/test-send", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          business_id: businessId,
          channel_id: "auto",
          preferred_provider: "telegram",
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || "Авто-маршрут не доставил сообщение");
      }
      toast({
        title: "Авто-маршрут сработал",
        description: `Сообщение ушло через ${data.channel_id}.`,
      });
    } catch (e: any) {
      toast({
        title: "Авто-маршрут не сработал",
        description: e.message || "Не удалось пройти по цепочке fallback",
        variant: "destructive",
      });
    } finally {
      setSendingChannelId(null);
    }
  };

  const getBadgeClass = (status: string) => {
    if (status === "ready") {
      return "bg-emerald-100 text-emerald-700 border-emerald-200";
    }
    if (status === "verification_required") {
      return "bg-amber-100 text-amber-700 border-amber-200";
    }
    return "bg-slate-100 text-slate-600 border-slate-200";
  };

  return (
    <Card className="border-slate-200 shadow-sm">
      <CardHeader className="pb-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-xl">
              <MessageCircleMore className="h-5 w-5 text-primary" />
              Центр каналов
            </CardTitle>
            <CardDescription className="mt-1">
              Единый статус каналов связи для ИИ-агентов и быстрый тест отправки. Используйте это как
              первичную проверку перед запуском автоматизации.
            </CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={loadStatus} disabled={loading || !businessId}>
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCcw className="mr-2 h-4 w-4" />}
            Обновить
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="rounded-2xl border border-amber-200 bg-gradient-to-r from-amber-50 via-white to-orange-50 p-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="text-sm font-medium text-slate-700">
                {businessName ? `Бизнес: ${businessName}` : "Выберите бизнес"}
              </div>
              <div className="mt-1 text-xs text-slate-500">
                Готово каналов: {readyCount} из {channels.length}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-white px-3 py-1 text-xs font-medium text-slate-700">
                <ShieldCheck className="h-4 w-4 text-emerald-600" />
                Multi-channel readiness
              </div>
              <Button size="sm" onClick={handleAutoRouteTest} disabled={!businessId || sendingChannelId === "auto"}>
                {sendingChannelId === "auto" ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Send className="mr-2 h-4 w-4" />
                )}
                Авто-тест по цепочке
              </Button>
            </div>
          </div>
        </div>

        {businessId && recommendedRoute.length > 0 ? (
          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
            <div className="text-sm font-semibold text-slate-900">Рекомендуемая цепочка доставки</div>
            <div className="mt-3 flex flex-wrap gap-2">
              {recommendedRoute.map((item) => (
                <div
                  key={item.channel_id}
                  className={`rounded-full border px-3 py-1 text-xs font-medium ${
                    item.eligible
                      ? "border-emerald-200 bg-white text-slate-700"
                      : "border-slate-200 bg-white text-slate-400"
                  }`}
                >
                  {item.fallback_order}. {item.label}
                  {item.preferred ? " (preferred)" : ""}
                  {!item.eligible ? " [skip]" : ""}
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {!businessId ? (
          <div className="rounded-xl border border-dashed border-slate-300 px-4 py-6 text-sm text-slate-500">
            Сначала выберите бизнес. После этого здесь появится реальный статус каналов.
          </div>
        ) : channels.length === 0 && !loading ? (
          <div className="rounded-xl border border-dashed border-slate-300 px-4 py-6 text-sm text-slate-500">
            Каналы ещё не настроены.
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {channels.map((channel) => (
              <div
                key={channel.channel_id}
                className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-slate-900">{channel.label}</div>
                    <div className="mt-1 text-xs uppercase tracking-wide text-slate-400">{channel.provider}</div>
                  </div>
                  <div className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${getBadgeClass(channel.status)}`}>
                    {channel.status === "ready"
                      ? "Готов"
                      : channel.status === "verification_required"
                        ? "Нужна верификация"
                        : "Не настроен"}
                  </div>
                </div>

                <div className="mt-4 text-sm text-slate-600">{channel.detail}</div>
                {channel.target ? (
                  <div className="mt-3 text-xs text-slate-500">Цель теста: {channel.target}</div>
                ) : null}

                <div className="mt-5 flex items-center justify-between gap-3">
                  <div className="text-xs text-slate-400">
                    {channel.configured ? "Конфигурация найдена" : "Конфигурации пока нет"}
                  </div>
                  <Button
                    size="sm"
                    variant={channel.testable ? "default" : "outline"}
                    disabled={!channel.testable || sendingChannelId === channel.channel_id}
                    onClick={() => handleTestSend(channel.channel_id)}
                  >
                    {sendingChannelId === channel.channel_id ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="mr-2 h-4 w-4" />
                    )}
                    {channel.testable ? "Тест" : "Только статус"}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};
