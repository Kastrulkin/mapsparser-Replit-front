import { useState } from "react";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";

const Contact = () => {
  const [form, setForm] = useState({
    name: "",
    phone: "",
    email: "",
    yandex: "",
  });
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name || !form.phone || !form.email || !form.yandex) {
      setError("Пожалуйста, заполните все поля.");
      return;
    }
    setError("");
    setSubmitted(true);
    // Здесь можно добавить отправку данных на сервер или в supabase
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Header />
      <main className="flex-1 flex items-center justify-center py-16 px-4 sm:px-6 lg:px-8">
        <div className="w-full max-w-lg bg-card rounded-2xl shadow-xl p-8 border border-border">
          <h1 className="text-3xl font-bold text-foreground mb-6 text-center">Давайте заполним ваш график!</h1>
          {submitted ? (
            <div className="text-center text-green-600 text-xl font-semibold py-12">
              Спасибо! Мы свяжемся с вами в ближайшее время.
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <label className="block text-sm font-medium mb-1 text-foreground" htmlFor="name">Имя</label>
                <input
                  type="text"
                  id="name"
                  name="name"
                  value={form.name}
                  onChange={handleChange}
                  className="w-full border rounded px-3 py-2 bg-background text-foreground"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 text-foreground" htmlFor="phone">Телефон</label>
                <input
                  type="tel"
                  id="phone"
                  name="phone"
                  value={form.phone}
                  onChange={handleChange}
                  className="w-full border rounded px-3 py-2 bg-background text-foreground"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 text-foreground" htmlFor="email">Почта</label>
                <input
                  type="email"
                  id="email"
                  name="email"
                  value={form.email}
                  onChange={handleChange}
                  className="w-full border rounded px-3 py-2 bg-background text-foreground"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 text-foreground" htmlFor="yandex">Есть ли у вас аккаунт Яндекс.Бизнес?</label>
                <select
                  id="yandex"
                  name="yandex"
                  value={form.yandex}
                  onChange={handleChange}
                  className="w-full border rounded px-3 py-2 bg-background text-foreground"
                  required
                >
                  <option value="">Выберите...</option>
                  <option value="yes">Да</option>
                  <option value="no">Нет</option>
                </select>
              </div>
              {error && <div className="text-red-600 text-sm">{error}</div>}
              <Button type="submit" size="lg" className="w-full text-lg px-8 py-3 bg-orange-500 hover:bg-orange-600 text-white border-none mt-2">
                Отправить
              </Button>
            </form>
          )}
        </div>
      </main>
      <Footer />
    </div>
  );
};

export default Contact; 