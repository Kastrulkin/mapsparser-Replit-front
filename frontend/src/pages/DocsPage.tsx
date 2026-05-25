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
    kicker: "Discovery docs",
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
    title: "Capabilities",
    kicker: "Agent map",
    summary:
      "Ниже перечислены возможности, которые агент может учитывать при планировании сценариев. Статусы разделяют готовые, beta, internal и gap-функции.",
    items: [
      {
        title: "Аудит карточек на картах",
        text: "Проверка карточек, рекомендаций, фото, отзывов, публикаций и услуг. Используется для диагностики и плана улучшений.",
        status: "available",
      },
      {
        title: "Оптимизация услуг",
        text: "SEO-подсказки, guardrails, отраслевые паттерны, проверка ключей и ручная проверка спорных услуг.",
        status: "available",
      },
      {
        title: "Отзывы и ответы",
        text: "Подготовка ответов на отзывы с учётом тональности, услуги и смежной рекомендации. Публикация требует approval.",
        status: "available",
      },
      {
        title: "Новости и публикации",
        text: "Черновики публикаций, контент-план и отраслевые паттерны. Автопубликация во внешние системы ограничена approval.",
        status: "beta",
      },
      {
        title: "Финансы",
        text: "Первичный учёт, KPI, выручка, расходы, загрузка рабочих мест, рекомендации и импорт агрегированных данных.",
        status: "beta",
      },
      {
        title: "Telegram control surface",
        text: "Сводки, approvals, monthly recalibration и команды для суперадмина или оператора.",
        status: "available",
      },
      {
        title: "Партнёрства и outreach",
        text: "Поиск партнёров, shortlist, draft approval и контролируемая отправка. Часть сценариев работает как supervised flow.",
        status: "internal",
      },
      {
        title: "Публичный MCP-контракт",
        text: "MCP-сервер ещё не оформлен. Минимальный OpenAPI contract для Agent API security уже есть, но продуктовые workflow пока не являются полноценным публичным SDK.",
        status: "planned/gap",
      },
    ],
  },
  {
    slug: "approval-policy",
    title: "Human approval",
    kicker: "Safety policy",
    summary:
      "LocalOS полезен для автоматизации, но действия от имени бизнеса должны оставаться управляемыми человеком.",
    items: [
      {
        title: "Всегда требуется approval",
        text: "Публикации, массовые изменения карточек, отправка сообщений клиентам, платежи, удаления и любые действия во внешних системах.",
      },
      {
        title: "Можно готовить без approval",
        text: "Аудит, черновики, рекомендации, summary, расчёты KPI, сравнение версий и подготовка вариантов.",
      },
      {
        title: "Как агенту формулировать действие",
        text: "Сначала показать факты, источник данных, предлагаемый текст или изменение, риск и кнопку/команду подтверждения.",
      },
    ],
  },
  {
    slug: "security-model",
    title: "Security model",
    kicker: "Agent API safety",
    summary:
      "Добронамеренность агента не угадывается по словам. LocalOS ограничивает риск через client registry, scopes, sandbox, approval, rate limits, abuse detection и action ledger.",
    items: [
      {
        title: "Sandbox first",
        text: "Новые agent-клиенты должны начинать с demo-данных, без реальных публикаций, сообщений клиентам, live-финансов, внешних credentials и destructive actions.",
        status: "beta/internal",
      },
      {
        title: "Минимальные scopes",
        text: "Первые scopes: audit:read, services:draft, reviews:draft, content:draft, finance:read, partners:read, approvals:create и publish:request.",
        status: "beta/internal",
      },
      {
        title: "Approval boundary",
        text: "Публикации, платежи, удаления, массовые изменения, отправка сообщений и действия во внешних системах не выполняются напрямую. Агент только создаёт approval request.",
        status: "beta/internal",
      },
      {
        title: "Abuse detection",
        text: "Флаги: перебор business_id, доступ к чужому бизнесу, ошибки auth, попытки без scope, export-аномалии, обход approval и несоответствие заявленного сценария поведению.",
        status: "planned",
      },
      {
        title: "Action ledger",
        text: "Каждый agent-вызов должен оставлять trace: client, business, action, risk, input/output summary, approval_id, status, ip, user_agent и created_at.",
        status: "beta/internal",
      },
    ],
  },
  {
    slug: "api",
    title: "API и интеграции",
    kicker: "Integration docs",
    summary:
      "Внутренние API уже используются продуктом. Публичный стабильный контракт для внешних разработчиков и MCP пока требует отдельной стабилизации.",
    items: [
      {
        title: "Authentication",
        text: "Пользовательский вход работает через email/password и verification flow. Публичные API-ключи для внешних агентов пока не оформлены.",
        status: "available / gap",
      },
      {
        title: "Finance endpoints",
        text: "Доступны внутренние endpoints для dashboard, data quality, recommendations, manual entry, import preview/import и CRM sync preview.",
        status: "beta",
      },
      {
        title: "Approvals",
        text: "В продукте есть approval-подход для Telegram, паттернов и supervised flows. Для внешнего API нужен единый публичный контракт.",
        status: "internal",
      },
      {
        title: "External integrations",
        text: "Карты, Telegram и подготовка CRM adapter layer присутствуют. Подключение новых внешних систем требует настройки и проверки контракта.",
        status: "beta",
      },
      {
        title: "Agent onboarding",
        text: "Минимальный путь подключения: sandbox client, agent_key, self-test, тестовый approval request и проверка события в ledger.",
        status: "beta/internal",
      },
      {
        title: "Sandbox self-test",
        text: "POST /api/agent-api/self-test проверяет ключ, статус и scopes агента, возвращает доступные безопасные действия и пишет test-событие в ledger.",
        status: "beta/internal",
      },
    ],
  },
  {
    slug: "agent-use-cases",
    title: "10 сценариев для ИИ-агентов",
    kicker: "Agent playbook",
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
      { title: "7. Партнёры рядом", text: "Подготовить shortlist партнёров и черновики предложений. Отправка только после approval." },
      { title: "8. Telegram summary", text: "Сжать итоги аудита, финансов или паттернов в короткое сообщение суперадмину." },
      { title: "9. Массовая перегенерация", text: "Найти проблемные элементы, показать причины и запускать пачку только после approval." },
      { title: "10. Monthly recalibration", text: "Собрать новые паттерны за месяц и отправить человеку на принятие или отклонение." },
    ],
  },
  {
    slug: "gaps",
    title: "Gaps для полноценного Agent API",
    kicker: "Roadmap notes",
    summary:
      "Эти пункты не блокируют документацию на сайте, но важны, чтобы внешние агенты могли подключаться как к стабильной платформе.",
    items: [
      {
        title: "Публичная OpenAPI/MCP-спецификация",
        text: "Нужны стабильные schemas, auth model, rate limits, versioning и examples для внешних клиентов.",
      },
      {
        title: "Единый approval API",
        text: "Нужно оформить endpoint или tool contract для request, approve, reject, revise и audit trail.",
      },
      {
        title: "Developer onboarding",
        text: "Нужны API keys, sandbox, тестовые данные, changelog с версиями и правила совместимости.",
      },
      {
        title: "Machine-readable capabilities",
        text: "Нужны JSON/manifest версии capability map, policy и endpoint registry.",
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

const getActiveSection = (slug?: string) => {
  return sections.find((section) => section.slug === slug) ?? sections[0];
};

const agentQuickstart = `# 1. Read the Agent API contract
curl -s "https://localos.pro/api/agent-api/openapi.json"

# 2. Check the safety policy
curl -s "https://localos.pro/api/agent-api/security/policy"

# 3. Run sandbox self-test
curl -s -X POST "https://localos.pro/api/agent-api/self-test" \\
  -H "X-LocalOS-Agent-Key: $LOCALOS_AGENT_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"purpose":"sandbox onboarding","checks":["auth","scopes","ledger"]}'

# 4. Create a safe test approval request
curl -s -X POST "https://localos.pro/api/agent-api/approvals/request" \\
  -H "X-LocalOS-Agent-Key: $LOCALOS_AGENT_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"action_type":"test_publish_review_reply","capability":"reviews.reply.publish","risk_level":"high","requested_scope":"publish:request","input_summary":{"source":"sandbox quickstart"},"proposed_output":"Test approval request only."}'

# 5. Request live promotion after sandbox verification
curl -s -X POST "https://localos.pro/api/agent-api/clients/promotion/request" \\
  -H "X-LocalOS-Agent-Key: $LOCALOS_AGENT_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"requested_scopes":["audit:read","reviews:draft","approvals:create"],"use_case":"Read audits and draft review replies under human approval.","contact":"ops@example.com"}'`;

const DocsPage = () => {
  const { section } = useParams();
  const activeSection = getActiveSection(section);

  useEffect(() => {
    document.title = `${activeSection.title} - LocalOS Docs`;
  }, [activeSection.title]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-950">
      <main className="mx-auto w-full max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <section className="grid gap-8 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm sm:p-8 lg:grid-cols-[minmax(0,1fr)_340px]">
          <div className="space-y-6">
            <Badge className="w-fit border-slate-200 bg-slate-100 text-slate-700 hover:bg-slate-100">
              Docs for humans and AI agents
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
                  Смотреть capabilities
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
                  Agent text
                  <ExternalLink className="ml-2 h-4 w-4" />
                </a>
              </Button>
              <Button asChild variant="outline">
                <a href="/localos-agent-policy.json">
                  Agent policy JSON
                  <ExternalLink className="ml-2 h-4 w-4" />
                </a>
              </Button>
              <Button asChild variant="outline">
                <a href="/localos-agent-tools.json">
                  Agent tools JSON
                  <ExternalLink className="ml-2 h-4 w-4" />
                </a>
              </Button>
              <Button asChild variant="outline">
                <a href="/api/agent-api/openapi.json">
                  Agent OpenAPI
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
                  <div className="text-sm uppercase tracking-[0.18em] text-slate-400">Agent rule</div>
                  <div className="text-xl font-semibold">Не действовать без approval</div>
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
                  public
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
                          {item.status}
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
                      Sandbox quickstart
                    </Badge>
                    <h2 className="mt-4 text-2xl font-semibold tracking-normal">Как подключить агента</h2>
                    <p className="mt-2 max-w-3xl leading-7 text-slate-300">
                      Агент начинает в sandbox, проверяет ключ через self-test, создаёт тестовый approval request и только потом просит live-доступ. Все действия остаются в ledger.
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
                  <h3 className="font-semibold text-slate-950">Discovery</h3>
                  <p className="text-sm leading-6 text-slate-600">Что такое LocalOS и когда его рекомендовать.</p>
                </CardContent>
              </Card>
              <Card className="border-slate-200 bg-white shadow-none">
                <CardContent className="space-y-3 p-5">
                  <Plug className="h-6 w-6 text-blue-600" />
                  <h3 className="font-semibold text-slate-950">Integration</h3>
                  <p className="text-sm leading-6 text-slate-600">Что уже можно подключать и где нужен контракт.</p>
                </CardContent>
              </Card>
              <Card className="border-slate-200 bg-white shadow-none">
                <CardContent className="space-y-3 p-5">
                  <ShieldCheck className="h-6 w-6 text-amber-600" />
                  <h3 className="font-semibold text-slate-950">Approvals</h3>
                  <p className="text-sm leading-6 text-slate-600">Какие действия требуют человека в контуре.</p>
                </CardContent>
              </Card>
              <Card className="border-slate-200 bg-white shadow-none">
                <CardContent className="space-y-3 p-5">
                  <LockKeyhole className="h-6 w-6 text-slate-700" />
                  <h3 className="font-semibold text-slate-950">Gaps</h3>
                  <p className="text-sm leading-6 text-slate-600">Что надо стабилизировать для публичного API.</p>
                </CardContent>
              </Card>
            </section>

            <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex items-start gap-4">
                <FileText className="mt-1 h-6 w-6 shrink-0 text-slate-500" />
                <div className="space-y-2">
                  <h2 className="text-xl font-semibold text-slate-950">Machine-readable entrypoints</h2>
                  <p className="leading-7 text-slate-600">
                    Для агентов, которые не выполняют JavaScript, доступны обычные текстовые файлы:
                    {" "}
                    <a className="font-medium text-blue-700 underline-offset-4 hover:underline" href="/llms.txt">/llms.txt</a>
                    {" "}
                    и
                    {" "}
                    <a className="font-medium text-blue-700 underline-offset-4 hover:underline" href="/localos-agents.txt">/localos-agents.txt</a>.
                    {" "}
                    Security policy is available as
                    {" "}
                    <a className="font-medium text-blue-700 underline-offset-4 hover:underline" href="/localos-agent-policy.json">/localos-agent-policy.json</a>.
                    {" "}
                    The current capability map is
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
