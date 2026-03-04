import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import Footer from "@/components/Footer";

const Requisites = () => {
  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <Card>
          <CardHeader>
            <CardTitle className="text-3xl font-bold text-center">
              Реквизиты
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-6 text-foreground">
              <section className="space-y-3">
                <div className="grid gap-3 sm:grid-cols-[220px_1fr]">
                  <div className="font-semibold text-muted-foreground">Имя</div>
                  <div>Демьянов Александр Петрович</div>
                </div>
                <div className="grid gap-3 sm:grid-cols-[220px_1fr]">
                  <div className="font-semibold text-muted-foreground">ИНН</div>
                  <div>780224024640</div>
                </div>
                <div className="grid gap-3 sm:grid-cols-[220px_1fr]">
                  <div className="font-semibold text-muted-foreground">Банк</div>
                  <div>Северо-Западный банк ПАО Сбербанк</div>
                </div>
                <div className="grid gap-3 sm:grid-cols-[220px_1fr]">
                  <div className="font-semibold text-muted-foreground">БИК</div>
                  <div>044030653</div>
                </div>
                <div className="grid gap-3 sm:grid-cols-[220px_1fr]">
                  <div className="font-semibold text-muted-foreground">Номер счёта</div>
                  <div>40817810655192572704</div>
                </div>
              </section>
            </div>
          </CardContent>
        </Card>
      </div>
      <Footer />
    </div>
  );
};

export default Requisites;
