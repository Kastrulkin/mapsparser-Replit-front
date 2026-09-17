import { AlertCircle, CheckCircle2, Lock, RefreshCcw, TrendingUp } from 'lucide-react';
import React from 'react';
import { useApiData } from '../hooks/useApiData';
import { cn } from '../lib/utils';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { ScrollArea } from './ui/scroll-area';

// --- Interfaces ---

interface GrowthStage {
  id: string;
  stage_number: number;
  stage_name: string;
  stage_description: string;
  status: 'completed' | 'active' | 'locked' | 'pending';
  progress_percentage: number;
  duration: string;
  goal: string;
  expected_result: string;
  // Legacy fields (optional support)
  target_revenue?: number;
  current_revenue?: number;
}

interface SprintTask {
  id: string;
  title: string;
  description: string;
  expected_effect: string;
  deadline: string;
  status: 'pending' | 'done' | 'postponed' | 'help_needed';
}

interface ProgressTrackerProps {
  onUpdate?: () => void;
  businessId?: string | null;
}

// --- Component ---

const ProgressTracker: React.FC<ProgressTrackerProps> = ({ onUpdate, businessId }) => {
  // 1. Fetch Stages
  const { data: stagesData, loading: loadingStages, error: errorStages } = useApiData<GrowthStage[], { stages?: GrowthStage[] }>(
    businessId ? `/api/business/${businessId}/stages` : null,
    {
      transform: (data) => data.stages || []
    }
  );
  const stages = stagesData || [];

  const reloadStages = () => {
    window.location.reload();
  };

  // 2. Fetch Sprint
  const { data: sprintData, loading: loadingSprint } = useApiData<{ tasks: SprintTask[] }, { sprint?: { tasks: SprintTask[] } }>(
    businessId ? `/api/business/${businessId}/sprint` : null,
    {
      transform: (data) => data.sprint || { tasks: [] }
    }
  );
  const sprint = sprintData;

  const currentStage = stages.find(s => s.status === 'active') || stages[stages.length - 1];
  const completedStagesCount = stages.filter(s => s.status === 'completed').length;
  const progress = stages.length > 0 ? (completedStagesCount / stages.length) * 100 : 0;

  // --- Render Helpers ---

  if (loadingStages && !stages.length) {
    return (
      <Card className="w-full">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-primary" />
            План роста
          </CardTitle>
          <CardDescription>Загрузка плана развития...</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-24 bg-muted/20 animate-pulse rounded-lg" />
          ))}
        </CardContent>
      </Card>
    );
  }

  if (errorStages) {
    return (
      <Card className="w-full border-destructive/20">
        <CardHeader>
          <CardTitle className="text-destructive flex items-center gap-2">
            <AlertCircle className="w-5 h-5" />
            Ошибка загрузки
          </CardTitle>
          <CardDescription>{errorStages}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={reloadStages} variant="outline" className="gap-2">
            <RefreshCcw className="w-4 h-4" />
            Попробовать снова
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card className="w-full">
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <CardTitle className="flex items-center gap-2 text-xl text-primary">
                <TrendingUp className="h-5 w-5" />
                План роста бизнеса
              </CardTitle>
              <CardDescription>
                Следуйте пошаговому плану для масштабирования результатов
              </CardDescription>
            </div>
            <Badge variant={progress === 100 ? "default" : "secondary"} className="text-sm px-3 py-1">
              {Math.round(progress)}% пройдено
            </Badge>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          <ScrollArea className="h-full px-6 pb-6 max-h-[600px]">
            <div className="relative space-y-8 pl-2 pt-2">
              {/* Timeline Line */}
              <div className="absolute left-6 top-6 bottom-6 w-0.5 bg-border -z-10" />

              {stages.map((stage) => {
                const isActive = stage.status === 'active';
                const isCompleted = stage.status === 'completed';
                const isLocked = stage.status === 'locked' || stage.status === 'pending';

                return (
                  <div key={stage.id} className={cn(
                    "relative flex gap-6 group transition-all duration-300",
                    isLocked && "opacity-60 grayscale-[0.5]"
                  )}>
                    {/* Status Icon */}
                    <div className={cn(
                      "flex-none w-12 h-12 rounded-full border-4 bg-background flex items-center justify-center z-10 transition-colors",
                      isCompleted && "border-primary text-primary-foreground bg-primary",
                      isActive && "border-primary text-primary ring-4 ring-primary/20",
                      isLocked && "border-muted text-muted-foreground bg-muted/20"
                    )}>
                      {isCompleted ? (
                        <CheckCircle2 className="w-6 h-6" />
                      ) : isActive ? (
                        <div className="w-3 h-3 bg-primary rounded-full animate-pulse" />
                      ) : (
                        <Lock className="w-5 h-5" />
                      )}
                    </div>

                    {/* Content Card */}
                    <div className={cn(
                      "flex-1 p-5 rounded-xl border bg-card transition-all hover:shadow-md",
                      isActive && "border-primary/50 shadow-lg ring-1 ring-primary/10 bg-gradient-to-br from-card to-primary/5"
                    )}>
                      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 mb-3">
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <span className={cn(
                              "text-xs font-bold uppercase tracking-wider",
                              isActive ? "text-primary" : "text-muted-foreground"
                            )}>
                              Этап {stage.stage_number}
                            </span>
                            {isActive && <Badge>Текущий</Badge>}
                            {isCompleted && <Badge variant="outline" className="text-primary border-primary/20">Выполнен</Badge>}
                          </div>
                          <h3 className={cn(
                            "text-lg font-bold",
                            isActive ? "text-foreground" : "text-muted-foreground"
                          )}>
                            {stage.stage_name}
                          </h3>
                        </div>

                        {stage.duration && (
                          <div className="bg-muted/50 px-2 py-1 rounded text-xs font-medium whitespace-nowrap text-muted-foreground h-fit">
                            ⏱ {stage.duration}
                          </div>
                        )}
                      </div>

                      <p className="text-sm text-muted-foreground mb-4">
                        {stage.stage_description}
                      </p>

                      {(isCompleted || isActive) && (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4 pt-4 border-t border-border/50">
                          {stage.goal && (
                            <div className="space-y-1">
                              <span className="text-xs font-semibold text-primary/80 uppercase">Цель</span>
                              <p className="text-xs text-foreground/80">{stage.goal}</p>
                            </div>
                          )}
                          {stage.expected_result && (
                            <div className="space-y-1">
                              <span className="text-xs font-semibold text-green-600 uppercase">Результат</span>
                              <p className="text-xs text-foreground/80">{stage.expected_result}</p>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>

      {/* --- Sprint Section (Preserved) --- */}
      {sprint && sprint.tasks.length > 0 && (
        <Card className="border-primary/50 shadow-lg shadow-orange-500/10">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-lg font-semibold flex items-center gap-2">
              📋 Спринт на неделю
            </CardTitle>
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.location.href = `/sprint?business_id=${businessId}`}
            >
              Открыть доску
            </Button>
          </CardHeader>
          <CardContent className="pt-4">
            <div className="space-y-3">
              {sprint.tasks.slice(0, 3).map((task) => (
                <div key={task.id} className="bg-muted/30 rounded-lg p-3 border border-border">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="font-medium text-foreground">{task.title}</div>
                      <div className="text-sm text-muted-foreground mt-1 line-clamp-2">{task.description}</div>
                      <div className="text-xs text-muted-foreground mt-2 flex gap-2">
                        <span className="font-medium text-primary">{task.expected_effect}</span>
                        •
                        <span>Дедлайн: {task.deadline}</span>
                      </div>
                    </div>
                    {task.status === 'done' && (
                      <Badge variant="secondary" className="bg-green-100 text-green-800 ml-2">Сделано</Badge>
                    )}
                    {task.status === 'help_needed' && (
                      <Badge variant="destructive" className="ml-2">Нужна помощь</Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {sprint.tasks.length > 3 && (
              <div className="mt-4 text-center">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => window.location.href = `/sprint?business_id=${businessId}`}
                >
                  Показать все задачи ({sprint.tasks.length})
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default ProgressTracker;
