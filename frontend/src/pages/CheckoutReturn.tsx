import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { CheckCircle2, CircleAlert, ExternalLink, Loader2, Mail } from "lucide-react";

type CheckoutStatusPayload = {
  session_id: string;
  provider: string;
  entry_point: string;
  status: string;
  tariff_id: string;
  email: string;
  telegram_id: string;
  user_id: string;
  business_id: string;
  business_name: string;
  audit_public_url: string;
  maps_url: string;
  account_created: boolean;
  business_created: boolean;
  requires_password_setup: boolean;
  paid_at?: string;
  completed_at?: string;
  provider_status?: string;
};

const terminalStatuses = new Set(["completed", "failed", "expired"]);

const CheckoutReturn = () => {
  const [searchParams] = useSearchParams();
  const sessionId = String(searchParams.get("session_id") || "").trim();
  const canceled = String(searchParams.get("status") || "").trim().toLowerCase() === "cancelled";
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [checkout, setCheckout] = useState<CheckoutStatusPayload | null>(null);

  useEffect(() => {
    if (!sessionId) {
      setLoading(false);
      setError("Не найден session_id платежа.");
      return;
    }

    let alive = true;
    let timer: number | null = null;

    const poll = async () => {
      try {
        const response = await fetch(`/api/billing/checkout/session/status?session_id=${encodeURIComponent(sessionId)}`);
        const data = await response.json();
        if (!alive) return;
        if (!response.ok) {
          throw new Error(String(data?.error || "Не удалось получить статус оплаты"));
        }
        const nextCheckout = data?.checkout as CheckoutStatusPayload;
        setCheckout(nextCheckout);
        setError(null);
        const nextStatus = String(nextCheckout?.status || "").trim().toLowerCase();
        if (!terminalStatuses.has(nextStatus)) {
          timer = window.setTimeout(poll, 2500);
        }
      } catch (err) {
        if (!alive) return;
        setError(err instanceof Error ? err.message : "Не удалось получить статус оплаты");
      } finally {
        if (alive) {
          setLoading(false);
        }
      }
    };

    void poll();
    return () => {
      alive = false;
      if (timer) {
        window.clearTimeout(timer);
      }
    };
  }, [sessionId]);

  const title = useMemo(() => {
    if (canceled) return "Оплата отменена";
    if (error) return "Не удалось завершить оплату";
    if (loading && !checkout) return "Проверяем оплату";
    if (checkout?.status === "completed") return "Оплата подтверждена";
    if (checkout?.status === "failed" || checkout?.status === "expired") return "Платёж не завершён";
    return "Завершаем оформление";
  }, [canceled, error, loading, checkout]);

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-12">
      <div className="mx-auto max-w-2xl rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="flex items-start gap-4">
          {checkout?.status === "completed" ? (
            <CheckCircle2 className="mt-1 h-8 w-8 text-emerald-600" />
          ) : error || canceled || checkout?.status === "failed" || checkout?.status === "expired" ? (
            <CircleAlert className="mt-1 h-8 w-8 text-rose-600" />
          ) : (
            <Loader2 className="mt-1 h-8 w-8 animate-spin text-sky-600" />
          )}
          <div className="min-w-0 flex-1">
            <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
            <p className="mt-2 text-sm text-slate-600">
              {checkout?.status === "completed"
                ? "Мы сохранили контекст оплаты и подготовили доступ к платным функциям."
                : canceled
                  ? "Платёж был отменён. Вы можете вернуться к тарифам и попробовать снова."
                  : error
                    ? error
                    : "Это может занять несколько секунд, пока провайдер подтвердит платёж."}
            </p>
          </div>
        </div>

        {checkout ? (
          <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
            <div>Тариф: <span className="font-medium text-slate-900">{checkout.tariff_id}</span></div>
            {checkout.email ? <div className="mt-1">Email: <span className="font-medium text-slate-900">{checkout.email}</span></div> : null}
            {checkout.business_name ? <div className="mt-1">Бизнес: <span className="font-medium text-slate-900">{checkout.business_name}</span></div> : null}
          </div>
        ) : null}

        <div className="mt-8 flex flex-wrap gap-3">
          {checkout?.audit_public_url ? (
            <a href={checkout.audit_public_url} target="_blank" rel="noreferrer">
              <Button className="bg-slate-900 text-white hover:bg-slate-800">
                Открыть аудит
                <ExternalLink className="ml-2 h-4 w-4" />
              </Button>
            </a>
          ) : null}

          {checkout?.status === "completed" && checkout.requires_password_setup && checkout.email ? (
            <Link to={`/set-password?email=${encodeURIComponent(checkout.email)}`}>
              <Button variant="outline">
                <Mail className="mr-2 h-4 w-4" />
                Установить пароль
              </Button>
            </Link>
          ) : null}

          {checkout?.status === "completed" ? (
            <Link to="/login">
              <Button variant="outline">Войти в LocalOS</Button>
            </Link>
          ) : null}

          <Link to="/about#pricing">
            <Button variant="ghost">Назад к тарифам</Button>
          </Link>
        </div>
      </div>
    </div>
  );
};

export default CheckoutReturn;
