import { Link, useSearchParams } from "react-router-dom";
import { ArrowRight, CheckCircle2, ShieldCheck } from "lucide-react";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const YclientsConnect = () => {
  const [params] = useSearchParams();
  const salonId = params.get("salon_id") || params.get("company_id") || "";

  return (
    <div className="min-h-screen bg-background">
      <main className="mx-auto flex max-w-5xl flex-col gap-8 px-4 py-12 sm:px-6 lg:px-8">
        <section className="space-y-4">
          <p className="text-sm font-semibold uppercase tracking-wide text-primary">YCLIENTS + LocalOS</p>
          <h1 className="max-w-3xl text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            Подключение филиала YCLIENTS к LocalOS
          </h1>
          <p className="max-w-3xl text-base leading-7 text-muted-foreground">
            LocalOS импортирует данные филиала, услуги и цены, помогает подключить карты,
            подготовить ответы на отзывы, контент-план, новости и первые партнёрские письма.
            Внешние публикации и массовые действия выполняются только после вашего подтверждения.
          </p>
        </section>

        <div className="grid gap-4 md:grid-cols-[1.2fr_0.8fr]">
          <Card>
            <CardHeader>
              <CardTitle>Что сделать дальше</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm leading-6 text-muted-foreground">
              <div className="flex gap-3">
                <CheckCircle2 className="mt-1 h-5 w-5 shrink-0 text-primary" />
                <p>Войдите в LocalOS или создайте аккаунт владельца бизнеса.</p>
              </div>
              <div className="flex gap-3">
                <CheckCircle2 className="mt-1 h-5 w-5 shrink-0 text-primary" />
                <p>Выберите существующий бизнес или создайте новый по данным филиала YCLIENTS.</p>
              </div>
              <div className="flex gap-3">
                <CheckCircle2 className="mt-1 h-5 w-5 shrink-0 text-primary" />
                <p>Запустите импорт услуг и цен, затем подключите Google, Яндекс или 2ГИС карты.</p>
              </div>
              <Button asChild className="mt-2">
                <Link to="/login">
                  Продолжить в LocalOS
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Данные подключения</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm text-muted-foreground">
              <div>
                <div className="font-medium text-foreground">Филиал YCLIENTS</div>
                <div>{salonId || "Будет определён после редиректа из YCLIENTS"}</div>
              </div>
              <div className="flex gap-3 rounded-md border p-3">
                <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                <p>
                  LocalOS использует только разрешённые вами данные. Публикации, отправки и
                  изменения во внешних сервисах требуют ручного approval.
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
      <Footer />
    </div>
  );
};

export default YclientsConnect;
