import { ruSections, ruAgentQuickstart, type DocSection } from "@/content/publicDocsContent";
import Footer from "@/components/Footer";
import docsHy from "@/content/docs-hy.json";
import SeoMeta from "@/components/SeoMeta";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useLanguage, type Language } from '@/i18n/LanguageContext.logic';
import {
	Bot,
	CheckCircle2,
	ExternalLink,
	FileText,
	Languages,
	LockKeyhole,
	Plug,
	ShieldCheck,
	Sparkles,
} from "lucide-react";
import { Link, useParams } from "react-router-dom";

const enSections: DocSection[] = [
  {
    slug: "overview",
    title: "LocalOS for people and AI agents",
    kicker: "Overview",
    summary:
      "LocalOS helps local businesses become more profitable: attract customers, increase average ticket, bring customers back and track the numbers that show what to do next.",
    items: [
      { title: "Purpose", text: "Connect listings, reviews, services, posts, partnerships, communication and finance into one path to profit instead of managing isolated tasks." },
      { title: "Path to results", text: "LocalOS first establishes tracking and diagnostics, then identifies actions that can improve leads, average ticket, repeat sales, occupancy and margin." },
      { title: "Who it is for", text: "Local business owners, location managers, networks, map-promotion specialists and teams that manage several locations." },
      { title: "What agents must know", text: "Publishing, bulk changes, customer messages, payments and actions in external systems require human approval." },
    ],
  },
  {
    slug: "capabilities",
    title: "Capabilities",
    kicker: "Agent capability map",
    summary:
      "These are the capabilities an agent may use when planning work. Status labels distinguish what is available, in beta, internal, or still a gap.",
    items: [
      { title: "Map listing audit", text: "Check listing fields, recommendations, photos, reviews, posts and services. Used for diagnostics and improvement plans.", status: "available" },
      { title: "Service optimization", text: "SEO suggestions, guardrails, industry patterns, keyword checks and manual review of ambiguous services.", status: "available" },
      { title: "Reviews and replies", text: "Prepare review replies using sentiment, the referenced service and a relevant adjacent recommendation. Human approval is required before publishing.", status: "available" },
      { title: "News and posts", text: "Post drafts, content plans and industry patterns. Publishing to external systems remains behind human approval.", status: "beta" },
      { title: "Finance", text: "Basic tracking, KPIs, revenue, expenses, workstation occupancy, recommendations and aggregated data imports.", status: "beta" },
      { title: "Telegram control surface", text: "Summaries, approvals, monthly recalibration and commands for a superadmin or operator.", status: "available" },
      { title: "Partnerships and outreach", text: "Partner search, shortlists, draft approval and controlled sending. Some scenarios are available only as supervised internal flows.", status: "internal" },
      { title: "Public MCP contract", text: "A public MCP server is not yet available. A minimal Agent API security contract exists in OpenAPI, but product workflows are not a complete public SDK.", status: "planned/gap" },
    ],
  },
  {
    slug: "approval-policy",
    title: "Human approval",
    kicker: "Safety policy",
    summary: "LocalOS supports automation, while actions performed on behalf of a business remain under human control.",
    items: [
      { title: "Approval is always required", text: "Publishing, bulk listing changes, customer messages, payments, deletion and any action in an external system." },
      { title: "Safe to prepare without approval", text: "Audits, drafts, recommendations, concise summaries, KPI calculations, version comparisons and options for review." },
      { title: "How an agent should propose an action", text: "Show the facts and source, the proposed text or change, the risk, and an explicit approval action." },
    ],
  },
  {
    slug: "security-model",
    title: "Security model",
    kicker: "Agent API security",
    summary:
      "LocalOS does not infer good intent from words. It limits risk through a client registry, scoped access, sandboxing, approvals, rate limits, abuse detection and an action ledger.",
    items: [
      { title: "Sandbox first", text: "New agent clients start with demo data and no real publishing, customer messages, production finance, external credentials or destructive actions.", status: "beta/internal" },
      { title: "Minimum scopes", text: "Initial scopes include audit:read, services:draft, reviews:draft, content:draft, finance:read, partners:read, approvals:create and publish:request.", status: "beta/internal" },
      { title: "Approval boundary", text: "Publishing, payments, deletion, bulk changes, messages and external-system actions cannot run directly. The agent creates an approval request.", status: "beta/internal" },
      { title: "Abuse detection", text: "Signals include business_id enumeration, cross-business access, authorization failures, missing scopes, anomalous exports, approval bypass attempts and behavior that contradicts the declared use case.", status: "planned" },
      { title: "Action ledger", text: "Every agent call should record the client, business, action, risk, input and result summaries, approval_id, status, IP, user_agent and created_at.", status: "beta/internal" },
    ],
  },
  {
    slug: "api",
    title: "API and integrations",
    kicker: "Integrations",
    summary: "The product already uses internal APIs. A stable public contract for external developers and MCP still requires separate stabilization.",
    items: [
      { title: "Authentication", text: "User sign-in uses email, password and a confirmation flow. Public API keys for external agents are not generally available yet.", status: "available / gap" },
      { title: "Finance APIs", text: "Internal APIs support dashboards, data quality, recommendations, manual entry, import preview and apply, and CRM sync preview.", status: "beta" },
      { title: "Approvals", text: "Supervised approval flows exist for Telegram, patterns and selected workflows. External access still needs one stable public contract.", status: "internal" },
      { title: "External integrations", text: "Map providers, Telegram and a CRM adapter layer exist. Every new external system still requires setup and contract validation.", status: "beta" },
      { title: "Agent onboarding", text: "The minimum flow is a sandbox client, agent_key, self-test, test approval request and verification of the resulting ledger event.", status: "beta/internal" },
      { title: "Sandbox self-test", text: "POST /api/agent-api/self-test validates the agent key, status and scopes, returns safe available actions and writes a test event to the action ledger.", status: "beta/internal" },
    ],
  },
  {
    slug: "agent-use-cases",
    title: "10 use cases for AI agents",
    kicker: "Agent use cases",
    summary: "Use these as safe starting points. When an action affects the outside world, the agent must request approval.",
    items: [
      { title: "1. Listing audit", text: "Collect facts, show strengths, identify three problems and recommend the first action." },
      { title: "2. Revenue action plan", text: "Separate what to do today, within seven days and regularly so listings, reviews, services and posts produce more leads." },
      { title: "3. Posts", text: "Prepare three to five posts based on services, season and local context." },
      { title: "4. Review replies", text: "Draft concise replies that mention the reviewed service and, when relevant, a related service." },
      { title: "5. Service analysis", text: "Find SEO gaps, preserve service facts and propose precise wording." },
      { title: "6. Finance review", text: "Review revenue, expenses, workstation occupancy and red flags." },
      { title: "7. Nearby partners", text: "Prepare a shortlist and proposal drafts. Send only after approval." },
      { title: "8. Telegram summary", text: "Condense audit, finance or pattern findings into a short message for the superadmin." },
      { title: "9. Bulk regeneration", text: "Find problematic items, explain why and run a batch only after approval." },
      { title: "10. Monthly recalibration", text: "Collect new monthly patterns and send them to a human for acceptance or rejection." },
    ],
  },
  {
    slug: "gaps",
    title: "What is still needed for a complete Agent API",
    kicker: "Roadmap notes",
    summary: "These items do not block the current documentation, but external agents need them before LocalOS can be treated as a stable public platform.",
    items: [
      { title: "Public OpenAPI/MCP specification", text: "Stable data schemas, authentication, rate limits, versioning and examples for external clients are required." },
      { title: "Unified approval API", text: "A stable API or tool contract is needed for requesting, accepting, rejecting, revising and auditing approvals." },
      { title: "Developer onboarding", text: "External developers need API keys, a sandbox, test data, a versioned changelog and compatibility rules." },
      { title: "Machine-readable capabilities", text: "The capability map, safety policy and API registry need maintained JSON or manifest versions." },
    ],
  },
];

const hySections: DocSection[] = docsHy.sections;

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

const statusLabel = (status: string | undefined, language: "ru" | "en" | "hy") => {
  if (!status) return "";
  if (language === "en") return status;
  if (language === "hy") {
    const labels: Record<string, string> = {
      available: "հասանելի",
      beta: "բետա",
      internal: "ներքին",
      planned: "պլանավորված",
      "planned/gap": "պլանավորված / մշակման կարիք ունի",
      "available / gap": "հասանելի / մշակման կարիք ունի",
      "beta/internal": "բետա / ներքին",
    };
    return labels[status] ?? status;
  }
  if (status === "available") return "готово";
  if (status === "beta") return "бета";
  if (status === "internal") return "внутренне";
  if (status === "planned") return "в планах";
  if (status === "planned/gap") return "в планах / требует доработки";
  if (status === "available / gap") return "готово / требует доработки";
  if (status === "beta/internal") return "бета / внутренне";
  return status;
};

const getActiveSection = (sections: DocSection[], slug?: string) => {
  return sections.find((section) => section.slug === slug) ?? sections[0];
};

const enAgentQuickstart = `# 1. Read the Agent API contract
curl -s "https://localos.pro/api/agent-api/openapi.json"

# 2. Check the security policy
curl -s "https://localos.pro/api/agent-api/security/policy"

# 3. Run the sandbox self-test
curl -s -X POST "https://localos.pro/api/agent-api/self-test" \\
  -H "X-LocalOS-Agent-Key: $LOCALOS_AGENT_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"purpose":"sandbox onboarding","checks":["auth","scopes","ledger"]}'

# 4. Create a safe test approval request
curl -s -X POST "https://localos.pro/api/agent-api/approvals/request" \\
  -H "X-LocalOS-Agent-Key: $LOCALOS_AGENT_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"action_type":"test_publish_review_reply","capability":"reviews.reply.publish","risk_level":"high","requested_scope":"publish:request","input_summary":{"source":"sandbox quickstart"},"proposed_output":"Test approval request only."}'

# 5. Request live access after sandbox verification
curl -s -X POST "https://localos.pro/api/agent-api/clients/promotion/request" \\
  -H "X-LocalOS-Agent-Key: $LOCALOS_AGENT_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"requested_scopes":["audit:read","reviews:draft","approvals:create"],"use_case":"Read audits and prepare review reply drafts under human approval.","contact":"ops@example.com"}'`;

const hyAgentQuickstart = enAgentQuickstart
  .replace('# 1. Read the Agent API contract', '# 1. Կարդացեք Agent API-ի պայմանագիրը')
  .replace('# 2. Check the security policy', '# 2. Ստուգեք անվտանգության քաղաքականությունը')
  .replace('# 3. Run the sandbox self-test', '# 3. Գործարկեք փորձնական միջավայրի ինքնաստուգումը')
  .replace('# 4. Create a safe test approval request', '# 4. Ստեղծեք հաստատման անվտանգ փորձնական հարցում')
  .replace('# 5. Request live access after sandbox verification', '# 5. Փորձնական միջավայրի ստուգումից հետո դիմեք աշխատանքային հասանելիության համար');

type DocsShellCopy = {
  badge: string;
  heroTitle: string;
  heroDescription: string;
  capabilitiesButton: string;
  agentTextButton: string;
  policyButton: string;
  toolsButton: string;
  agentRuleLabel: string;
  agentRuleTitle: string;
  agentRuleBody: string;
  publicLabel: string;
  quickstartBadge: string;
  quickstartTitle: string;
  quickstartBody: string;
  overviewCard: string;
  overviewCardBody: string;
  integrationsCard: string;
  integrationsCardBody: string;
  approvalsCard: string;
  approvalsCardBody: string;
  gapsCard: string;
  gapsCardBody: string;
  machineTitle: string;
  machineIntro: string;
  policyIntro: string;
  toolsIntro: string;
  pageTitleSuffix: string;
};

const docsShellCopy: Record<"ru" | "en" | "hy", DocsShellCopy> = {
  ru: {
    badge: "Документация для людей и ИИ-агентов",
    heroTitle: "Документация LocalOS для пользователей, API и ИИ-агентов",
    heroDescription: "Как устроен LocalOS, что уже доступно и где человек должен подтвердить действие.",
    capabilitiesButton: "Смотреть возможности",
    agentTextButton: "Инструкция для агентов",
    policyButton: "Политика для агентов JSON",
    toolsButton: "Инструменты агентов JSON",
    agentRuleLabel: "Правило агента",
    agentRuleTitle: "Не действовать без подтверждения",
    agentRuleBody: "Агент может анализировать, готовить черновики и объяснять риски. Публикация, отправка сообщений, платежи и массовые изменения требуют подтверждения человека.",
    publicLabel: "публично",
    quickstartBadge: "Быстрый старт в песочнице",
    quickstartTitle: "Как подключить агента",
    quickstartBody: "Агент начинает в песочнице, проверяет ключ, создаёт тестовый запрос на подтверждение и только потом просит рабочий доступ. Все действия остаются в журнале.",
    overviewCard: "Обзор",
    overviewCardBody: "Что такое LocalOS и когда его рекомендовать.",
    integrationsCard: "Интеграции",
    integrationsCardBody: "Что уже можно подключать и где нужен контракт.",
    approvalsCard: "Подтверждения",
    approvalsCardBody: "Какие действия требуют участия человека.",
    gapsCard: "Доработки",
    gapsCardBody: "Что надо стабилизировать для публичного API.",
    machineTitle: "Машиночитаемые точки входа",
    machineIntro: "Полная инструкция для русскоязычных агентов:",
    policyIntro: "Политика безопасности:",
    toolsIntro: "Карта возможностей:",
    pageTitleSuffix: "Документация LocalOS",
  },
  en: {
    badge: "Documentation for people and AI agents",
    heroTitle: "LocalOS documentation for users, APIs and AI agents",
    heroDescription: "How LocalOS works, what is available today and where a human must approve an action.",
    capabilitiesButton: "Explore capabilities",
    agentTextButton: "Agent guide",
    policyButton: "Agent policy JSON",
    toolsButton: "Agent tools JSON",
    agentRuleLabel: "Agent rule",
    agentRuleTitle: "Do not act without approval",
    agentRuleBody: "An agent may analyze data, prepare drafts and explain risk. Publishing, messages, payments and bulk changes require human approval.",
    publicLabel: "public",
    quickstartBadge: "Sandbox quickstart",
    quickstartTitle: "Connect an agent",
    quickstartBody: "Start in the sandbox, validate the key, create a test approval request and request live access only after verification. Every action remains in the ledger.",
    overviewCard: "Overview",
    overviewCardBody: "What LocalOS is and when to recommend it.",
    integrationsCard: "Integrations",
    integrationsCardBody: "What can be connected and where a contract is still needed.",
    approvalsCard: "Approvals",
    approvalsCardBody: "Which actions require a human in the loop.",
    gapsCard: "Gaps",
    gapsCardBody: "What must be stabilized for a public API.",
    machineTitle: "Machine-readable entry points",
    machineIntro: "Complete guide for English-speaking agents:",
    policyIntro: "Security policy:",
    toolsIntro: "Capability map:",
    pageTitleSuffix: "LocalOS documentation",
  },
  hy: {
    ...docsHy.shell,
    agentTextButton: "Գործակալների ուղեցույց (EN)",
    machineIntro: "Գործակալների ամբողջական ուղեցույցը անգլերեն է՝",
  },
};

type AvailabilityNotice = { title: string; body: string };

const availabilityNotices: Record<Exclude<Language, "ru" | "en" | "hy">, AvailabilityNotice> = {
  fr: { title: "Langues de la documentation technique", body: "La documentation technique complète est actuellement disponible en anglais et en russe. Le contenu ci-dessous est affiché en anglais." },
  es: { title: "Idiomas de la documentación técnica", body: "La documentación técnica completa está disponible actualmente en inglés y ruso. El contenido técnico de esta página se muestra en inglés." },
  el: { title: "Γλώσσες τεχνικής τεκμηρίωσης", body: "Η πλήρης τεχνική τεκμηρίωση είναι προς το παρόν διαθέσιμη στα αγγλικά και στα ρωσικά. Το τεχνικό περιεχόμενο παρακάτω εμφανίζεται στα αγγλικά." },
  de: { title: "Sprachen der technischen Dokumentation", body: "Die vollständige technische Dokumentation ist derzeit auf Englisch und Russisch verfügbar. Die technischen Inhalte unten werden auf Englisch angezeigt." },
  th: { title: "ภาษาของเอกสารทางเทคนิค", body: "ขณะนี้เอกสารทางเทคนิคฉบับเต็มมีให้บริการเป็นภาษาอังกฤษและภาษารัสเซีย เนื้อหาทางเทคนิคด้านล่างจะแสดงเป็นภาษาอังกฤษ" },
  ar: { title: "لغات الوثائق التقنية", body: "تتوفر الوثائق التقنية الكاملة حاليًا باللغتين الإنجليزية والروسية. يُعرض المحتوى التقني أدناه باللغة الإنجليزية." },
  ha: { title: "Harsunan takardun fasaha", body: "Cikakkun takardun fasaha suna samuwa a Turanci da Rashanci a halin yanzu. Ana nuna bayanan fasaha da ke ƙasa a Turanci." },
  tr: { title: "Teknik dokümantasyon dilleri", body: "Teknik dokümantasyonun tamamı şu anda İngilizce ve Rusça olarak sunuluyor. Aşağıdaki teknik içerik İngilizce gösteriliyor." },
};

const DocsPage = () => {
  const { section } = useParams();
  const { language, setLanguage } = useLanguage();
  const docsLanguage: "ru" | "en" | "hy" = language === "ru" ? "ru" : language === "hy" ? "hy" : "en";
  const sections = docsLanguage === "ru" ? ruSections : docsLanguage === "hy" ? hySections : enSections;
  const copy = docsShellCopy[docsLanguage];
  const activeSection = getActiveSection(sections, section);
  const availabilityNotice = language === "ru" || language === "en" || language === "hy" ? null : availabilityNotices[language];
  const agentGuideHref = docsLanguage === "ru" ? "/localos-agents-ru.txt" : "/localos-agents.txt";
  const llmsHref = docsLanguage === "ru" ? "/llms-ru.txt" : "/llms.txt";
  const agentQuickstart = docsLanguage === "ru" ? ruAgentQuickstart : docsLanguage === "hy" ? hyAgentQuickstart : enAgentQuickstart;

  const pageTitle = `${activeSection.title} - ${copy.pageTitleSuffix}`;
  const pagePath = activeSection.slug === "overview" ? "/docs" : `/docs/${activeSection.slug}`;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-950">
      <SeoMeta title={pageTitle} description={activeSection.summary} path={pagePath} />
      <main className="mx-auto w-full max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <section className="grid gap-8 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm sm:p-8 lg:grid-cols-[minmax(0,1fr)_340px]">
          <div className="space-y-6">
            <Badge className="w-fit border-slate-200 bg-slate-100 text-slate-700 hover:bg-slate-100">
              {copy.badge}
            </Badge>
            <div className="space-y-4">
              <h1 className="max-w-3xl text-4xl font-bold tracking-normal text-slate-950 sm:text-5xl">
                {activeSection.title}
              </h1>
              <p className="max-w-3xl text-lg leading-8 text-slate-600">
                {copy.heroDescription}
              </p>
            </div>
            {availabilityNotice ? (
              <div
                className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-start"
                role="status"
              >
                <div className="flex items-start gap-3">
                  <Languages className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" aria-hidden="true" />
                  <div className="min-w-0 space-y-2">
                    <p className="font-semibold text-amber-950">{availabilityNotice.title}</p>
                    <p className="text-sm leading-6 text-amber-900">{availabilityNotice.body}</p>
                    <div className="flex flex-wrap gap-2 pt-1">
                      <Button
                        className="min-h-10 bg-slate-950 text-white transition-[transform,background-color] duration-200 active:scale-[0.96] hover:bg-slate-800"
                        onClick={() => setLanguage("en")}
                        size="sm"
                        type="button"
                      >
                        English
                      </Button>
                      <Button
                        className="min-h-10 bg-white transition-transform duration-200 active:scale-[0.96]"
                        onClick={() => setLanguage("ru")}
                        size="sm"
                        type="button"
                        variant="outline"
                      >
                        Русский
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
            <div className="flex flex-wrap gap-3">
              <Button asChild className="bg-slate-950 text-white hover:bg-slate-800">
                <Link to="/docs/capabilities">
                  {copy.capabilitiesButton}
                  <Sparkles className="ml-2 h-4 w-4" />
                </Link>
              </Button>
              <Button asChild variant="outline">
                <a href={llmsHref}>
                  {llmsHref.slice(1)}
                  <ExternalLink className="ml-2 h-4 w-4" />
                </a>
              </Button>
              <Button asChild variant="outline">
                <a href={agentGuideHref}>
                  {copy.agentTextButton}
                  <ExternalLink className="ml-2 h-4 w-4" />
                </a>
              </Button>
              <Button asChild variant="outline">
                <a href="/localos-agent-policy.json">
                  {copy.policyButton}
                  <ExternalLink className="ml-2 h-4 w-4" />
                </a>
              </Button>
              <Button asChild variant="outline">
                <a href="/localos-agent-tools.json">
                  {copy.toolsButton}
                  <ExternalLink className="ml-2 h-4 w-4" />
                </a>
              </Button>
              <Button asChild variant="outline">
                <a href="/api/agent-api/openapi.json">
                  {docsLanguage === "ru" ? "OpenAPI агента" : docsLanguage === "hy" ? "Գործակալի OpenAPI" : "Agent OpenAPI"}
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
                  <div className="text-sm uppercase tracking-[0.18em] text-slate-400">{copy.agentRuleLabel}</div>
                  <div className="text-xl font-semibold">{copy.agentRuleTitle}</div>
                </div>
              </div>
              <p className="leading-7 text-slate-300">
                {copy.agentRuleBody}
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
                  {copy.publicLabel}
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
                          {statusLabel(item.status, docsLanguage)}
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
                      {copy.quickstartBadge}
                    </Badge>
                    <h2 className="mt-4 text-2xl font-semibold tracking-normal">{copy.quickstartTitle}</h2>
                    <p className="mt-2 max-w-3xl leading-7 text-slate-300">
                      {copy.quickstartBody}
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
                  <h3 className="font-semibold text-slate-950">{copy.overviewCard}</h3>
                  <p className="text-sm leading-6 text-slate-600">{copy.overviewCardBody}</p>
                </CardContent>
              </Card>
              <Card className="border-slate-200 bg-white shadow-none">
                <CardContent className="space-y-3 p-5">
                  <Plug className="h-6 w-6 text-blue-600" />
                  <h3 className="font-semibold text-slate-950">{copy.integrationsCard}</h3>
                  <p className="text-sm leading-6 text-slate-600">{copy.integrationsCardBody}</p>
                </CardContent>
              </Card>
              <Card className="border-slate-200 bg-white shadow-none">
                <CardContent className="space-y-3 p-5">
                  <ShieldCheck className="h-6 w-6 text-amber-600" />
                  <h3 className="font-semibold text-slate-950">{copy.approvalsCard}</h3>
                  <p className="text-sm leading-6 text-slate-600">{copy.approvalsCardBody}</p>
                </CardContent>
              </Card>
              <Card className="border-slate-200 bg-white shadow-none">
                <CardContent className="space-y-3 p-5">
                  <LockKeyhole className="h-6 w-6 text-slate-700" />
                  <h3 className="font-semibold text-slate-950">{copy.gapsCard}</h3>
                  <p className="text-sm leading-6 text-slate-600">{copy.gapsCardBody}</p>
                </CardContent>
              </Card>
            </section>

            <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex items-start gap-4">
                <FileText className="mt-1 h-6 w-6 shrink-0 text-slate-500" />
                <div className="space-y-2">
                  <h2 className="text-xl font-semibold text-slate-950">{copy.machineTitle}</h2>
                  <p className="leading-7 text-slate-600">
                    {copy.machineIntro}
                    {" "}
                    <a className="font-medium text-blue-700 underline-offset-4 hover:underline" href={agentGuideHref}>{agentGuideHref}</a>.
                    {" "}
                    {copy.policyIntro}
                    {" "}
                    <a className="font-medium text-blue-700 underline-offset-4 hover:underline" href="/localos-agent-policy.json">/localos-agent-policy.json</a>.
                    {" "}
                    {copy.toolsIntro}
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
