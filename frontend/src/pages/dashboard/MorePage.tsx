import { Bot, Building2, CreditCard, MessageSquare, Radar, Settings, Sparkles, WalletCards } from 'lucide-react';
import { Link } from 'react-router-dom';

const sections = [
  {
    title: 'Бизнес',
    items: [
      { title: 'Профиль компании', description: 'Данные, услуги и точки присутствия.', route: '/dashboard/profile', icon: Building2 },
      { title: 'Финансы', description: 'Выручка, загрузка и средний чек.', route: '/dashboard/finance', icon: CreditCard },
      { title: 'Средний чек', description: 'Идеи допродаж и пакетных предложений.', route: '/dashboard/average-ticket', icon: WalletCards },
    ],
  },
  {
    title: 'Работа и контроль',
    items: [
      { title: 'Оператор', description: 'Задачи, подтверждения и ручные действия.', route: '/dashboard/operator', icon: Bot },
      { title: 'Агенты', description: 'Регулярная работа и история запусков.', route: '/dashboard/agents', icon: Sparkles },
      { title: 'Чаты', description: 'Сообщения и ответы клиентам.', route: '/dashboard/chats', icon: MessageSquare },
      { title: 'Telegram-радар', description: 'Сигналы рынка и новые возможности.', route: '/dashboard/telegram-radar', icon: Radar },
      { title: 'Настройки и подключения', description: 'Тариф, интеграции, команда и безопасность.', route: '/dashboard/settings', icon: Settings },
    ],
  },
];

export const MorePage = () => (
  <div className="space-y-6 pb-10">
    <header className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Ещё</p>
      <h1 className="mt-2 text-balance text-3xl font-semibold tracking-tight text-slate-950">Управление бизнесом и LocalOS</h1>
      <p className="mt-3 max-w-2xl text-pretty text-sm leading-6 text-slate-600">Здесь находятся инструменты, которые помогают выполнять основную работу, но не конкурируют с текущим путём роста.</p>
    </header>
    {sections.map((section) => (
      <section key={section.title}>
        <h2 className="mb-3 text-lg font-semibold text-slate-950">{section.title}</h2>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {section.items.map((item) => {
            const Icon = item.icon;
            return (
              <Link key={item.route} to={item.route} className="group flex min-h-28 items-start gap-4 rounded-2xl border border-slate-200 bg-white p-4 transition-[border-color,box-shadow,transform] duration-150 hover:border-slate-300 hover:shadow-md active:scale-[0.96] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-950 focus-visible:ring-offset-2">
                <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-slate-100 text-slate-700"><Icon className="h-5 w-5" aria-hidden="true" /></span>
                <span><b className="text-balance text-sm text-slate-950">{item.title}</b><small className="mt-1 block text-pretty text-xs leading-5 text-slate-600">{item.description}</small></span>
              </Link>
            );
          })}
        </div>
      </section>
    ))}
  </div>
);
