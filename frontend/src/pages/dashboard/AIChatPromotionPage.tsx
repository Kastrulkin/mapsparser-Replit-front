import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { CheckCircle2, Circle, ExternalLink, Copy, Check, Sparkles, AlertCircle } from 'lucide-react';
import { useToast } from '../../hooks/use-toast';
import { useLanguage } from '@/i18n/LanguageContext';

export const AIChatPromotionPage = () => {
  const [completedSteps, setCompletedSteps] = useState<Set<number>>(new Set());
  const [copiedCode, setCopiedCode] = useState<number | null>(null);
  const { toast } = useToast();
  const { t } = useLanguage();

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
      title: t.dashboard.aiChatPromotion.actions.copied,
      description: t.dashboard.aiChatPromotion.actions.copied,
    });
    setTimeout(() => setCopiedCode(null), 2000);
  };

  const steps = t.dashboard.aiChatPromotion.steps;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-xl bg-primary/10">
            <Sparkles className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-foreground">{t.dashboard.aiChatPromotion.title}</h1>
            <p className="text-muted-foreground">
              {t.dashboard.aiChatPromotion.subtitle}
            </p>
          </div>
        </div>
      </div>

      {/* Info Card */}
      <Card className="border-primary/20 bg-primary/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-primary" />
            {t.dashboard.aiChatPromotion.whyImportant.title}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground leading-relaxed">
            {t.dashboard.aiChatPromotion.whyImportant.description}
          </p>
        </CardContent>
      </Card>

      {/* Steps */}
      <div className="space-y-6">
        {steps.map((step: any) => {
          const isCompleted = completedSteps.has(step.id);
          return (
            <Card
              key={step.id}
              className={`transition-all duration-200 ${isCompleted ? 'border-green-200 bg-green-50/50' : 'border-border'
                }`}
            >
              <CardHeader>
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-4 flex-1">
                    <button
                      onClick={() => toggleStep(step.id)}
                      className={`mt-1 p-1 rounded-full transition-colors ${isCompleted
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
                          {t.dashboard.aiChatPromotion.card.step} {step.id}
                        </span>
                        {isCompleted && (
                          <span className="px-2.5 py-1 text-xs font-medium rounded-full bg-green-100 text-green-700">
                            {t.dashboard.aiChatPromotion.card.completed}
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
                  <h4 className="font-semibold text-sm mb-2 text-foreground">{t.dashboard.aiChatPromotion.actions.todo}</h4>
                  <ul className="space-y-2">
                    {step.details.map((detail: string, idx: number) => (
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
                    <h4 className="font-semibold text-sm mb-2 text-foreground">{t.dashboard.aiChatPromotion.actions.links}</h4>
                    <div className="flex flex-wrap gap-2">
                      {step.links.map((link: any, idx: number) => (
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
                      <h4 className="font-semibold text-sm text-foreground">{t.dashboard.aiChatPromotion.actions.code}</h4>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => copyCode(step.codeExample!, step.id)}
                        className="h-7 text-xs"
                      >
                        {copiedCode === step.id ? (
                          <>
                            <Check className="w-3 h-3 mr-1" />
                            {t.dashboard.aiChatPromotion.actions.copied}
                          </>
                        ) : (
                          <>
                            <Copy className="w-3 h-3 mr-1" />
                            {t.dashboard.aiChatPromotion.actions.copy}
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
          <CardTitle>{t.dashboard.aiChatPromotion.progress.title}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-foreground">
                {t.dashboard.aiChatPromotion.progress.completed} {completedSteps.size} {t.dashboard.aiChatPromotion.progress.from} {steps.length}
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
                  <strong>{t.dashboard.aiChatPromotion.progress.success}</strong>
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
