import { useState } from "react";
import { Button } from "@/components/ui/button";

type StepKey = 1 | 2 | 3;

const WizardYandex = () => {
  const [step, setStep] = useState<StepKey>(1);

  const next = () => setStep((s) => (s < 3 ? ((s + 1) as StepKey) : s));
  const prev = () => setStep((s) => (s > 1 ? ((s - 1) as StepKey) : s));

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto px-4 py-8">
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-gray-900">Мастер оптимизации бизнеса</h1>
            <div className="text-sm text-gray-600">Шаг {step}/3</div>
          </div>
        </div>

        {/* Шаг 1 */}
        {step === 1 && (
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="mb-4 text-gray-600">Соберём ключевые данные по карточке, чтобы дать точные рекомендации.</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Вставьте ссылку на карточку вашего салона на картах.
                </label>
                <input className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="https://yandex.ru/maps/org/..." />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Рейтинг (0–5)</label>
                <input className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="4.6" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Количество отзывов</label>
                <input className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="128" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Частота обновления фото</label>
                <div className="flex flex-wrap gap-2">
                  {['Еженедельно','Ежемесячно','Раз в квартал','Редко','Не знаю'].map(x => (
                    <span key={x} className="px-3 py-1 rounded-md bg-gray-100 text-gray-700 text-sm">{x}</span>
                  ))}
                </div>
              </div>
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-2">Новости (наличие/частота)</label>
                <div className="flex flex-wrap gap-2 mb-3">
                  {['Да','Нет'].map(x => (<span key={x} className="px-3 py-1 rounded-md bg-gray-100 text-gray-700 text-sm">{x}</span>))}
                </div>
                <div className="flex flex-wrap gap-2">
                  {['Еженедельно','Ежемесячно','Реже','По событию'].map(x => (
                    <span key={x} className="px-3 py-1 rounded-md bg-gray-100 text-gray-700 text-sm">{x}</span>
                  ))}
                </div>
              </div>
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">Текущие тексты/услуги</label>
                <textarea className="w-full px-3 py-2 border border-gray-300 rounded-md" rows={5} placeholder={"Стрижка мужская\nСтрижка женская\nОкрашивание"} />
              </div>
            </div>
          </div>
        )}

        {/* Шаг 2 */}
        {step === 2 && (
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="mb-4 text-gray-600">Опишите, как вы хотите звучать и чего избегать. Это задаст тон для всех текстов.</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">What do you like?</label>
                <textarea className="w-full px-3 py-2 border border-gray-300 rounded-md" rows={4} placeholder="Лаконично, экспертно, заботливо, премиально…" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">What do you dislike?</label>
                <textarea className="w-full px-3 py-2 border border-gray-300 rounded-md" rows={4} placeholder="Без клише, без канцелярита, без агрессивных продаж…" />
              </div>
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-2">Понравившиеся формулировки (до 5)</label>
                <div className="space-y-2">
                  {[1,2,3,4,5].map(i => (
                    <input key={i} className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="Например: Стрижка, которая держит форму и не требует укладки" />
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Шаг 3 */}
        {step === 3 && (
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="mb-4 text-gray-600">Немного цифр, чтобы план был реалистичным. Можно заполнить позже.</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Как давно работаете</label>
                <div className="flex flex-wrap gap-2">
                  {['0–6 мес','6–12 мес','1–3 года','3+ лет'].map(x => (<span key={x} className="px-3 py-1 rounded-md bg-gray-100 text-gray-700 text-sm">{x}</span>))}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Постоянные клиенты</label>
                <input className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="например, 150" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">CRM</label>
                <input className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="Например: Yclients" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Расположение</label>
                <div className="flex flex-wrap gap-2">
                  {['Дом','ТЦ','Двор','Магистраль','Центр','Спальник','Около метро'].map(x => (<span key={x} className="px-3 py-1 rounded-md bg-gray-100 text-gray-700 text-sm">{x}</span>))}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Средний чек (₽)</label>
                <input className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="2200" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Выручка в месяц (₽)</label>
                <input className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="350000" />
              </div>
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">Что нравится/не нравится в карточке</label>
                <textarea className="w-full px-3 py-2 border border-gray-300 rounded-md" rows={4} placeholder="Нравится: фото, тон. Не нравится: мало отзывов, нет новостей…" />
              </div>
            </div>
          </div>
        )}

        <div className="mt-6 flex justify-between">
          <Button variant="outline" onClick={prev} disabled={step===1}>Назад</Button>
          {step < 3 ? (
            <Button onClick={next}>Продолжить</Button>
          ) : (
            <Button onClick={() => (window.location.href = "/sprint")}>Сформировать план</Button>
          )}
        </div>
      </div>
    </div>
  );
};

export default WizardYandex;


