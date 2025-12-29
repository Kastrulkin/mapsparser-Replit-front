import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { CheckCircle2, Circle, ExternalLink, Copy, Check, Sparkles, AlertCircle } from 'lucide-react';
import { useToast } from '../../hooks/use-toast';

interface Step {
  id: number;
  title: string;
  description: string;
  details: string[];
  links?: { text: string; url: string }[];
  codeExample?: string;
}

const steps: Step[] = [
  {
    id: 1,
    title: 'Добавить сайт в Bing Webmaster',
    description: 'Bing Webmaster помогает ChatGPT находить ваш сайт в интернете',
    details: [
      'Зарегистрируйтесь на bing.com/webmasters',
      'Добавьте ваш сайт через "Добавить сайт"',
      'Подтвердите владение сайтом (через HTML-тег, файл или DNS)',
      'Отправьте карту сайта (sitemap.xml)',
      'Дождитесь индексации (обычно 1-2 недели)'
    ],
    links: [
      { text: 'Bing Webmaster Tools', url: 'https://www.bing.com/webmasters' },
      { text: 'Инструкция по добавлению сайта', url: 'https://www.bing.com/webmasters/help/how-to-add-and-verify-your-site-9e8f4b8a' }
    ]
  },
  {
    id: 2,
    title: 'Сделать разметку Schema.org',
    description: 'Структурированные данные помогают ChatGPT лучше понимать ваш контент',
    details: [
      'Добавьте JSON-LD разметку на страницы сайта',
      'Используйте типы: LocalBusiness, Service, FAQPage, Article',
      'Укажите название, адрес, телефон, услуги, цены',
      'Добавьте разметку для отзывов и рейтингов',
      'Проверьте разметку через Google Rich Results Test'
    ],
    links: [
      { text: 'Schema.org для бизнеса', url: 'https://schema.org/LocalBusiness' },
      { text: 'Google Rich Results Test', url: 'https://search.google.com/test/rich-results' },
      { text: 'Генератор Schema.org', url: 'https://schema.org/docs/gs.html' }
    ],
    codeExample: `{
  "@context": "https://schema.org",
  "@type": "LocalBusiness",
  "name": "Название вашего салона",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "Улица, дом",
    "addressLocality": "Город",
    "postalCode": "123456"
  },
  "telephone": "+7-XXX-XXX-XX-XX",
  "priceRange": "$$",
  "servesCuisine": "Косметология, Парикмахерские услуги"
}`
  },
  {
    id: 3,
    title: 'Добавить блок FAQ',
    description: 'ChatGPT любит сайты с ответами на частые вопросы',
    details: [
      'Создайте страницу "Часто задаваемые вопросы"',
      'Добавьте минимум 10-15 вопросов и ответов',
      'Используйте разметку FAQPage (Schema.org)',
      'Включите вопросы о: услугах, ценах, записи, мастерах, акциях',
      'Регулярно обновляйте FAQ новыми вопросами'
    ],
    links: [
      { text: 'Schema.org FAQPage', url: 'https://schema.org/FAQPage' },
      { text: 'Примеры FAQ для салонов', url: 'https://schema.org/docs/gs.html' }
    ],
    codeExample: `{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [{
    "@type": "Question",
    "name": "Какие услуги вы предоставляете?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "Мы предоставляем услуги косметологии, парикмахерские услуги..."
    }
  }]
}`
  },
  {
    id: 4,
    title: 'Ссылаться на исследования',
    description: 'ChatGPT предпочитает сайты, которые выглядят как энциклопедии с источниками',
    details: [
      'Добавьте раздел "Исследования" или "Статьи" на сайте',
      'Пишите статьи о ваших услугах с ссылками на источники',
      'Ссылайтесь на научные исследования, медицинские источники',
      'Добавьте раздел "О нас" с историей, достижениями, сертификатами',
      'Публикуйте кейсы, отзывы клиентов, фото до/после'
    ],
    links: [
      { text: 'Как писать контент для AI', url: 'https://developers.google.com/search/docs/fundamentals/creating-helpful-content' }
    ]
  }
];

export const AIChatPromotionPage: React.FC = () => {
  const [completedSteps, setCompletedSteps] = useState<Set<number>>(new Set());
  const [copiedCode, setCopiedCode] = useState<number | null>(null);
  const { toast } = useToast();

  const toggleStep = (stepId: number) => {
    const newCompleted = new Set(completedSteps);
    if (newCompleted.has(stepId)) {
      newCompleted.delete(stepId);
    } else {
      newCompleted.add(stepId);
    }
    setCompletedSteps(newCompleted);
  };

  const copyCode = (code: string, stepId: number) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(stepId);
    toast({
      title: 'Скопировано!',
      description: 'Код скопирован в буфер обмена',
    });
    setTimeout(() => setCopiedCode(null), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-xl bg-primary/10">
            <Sparkles className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-foreground">Продвижение через ИИ чаты</h1>
            <p className="text-muted-foreground">
              Пошаговая инструкция по попаданию вашего бизнеса в ChatGPT и другие ИИ-ассистенты
            </p>
          </div>
        </div>
      </div>

      {/* Info Card */}
      <Card className="border-primary/20 bg-primary/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-primary" />
            Почему это важно?
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground leading-relaxed">
            ChatGPT и другие ИИ-ассистенты становятся основным способом поиска информации. 
            Чтобы ваш бизнес появлялся в ответах ChatGPT, нужно правильно оптимизировать сайт. 
            Четыре ключевых шага помогут вашему бизнесу быть найденным через ИИ-чаты.
          </p>
        </CardContent>
      </Card>

      {/* Steps */}
      <div className="space-y-6">
        {steps.map((step) => {
          const isCompleted = completedSteps.has(step.id);
          return (
            <Card 
              key={step.id} 
              className={`transition-all duration-200 ${
                isCompleted ? 'border-green-200 bg-green-50/50' : 'border-border'
              }`}
            >
              <CardHeader>
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-4 flex-1">
                    <button
                      onClick={() => toggleStep(step.id)}
                      className={`mt-1 p-1 rounded-full transition-colors ${
                        isCompleted 
                          ? 'text-green-600 hover:text-green-700' 
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                      title={isCompleted ? 'Отметить как невыполненное' : 'Отметить как выполненное'}
                    >
                      {isCompleted ? (
                        <CheckCircle2 className="w-6 h-6" />
                      ) : (
                        <Circle className="w-6 h-6" />
                      )}
                    </button>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-primary/10 text-primary">
                          Шаг {step.id}
                        </span>
                        {isCompleted && (
                          <span className="px-2.5 py-1 text-xs font-medium rounded-full bg-green-100 text-green-700">
                            Выполнено
                          </span>
                        )}
                      </div>
                      <CardTitle className="text-xl mb-2">{step.title}</CardTitle>
                      <CardDescription className="text-base">{step.description}</CardDescription>
                    </div>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Details */}
                <div>
                  <h4 className="font-semibold text-sm mb-2 text-foreground">Что нужно сделать:</h4>
                  <ul className="space-y-2">
                    {step.details.map((detail, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-sm text-muted-foreground">
                        <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-primary flex-shrink-0" />
                        <span>{detail}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Links */}
                {step.links && step.links.length > 0 && (
                  <div>
                    <h4 className="font-semibold text-sm mb-2 text-foreground">Полезные ссылки:</h4>
                    <div className="flex flex-wrap gap-2">
                      {step.links.map((link, idx) => (
                        <Button
                          key={idx}
                          variant="outline"
                          size="sm"
                          asChild
                          className="text-xs"
                        >
                          <a 
                            href={link.url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="flex items-center gap-1.5"
                          >
                            {link.text}
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        </Button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Code Example */}
                {step.codeExample && (
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="font-semibold text-sm text-foreground">Пример кода:</h4>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => copyCode(step.codeExample!, step.id)}
                        className="h-7 text-xs"
                      >
                        {copiedCode === step.id ? (
                          <>
                            <Check className="w-3 h-3 mr-1" />
                            Скопировано
                          </>
                        ) : (
                          <>
                            <Copy className="w-3 h-3 mr-1" />
                            Копировать
                          </>
                        )}
                      </Button>
                    </div>
                    <pre className="p-4 bg-muted rounded-lg text-xs overflow-x-auto border border-border">
                      <code>{step.codeExample}</code>
                    </pre>
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Progress Summary */}
      <Card className="bg-gradient-to-r from-primary/10 to-primary/5 border-primary/20">
        <CardHeader>
          <CardTitle>Прогресс выполнения</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-foreground">
                Выполнено шагов: {completedSteps.size} из {steps.length}
              </span>
              <span className="text-sm text-muted-foreground">
                {Math.round((completedSteps.size / steps.length) * 100)}%
              </span>
            </div>
            <div className="w-full bg-muted rounded-full h-2.5">
              <div
                className="bg-primary h-2.5 rounded-full transition-all duration-300"
                style={{ width: `${(completedSteps.size / steps.length) * 100}%` }}
              />
            </div>
            {completedSteps.size === steps.length && (
              <div className="flex items-center gap-2 p-3 bg-green-50 rounded-lg border border-green-200">
                <CheckCircle2 className="w-5 h-5 text-green-600 flex-shrink-0" />
                <p className="text-sm text-green-800">
                  <strong>Отлично!</strong> Вы выполнили все шаги. Теперь ваш сайт оптимизирован для поиска через ИИ-чаты.
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};


