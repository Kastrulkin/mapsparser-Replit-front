import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Bot,
  CheckCircle2,
  ExternalLink,
  FileText,
  LockKeyhole,
  Plug,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import Footer from "@/components/Footer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

type DocItem = {
  title: string;
  text: string;
  status?: string;
};

type DocSection = {
  slug: string;
  title: string;
  kicker: string;
  summary: string;
  items: DocItem[];
};

const sections: DocSection[] = [
  {
    slug: "overview",
    title: "LocalOS для людей и ИИ-агентов",
    kicker: "Обзор",
    summary:
      "LocalOS помогает локальному бизнесу становиться прибыльнее: привлекать клиентов, повышать средний чек, возвращать людей повторно и вести учёт, чтобы видеть путь к росту.",
    items: [
      {
        title: "Для чего",
        text: "Чтобы связать карты, отзывы, услуги, публикации, партнёрства, коммуникации и финансы в один путь к прибыли, а не вести их как разрозненные задачи.",
      },
      {
        title: "Путь к успеху",
        text: "Сначала LocalOS помогает наладить учёт и диагностику, затем показывает действия для роста заявок, среднего чека, повторных продаж, загрузки и маржи.",
      },
      {
        title: "Кому полезно",
        text: "Владельцам локального бизнеса, управляющим точками, сетям, специалистам по продвижению на картах и командам, которые ведут несколько площадок.",
      },
      {
        title: "Что важно агентам",
        text: "Публикации, массовые изменения, сообщения клиентам, платежи и действия во внешних системах требуют подтверждения человека.",
      },
    ],
  },
  {
    slug: "capabilities",
    title: "Возможности",
    kicker: "Карта возможностей агента",
    summary:
      "Ниже перечислены возможности, которые агент может учитывать при планировании сценариев. Статусы показывают, что уже готово, что находится в бета-режиме, что доступно только внутри команды, а что ещё требует доработки.",
    items: [
      {
        title: "Аудит карточек на картах",
        text: "Проверка карточек, рекомендаций, фото, отзывов, публикаций и услуг. Используется для диагностики и плана улучшений.",
        status: "available",
      },
      {
        title: "Оптимизация услуг",
        text: "SEO-подсказки, защитные правила, отраслевые паттерны, проверка ключей и ручная проверка спорных услуг.",
        status: "available",
      },
      {
        title: "Отзывы и ответы",
        text: "Подготовка ответов на отзывы с учётом тональности, услуги и смежной рекомендации. Публикация требует подтверждения человека.",
        status: "available",
      },
      {
        title: "Новости и публикации",
        text: "Черновики публикаций, контент-план и отраслевые паттерны. Автопубликация во внешние системы ограничена подтверждением человека.",
        status: "beta",
      },
      {
        title: "Финансы",
        text: "Первичный учёт, KPI, выручка, расходы, загрузка рабочих мест, рекомендации и импорт агрегированных данных.",
        status: "beta",
      },
      {
        title: "Управление через Telegram",
        text: "Сводки, подтверждения, ежемесячная перенастройка и команды для суперадмина или оператора.",
        status: "available",
      },
      {
        title: "Партнёрства и исходящие сообщения",
        text: "Поиск партнёров, короткий список кандидатов, утверждение черновиков и контролируемая отправка. Часть сценариев работает как поток с ручным контролем.",
        status: "internal",
      },
      {
        title: "Публичный MCP-контракт",
        text: "MCP-сервер ещё не оформлен. Минимальный OpenAPI-контракт для безопасности Agent API уже есть, но продуктовые сценарии пока не являются полноценным публичным SDK.",
        status: "planned/gap",
      },
    ],
  },
  {
    slug: "approval-policy",
    title: "Подтверждение человеком",
    kicker: "Политика безопасности",
    summary:
      "LocalOS полезен для автоматизации, но действия от имени бизнеса должны оставаться управляемыми человеком.",
    items: [
      {
        title: "Всегда требуется подтверждение",
        text: "Публикации, массовые изменения карточек, отправка сообщений клиентам, платежи, удаления и любые действия во внешних системах.",
      },
      {
        title: "Можно готовить без подтверждения",
        text: "Аудит, черновики, рекомендации, краткие сводки, расчёты KPI, сравнение версий и подготовка вариантов.",
      },
      {
        title: "Как агенту формулировать действие",
        text: "Сначала показать факты, источник данных, предлагаемый текст или изменение, риск и кнопку/команду подтверждения.",
      },
    ],
  },
  {
    slug: "security-model",
    title: "Модель безопасности",
    kicker: "Безопасность Agent API",
    summary:
      "Добронамеренность агента не угадывается по словам. LocalOS ограничивает риск через реестр клиентов, права доступа, песочницу, подтверждения, лимиты запросов, поиск злоупотреблений и журнал действий.",
    items: [
      {
        title: "Сначала песочница",
        text: "Новые агентские клиенты должны начинать с демо-данных, без реальных публикаций, сообщений клиентам, рабочих финансов, внешних ключей доступа и разрушительных действий.",
        status: "beta/internal",
      },
      {
        title: "Минимальные права доступа",
        text: "Первые права доступа: audit:read, services:draft, reviews:draft, content:draft, finance:read, partners:read, approvals:create и publish:request.",
        status: "beta/internal",
      },
      {
        title: "Граница подтверждения",
        text: "Публикации, платежи, удаления, массовые изменения, отправка сообщений и действия во внешних системах не выполняются напрямую. Агент только создаёт запрос на подтверждение.",
        status: "beta/internal",
      },
      {
        title: "Поиск злоупотреблений",
        text: "Флаги: перебор business_id, доступ к чужому бизнесу, ошибки авторизации, попытки без нужных прав, аномальный экспорт, обход подтверждения и несоответствие заявленного сценария поведению.",
        status: "planned",
      },
      {
        title: "Журнал действий",
        text: "Каждый агентский вызов должен оставлять след: клиент, бизнес, действие, риск, краткое описание входа и результата, approval_id, статус, IP, user_agent и created_at.",
        status: "beta/internal",
      },
    ],
  },
  {
    slug: "api",
    title: "API и интеграции",
    kicker: "Интеграции",
    summary:
      "Внутренние API уже используются продуктом. Публичный стабильный контракт для внешних разработчиков и MCP пока требует отдельной стабилизации.",
    items: [
      {
        title: "Авторизация",
        text: "Пользовательский вход работает через email/password и поток подтверждения. Публичные API-ключи для внешних агентов пока не оформлены.",
        status: "available / gap",
      },
      {
        title: "Финансовые API",
        text: "Доступны внутренние API для дашборда, качества данных, рекомендаций, ручного ввода, предпросмотра импорта, импорта и предпросмотра синхронизации с CRM.",
        status: "beta",
      },
      {
        title: "Подтверждения",
        text: "В продукте есть подход с подтверждениями для Telegram, паттернов и потоков с ручным контролем. Для внешнего API нужен единый публичный контракт.",
        status: "internal",
      },
      {
        title: "Внешние интеграции",
        text: "Карты, Telegram и подготовка слоя CRM-адаптеров уже есть. Подключение новых внешних систем требует настройки и проверки контракта.",
        status: "beta",
      },
      {
        title: "Подключение агента",
        text: "Минимальный путь подключения: клиент в песочнице, agent_key, самопроверка, тестовый запрос на подтверждение и проверка события в журнале действий.",
        status: "beta/internal",
      },
      {
        title: "Самопроверка в песочнице",
        text: "POST /api/agent-api/self-test проверяет ключ, статус и права доступа агента, возвращает доступные безопасные действия и пишет тестовое событие в журнал действий.",
        status: "beta/internal",
      },
    ],
  },
  {
    slug: "agent-use-cases",
    title: "10 сценариев для ИИ-агентов",
    kicker: "Сценарии для агентов",
    summary:
      "Сценарии ниже можно использовать как безопасные заготовки. Где действие влияет на внешний мир, агент должен запрашивать подтверждение.",
    items: [
      { title: "1. Аудит карточки", text: "Собрать факты, показать сильные стороны, 3 проблемы и первый шаг." },
      {
        title: "2. План роста выручки",
        text: "Разложить, что сделать сегодня, за 7 дней и регулярно, чтобы карточки, отзывы, услуги и публикации приводили больше заявок.",
      },
      { title: "3. Посты", text: "Подготовить 3-5 публикаций по услугам, сезону и локальному контексту." },
      { title: "4. Ответы на отзывы", text: "Сделать короткие ответы с упоминанием услуги и мягкой смежной рекомендации." },
      { title: "5. Анализ услуг", text: "Найти SEO-пробелы, сохранить факты услуги и предложить точные формулировки." },
      { title: "6. Финансовый разбор", text: "Проверить выручку, расходы, загрузку рабочих мест и красные зоны." },
      { title: "7. Партнёры рядом", text: "Подготовить короткий список партнёров и черновики предложений. Отправка только после подтверждения." },
      { title: "8. Сводка в Telegram", text: "Сжать итоги аудита, финансов или паттернов в короткое сообщение суперадмину." },
      { title: "9. Массовая перегенерация", text: "Найти проблемные элементы, показать причины и запускать пачку только после подтверждения." },
      { title: "10. Ежемесячная перенастройка", text: "Собрать новые паттерны за месяц и отправить человеку на принятие или отклонение." },
    ],
  },
  {
    slug: "gaps",
    title: "Что нужно доработать для полноценного Agent API",
    kicker: "Заметки к дорожной карте",
    summary:
      "Эти пункты не блокируют документацию на сайте, но важны, чтобы внешние агенты могли подключаться как к стабильной платформе.",
    items: [
      {
        title: "Публичная OpenAPI/MCP-спецификация",
        text: "Нужны стабильные схемы данных, модель авторизации, лимиты запросов, версионирование и примеры для внешних клиентов.",
      },
      {
        title: "Единый API подтверждений",
        text: "Нужно оформить API или контракт инструмента для запроса, принятия, отклонения, доработки и журнала проверки.",
      },
      {
        title: "Подключение разработчиков",
        text: "Нужны API-ключи, песочница, тестовые данные, журнал изменений с версиями и правила совместимости.",
      },
      {
        title: "Машиночитаемые возможности",
        text: "Нужны JSON/manifest-версии карты возможностей, политики безопасности и реестра API.",
      },
    ],
  },
];

const statusClassName = (status?: string) => {
  if (!status) {
    return "border-slate-200 bg-slate-50 text-slate-600";
  }
  if (status.includes("available")) {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (status.includes("beta")) {
    return "border-blue-200 bg-blue-50 text-blue-700";
  }
  if (status.includes("internal")) {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  return "border-slate-200 bg-slate-100 text-slate-700";
};

const statusLabel = (status?: string) => {
  if (!status) return "";
  if (status === "available") return "готово";
  if (status === "beta") return "бета";
  if (status === "internal") return "внутренне";
  if (status === "planned") return "в планах";
  if (status === "planned/gap") return "в планах / требует доработки";
  if (status === "available / gap") return "готово / требует доработки";
  if (status === "beta/internal") return "бета / внутренне";
  return status;
};

const getActiveSection = (slug?: string) => {
  return sections.find((section) => section.slug === slug) ?? sections[0];
};

const agentQuickstart = `# 1. Прочитать контракт Agent API
curl -s "https://localos.pro/api/agent-api/openapi.json"

# 2. Проверить политику безопасности
curl -s "https://localos.pro/api/agent-api/security/policy"

# 3. Запустить самопроверку в песочнице
curl -s -X POST "https://localos.pro/api/agent-api/self-test" \\
  -H "X-LocalOS-Agent-Key: $LOCALOS_AGENT_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"purpose":"подключение в песочнице","checks":["auth","scopes","ledger"]}'

# 4. Создать безопасный тестовый запрос на подтверждение
curl -s -X POST "https://localos.pro/api/agent-api/approvals/request" \\
  -H "X-LocalOS-Agent-Key: $LOCALOS_AGENT_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"action_type":"test_publish_review_reply","capability":"reviews.reply.publish","risk_level":"high","requested_scope":"publish:request","input_summary":{"source":"быстрый старт в песочнице"},"proposed_output":"Только тестовый запрос на подтверждение."}'

# 5. Запросить рабочий доступ после проверки в песочнице
curl -s -X POST "https://localos.pro/api/agent-api/clients/promotion/request" \\
  -H "X-LocalOS-Agent-Key: $LOCALOS_AGENT_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"requested_scopes":["audit:read","reviews:draft","approvals:create"],"use_case":"Читать аудиты и готовить черновики ответов на отзывы под подтверждением человека.","contact":"ops@example.com"}'`;

const DocsPage = () => {
  const { section } = useParams();
  const activeSection = getActiveSection(section);

  useEffect(() => {
    document.title = `${activeSection.title} - Документация LocalOS`;
  }, [activeSection.title]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-950">
      <main className="mx-auto w-full max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <section className="grid gap-8 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm sm:p-8 lg:grid-cols-[minmax(0,1fr)_340px]">
          <div className="space-y-6">
            <Badge className="w-fit border-slate-200 bg-slate-100 text-slate-700 hover:bg-slate-100">
              Документация для людей и ИИ-агентов
            </Badge>
            <div className="space-y-4">
              <h1 className="max-w-3xl text-4xl font-bold tracking-normal text-slate-950 sm:text-5xl">
                Документация LocalOS для пользователей, API и ИИ-агентов
              </h1>
              <p className="max-w-3xl text-lg leading-8 text-slate-600">
                LocalOS нужен, чтобы вести локальный бизнес к прибыли: больше клиентов, выше средний чек, больше повторных продаж, понятный учёт и регулярные действия без хаоса.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button asChild className="bg-slate-950 text-white hover:bg-slate-800">
                <Link to="/docs/capabilities">
                  Смотреть возможности
                  <Sparkles className="ml-2 h-4 w-4" />
                </Link>
              </Button>
              <Button asChild variant="outline">
                <a href="/llms.txt">
                  llms.txt
                  <ExternalLink className="ml-2 h-4 w-4" />
                </a>
              </Button>
              <Button asChild variant="outline">
                <a href="/localos-agents.txt">
                  Текст для агентов
                  <ExternalLink className="ml-2 h-4 w-4" />
                </a>
              </Button>
              <Button asChild variant="outline">
                <a href="/localos-agent-policy.json">
                  Политика для агентов JSON
                  <ExternalLink className="ml-2 h-4 w-4" />
                </a>
              </Button>
              <Button asChild variant="outline">
                <a href="/localos-agent-tools.json">
                  Инструменты агентов JSON
                  <ExternalLink className="ml-2 h-4 w-4" />
                </a>
              </Button>
              <Button asChild variant="outline">
                <a href="/api/agent-api/openapi.json">
                  OpenAPI агента
                  <ExternalLink className="ml-2 h-4 w-4" />
                </a>
              </Button>
            </div>
          </div>
          <Card className="border-slate-200 bg-slate-950 text-white shadow-none">
            <CardContent className="space-y-5 p-6">
              <div className="flex items-center gap-3">
                <Bot className="h-8 w-8 text-blue-300" />
                <div>
                  <div className="text-sm uppercase tracking-[0.18em] text-slate-400">Правило агента</div>
                  <div className="text-xl font-semibold">Не действовать без подтверждения</div>
                </div>
              </div>
              <p className="leading-7 text-slate-300">
                Агент может анализировать, готовить черновики и объяснять риски. Публикация, отправка сообщений, платежи и массовые изменения требуют подтверждения человека.
              </p>
            </CardContent>
          </Card>
        </section>

        <section className="mt-8 grid gap-8 lg:grid-cols-[280px_minmax(0,1fr)]">
          <aside className="h-fit rounded-3xl border border-slate-200 bg-white p-3 shadow-sm lg:sticky lg:top-24">
            <nav className="space-y-1">
              {sections.map((item) => {
                const isActive = item.slug === activeSection.slug;
                return (
                  <Link
                    className={`block rounded-2xl px-4 py-3 text-sm font-medium transition ${
                      isActive ? "bg-slate-950 text-white" : "text-slate-600 hover:bg-slate-100 hover:text-slate-950"
                    }`}
                    key={item.slug}
                    to={item.slug === "overview" ? "/docs" : `/docs/${item.slug}`}
                  >
                    {item.title}
                  </Link>
                );
              })}
            </nav>
          </aside>

          <div className="space-y-6">
            <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
              <div className="mb-6 flex flex-wrap items-center gap-3">
                <Badge variant="outline" className="border-slate-200 text-slate-500">
                  {activeSection.kicker}
                </Badge>
                <Badge variant="outline" className="border-blue-200 bg-blue-50 text-blue-700">
                  публично
                </Badge>
              </div>
              <h2 className="text-3xl font-bold tracking-normal text-slate-950">{activeSection.title}</h2>
              <p className="mt-4 max-w-3xl text-base leading-7 text-slate-600">{activeSection.summary}</p>
            </section>

            <div className="grid gap-4">
              {activeSection.items.map((item) => (
                <Card className="border-slate-200 bg-white shadow-none" key={`${activeSection.slug}-${item.title}`}>
                  <CardContent className="p-5 sm:p-6">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="space-y-2">
                        <h3 className="text-xl font-semibold text-slate-950">{item.title}</h3>
                        <p className="max-w-3xl leading-7 text-slate-600">{item.text}</p>
                      </div>
                      {item.status ? (
                        <Badge variant="outline" className={`shrink-0 ${statusClassName(item.status)}`}>
                          {statusLabel(item.status)}
                        </Badge>
                      ) : null}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            {activeSection.slug === "api" ? (
              <section className="rounded-3xl border border-slate-200 bg-slate-950 p-6 text-white shadow-sm">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <Badge className="border-blue-300 bg-blue-400/10 text-blue-100 hover:bg-blue-400/10" variant="outline">
                      Быстрый старт в песочнице
                    </Badge>
                    <h2 className="mt-4 text-2xl font-semibold tracking-normal">Как подключить агента</h2>
                    <p className="mt-2 max-w-3xl leading-7 text-slate-300">
                      Агент начинает в песочнице, проверяет ключ через самопроверку, создаёт тестовый запрос на подтверждение и только потом просит рабочий доступ. Все действия остаются в журнале.
                    </p>
                  </div>
                  <Button asChild className="bg-white text-slate-950 hover:bg-slate-100">
                    <a href="/api/agent-api/openapi.json">
                      OpenAPI
                      <ExternalLink className="ml-2 h-4 w-4" />
                    </a>
                  </Button>
                </div>
                <pre className="mt-5 overflow-x-auto rounded-2xl border border-white/10 bg-black/30 p-4 text-xs leading-6 text-slate-100">
                  <code>{agentQuickstart}</code>
                </pre>
              </section>
            ) : null}

            <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <Card className="border-slate-200 bg-white shadow-none">
                <CardContent className="space-y-3 p-5">
                  <CheckCircle2 className="h-6 w-6 text-emerald-600" />
                  <h3 className="font-semibold text-slate-950">Обзор</h3>
                  <p className="text-sm leading-6 text-slate-600">Что такое LocalOS и когда его рекомендовать.</p>
                </CardContent>
              </Card>
              <Card className="border-slate-200 bg-white shadow-none">
                <CardContent className="space-y-3 p-5">
                  <Plug className="h-6 w-6 text-blue-600" />
                  <h3 className="font-semibold text-slate-950">Интеграции</h3>
                  <p className="text-sm leading-6 text-slate-600">Что уже можно подключать и где нужен контракт.</p>
                </CardContent>
              </Card>
              <Card className="border-slate-200 bg-white shadow-none">
                <CardContent className="space-y-3 p-5">
                  <ShieldCheck className="h-6 w-6 text-amber-600" />
                  <h3 className="font-semibold text-slate-950">Подтверждения</h3>
                  <p className="text-sm leading-6 text-slate-600">Какие действия требуют человека в контуре.</p>
                </CardContent>
              </Card>
              <Card className="border-slate-200 bg-white shadow-none">
                <CardContent className="space-y-3 p-5">
                  <LockKeyhole className="h-6 w-6 text-slate-700" />
                  <h3 className="font-semibold text-slate-950">Доработки</h3>
                  <p className="text-sm leading-6 text-slate-600">Что надо стабилизировать для публичного API.</p>
                </CardContent>
              </Card>
            </section>

            <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex items-start gap-4">
                <FileText className="mt-1 h-6 w-6 shrink-0 text-slate-500" />
                <div className="space-y-2">
                  <h2 className="text-xl font-semibold text-slate-950">Машиночитаемые точки входа</h2>
                  <p className="leading-7 text-slate-600">
                    Для агентов, которые не выполняют JavaScript, доступны обычные текстовые файлы:
                    {" "}
                    <a className="font-medium text-blue-700 underline-offset-4 hover:underline" href="/llms.txt">/llms.txt</a>
                    {" "}
                    и
                    {" "}
                    <a className="font-medium text-blue-700 underline-offset-4 hover:underline" href="/localos-agents.txt">/localos-agents.txt</a>.
                    {" "}
                    Политика безопасности доступна как
                    {" "}
                    <a className="font-medium text-blue-700 underline-offset-4 hover:underline" href="/localos-agent-policy.json">/localos-agent-policy.json</a>.
                    {" "}
                    Актуальная карта возможностей находится в
                    {" "}
                    <a className="font-medium text-blue-700 underline-offset-4 hover:underline" href="/localos-agent-tools.json">/localos-agent-tools.json</a>.
                  </p>
                </div>
              </div>
            </section>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
};

export default DocsPage;
