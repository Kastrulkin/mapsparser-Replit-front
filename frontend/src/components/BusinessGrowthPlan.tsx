import React, { useState, useEffect } from 'react';
import { useLanguage } from '@/i18n/LanguageContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { CheckCircle2, Circle, Lock, Unlock, ChevronDown, ChevronRight, HelpCircle, Clock, Trophy, Zap, Target } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { newAuth } from '@/lib/auth_new';
import { DESIGN_TOKENS, cn } from '@/lib/design-tokens';
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";

interface GrowthTask {
    id?: string;
    number: number;
    text: string;
    tooltip?: string;
    reward_value?: number;
    reward_type?: string;
    check_logic?: string;
    link_url?: string;
    link_text?: string;
    is_auto_verifiable?: boolean;
}

interface GrowthStage {
    id: string;
    stage_number: number;
    title: string;
    description: string;
    goal: string;
    expected_result: string;
    duration: string;
    tasks: GrowthTask[];
    is_unlocked: boolean;
    progress_percentage: number;
    completed_tasks: number[];
    unlocked_at: string | null;
    completed_at: string | null;
}

interface BusinessGrowthPlanProps {
    businessId?: string;
}

export const BusinessGrowthPlan: React.FC<BusinessGrowthPlanProps> = ({ businessId }) => {
    const { t } = useLanguage();
    const [stages, setStages] = useState<GrowthStage[]>([]);
    const [loading, setLoading] = useState(true);
    const [expandedStages, setExpandedStages] = useState<Set<string>>(new Set());
    const [unlockingStage, setUnlockingStage] = useState<string | null>(null);

    useEffect(() => {
        if (businessId) {
            loadStageProgress();
        }
    }, [businessId]);

    const loadStageProgress = async () => {
        if (!businessId) return;
        try {
            setLoading(true);
            const data = await newAuth.makeRequest(`/business/${businessId}/stage-progress`, { method: 'GET' });
            setStages(data.stages || []);

            // Авто-раскрываем текущий активный этап
            const activeStage = data.stages?.find((s: GrowthStage) =>
                s.is_unlocked && s.progress_percentage > 0 && s.progress_percentage < 100
            );
            if (activeStage) {
                setExpandedStages(new Set([activeStage.id]));
            }
        } catch (error) {
            console.error('Error loading stage progress:', error);
        } finally {
            setLoading(false);
        }
    };

    const translateStage = (stage: GrowthStage): GrowthStage => {
        const stageTranslations = (t as any).growthStages?.[stage.stage_number];

        if (!stageTranslations) {
            // Fallback to database values if translation doesn't exist
            return stage;
        }

        // Map translated tasks to the original task structure, preserving metadata
        const translatedTasks = stage.tasks.map((task, idx) => {
            const translatedText = stageTranslations.tasks?.[idx];
            return {
                ...task,
                text: typeof translatedText === 'string' ? translatedText : task.text
            };
        });

        return {
            ...stage,
            title: stageTranslations.title || stage.title,
            description: stageTranslations.description || stage.description,
            goal: stageTranslations.goal || stage.goal,
            expected_result: stageTranslations.expectedResult || stage.expected_result,
            duration: stageTranslations.duration || stage.duration,
            tasks: translatedTasks
        };
    };

    const toggleStageExpand = (stageId: string) => {
        const newExpanded = new Set(expandedStages);
        if (newExpanded.has(stageId)) {
            newExpanded.delete(stageId);
            newExpanded.add(stageId);
        }
        setExpandedStages(newExpanded);
    };

    const unlockStage = async (stageId: string) => {
        if (!businessId) return;
        try {
            setUnlockingStage(stageId);
            await newAuth.makeRequest(`/business/${businessId}/stage-progress/${stageId}/unlock`, {
                method: 'POST'
            });
            await loadStageProgress();
            setExpandedStages(new Set([stageId]));
        } catch (error) {
            console.error('Error unlocking stage:', error);
        } finally {
            setUnlockingStage(null);
        }
    };

    const toggleTask = async (stageId: string, taskNumber: number) => {
        if (!businessId) return;
        try {
            await newAuth.makeRequest(`/business/${businessId}/stage-progress/${stageId}/complete-task`, {
                method: 'POST',
                body: JSON.stringify({ task_number: taskNumber })
            });
            await loadStageProgress();
        } catch (error) {
            console.error('Error toggling task:', error);
        }
    };

    const getProgressColor = (percentage: number): string => {
        if (percentage >= 100) return 'text-green-600';
        if (percentage >= 50) return 'text-orange-500';
        return 'text-gray-600';
    };

    const getProgressBgColor = (percentage: number): string => {
        if (percentage >= 100) return 'bg-green-500';
        if (percentage >= 50) return 'bg-orange-500';
        return 'bg-gray-400';
    };

    // Определяем статус этапа: completed, active, unlocked, locked
    const getStageStatus = (stage: GrowthStage, index: number): 'completed' | 'active' | 'unlocked' | 'locked' => {
        if (stage.progress_percentage >= 100) return 'completed';
        if (stage.is_unlocked && stage.progress_percentage > 0) return 'active';
        if (stage.is_unlocked) return 'unlocked';
        return 'locked';
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center p-12">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-orange-500" />
            </div>
        );
    }

    if (!businessId) {
        return (
            <Card className="border-none shadow-sm bg-gray-50/50">
                <CardContent className="p-8 text-center text-gray-500">
                    {t.dashboard.progress.growthPlan.title}
                </CardContent>
            </Card>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className={cn(
                "relative overflow-hidden rounded-2xl p-8 text-white shadow-lg",
                DESIGN_TOKENS.gradients.gold
            )}>
                <div className="relative z-10">
                    <div className="flex items-center gap-3 mb-2">
                        <Trophy className="h-8 w-8 text-white/90" />
                        <h2 className="text-3xl font-bold">{t.dashboard.progress.growthPlan.title}</h2>
                    </div>
                    <p className="text-white/90 text-lg pl-11">
                        {t.dashboard.progress.growthPlan.subtitle}
                    </p>
                </div>
                {/* Decorative circles */}
                <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
                <div className="absolute bottom-0 left-0 w-32 h-32 bg-black/5 rounded-full blur-2xl translate-y-1/2 -translate-x-1/4" />
            </div>

            {/* Stages */}
            <div className="space-y-4">
                {stages.map((dbStage, index) => {
                    const stage = translateStage(dbStage);
                    const status = getStageStatus(stage, index);
                    const isExpanded = expandedStages.has(stage.id);
                    const isCompleted = status === 'completed';
                    const isActive = status === 'active';
                    const isLocked = status === 'locked';

                    return (
                        <motion.div
                            key={stage.id}
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: index * DESIGN_TOKENS.motion.fast }}
                        >
                            <Card
                                className={cn(
                                    "transition-all duration-300 border-0",
                                    isActive ? DESIGN_TOKENS.glass.default + " ring-1 ring-orange-500/20" : "bg-white/50 hover:bg-white/80",
                                    isCompleted && "bg-green-50/30 border-green-200/50",
                                    isLocked && "opacity-60 grayscale-[0.5]"
                                )}
                            >
                                <CardHeader className="pb-4">
                                    <div className="flex items-start justify-between">
                                        <div className="flex items-start space-x-4 flex-1">
                                            {/* Stage Icon */}
                                            <div className="mt-1">
                                                {isCompleted ? (
                                                    <motion.div
                                                        initial={{ scale: 0 }}
                                                        animate={{ scale: 1 }}
                                                        transition={{ type: "spring", stiffness: 200, damping: 10 }}
                                                    >
                                                        <div className="rounded-full bg-green-100 p-2">
                                                            <CheckCircle2 className="h-6 w-6 text-green-600" />
                                                        </div>
                                                    </motion.div>
                                                ) : isActive || stage.is_unlocked ? (
                                                    <div className="relative w-16 h-16">
                                                        {/* Progress Ring */}
                                                        <svg className="transform -rotate-90 w-16 h-16">
                                                            <circle
                                                                cx="32"
                                                                cy="32"
                                                                r="28"
                                                                stroke="currentColor"
                                                                strokeWidth="4"
                                                                fill="none" // Transparent center for glass effect
                                                                className="text-gray-100"
                                                            />
                                                            <motion.circle
                                                                cx="32"
                                                                cy="32"
                                                                r="28"
                                                                stroke="currentColor"
                                                                strokeWidth="4"
                                                                fill="none"
                                                                strokeDasharray={`${2 * Math.PI * 28}`}
                                                                strokeDashoffset={`${2 * Math.PI * 28 * (1 - stage.progress_percentage / 100)}`}
                                                                className={getProgressColor(stage.progress_percentage)}
                                                                strokeLinecap="round"
                                                                initial={{ strokeDashoffset: 2 * Math.PI * 28 }}
                                                                animate={{ strokeDashoffset: 2 * Math.PI * 28 * (1 - stage.progress_percentage / 100) }}
                                                                transition={{ duration: 1, ease: "easeOut" }}
                                                            />
                                                        </svg>
                                                        <div className="absolute inset-0 flex items-center justify-center">
                                                            <span className={`text-sm font-bold ${getProgressColor(stage.progress_percentage)}`}>
                                                                {stage.progress_percentage}%
                                                            </span>
                                                        </div>
                                                    </div>
                                                ) : (
                                                    <div className="rounded-full bg-gray-100 p-3">
                                                        <Lock className="h-6 w-6 text-gray-400" />
                                                    </div>
                                                )}
                                            </div>

                                            {/* Stage Info */}
                                            <div className="flex-1">
                                                <div className="flex items-center gap-3 mb-1">
                                                    <CardTitle className="text-xl font-display tracking-tight text-gray-900">
                                                        <span className="text-gray-400 font-normal mr-2">#{stage.stage_number}</span>
                                                        {stage.title}
                                                    </CardTitle>
                                                    {isActive && (
                                                        <span className="flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold rounded-full bg-orange-100/80 text-orange-700 border border-orange-200/50 backdrop-blur-sm">
                                                            <Zap className="w-3 h-3" />
                                                            {t.dashboard.progress.growthPlan.active}
                                                        </span>
                                                    )}
                                                </div>
                                                <CardDescription className="text-base text-gray-600 leading-relaxed max-w-2xl">
                                                    {stage.description}
                                                </CardDescription>

                                                {/* Duration & Goal */}
                                                {!isLocked && (
                                                    <div className="mt-4 flex flex-wrap gap-4 text-sm text-gray-500">
                                                        <div className="flex items-center gap-1.5 bg-gray-50 px-2.5 py-1 rounded-md border border-gray-100">
                                                            <Clock className="w-4 h-4 text-gray-400" />
                                                            {stage.duration}
                                                        </div>
                                                        <div className="flex items-center gap-1.5 bg-blue-50/50 px-2.5 py-1 rounded-md border border-blue-100/50 text-blue-700">
                                                            <Target className="w-4 h-4 text-blue-500" />
                                                            {stage.expected_result}
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        </div>

                                        {/* Expand/Action Button */}
                                        <div className="flex items-center gap-2 ml-4">
                                            {isLocked ? (
                                                <Button
                                                    onClick={() => unlockStage(stage.id)}
                                                    disabled={unlockingStage === stage.id}
                                                    variant="outline"
                                                    size="sm"
                                                    className="min-w-[120px] bg-white/50 backdrop-blur-sm"
                                                >
                                                    {unlockingStage === stage.id ? (
                                                        <><Unlock className="w-4 h-4 mr-2 animate-pulse" /> {t.dashboard.progress.growthPlan.unlocking}</>
                                                    ) : (
                                                        <><Lock className="w-4 h-4 mr-2" /> {t.dashboard.progress.growthPlan.unlock}</>
                                                    )}
                                                </Button>
                                            ) : (
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    onClick={() => toggleStageExpand(stage.id)}
                                                    className="rounded-full hover:bg-black/5"
                                                >
                                                    {isExpanded ? (
                                                        <ChevronDown className="h-5 w-5" />
                                                    ) : (
                                                        <ChevronRight className="h-5 w-5" />
                                                    )}
                                                </Button>
                                            )}
                                        </div>
                                    </div>
                                </CardHeader>

                                {/* Expanded Content */}
                                <AnimatePresence>
                                    {isExpanded && !isLocked && (
                                        <motion.div
                                            initial={{ height: 0, opacity: 0 }}
                                            animate={{ height: "auto", opacity: 1 }}
                                            exit={{ height: 0, opacity: 0 }}
                                            transition={{ duration: 0.3 }}
                                        >
                                            <CardContent className="pt-0 space-y-4">
                                                {/* Goal */}
                                                {stage.goal && (
                                                    <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                                                        <h4 className="font-semibold text-blue-900 mb-2">🎯 {t.dashboard.progress.growthPlan.target}</h4>
                                                        <p className="text-blue-800">{stage.goal}</p>
                                                    </div>
                                                )}

                                                {/* Tasks Checklist */}
                                                {stage.tasks && stage.tasks.length > 0 && (
                                                    <div>
                                                        <h4 className="font-semibold text-gray-900 mb-3">
                                                            {t.dashboard.progress.growthPlan.tasks} ({stage.completed_tasks?.length || 0}/{stage.tasks.length}):
                                                        </h4>
                                                        <div className="space-y-2">
                                                            {stage.tasks.map((task) => {
                                                                const isTaskCompleted = stage.completed_tasks?.includes(task.number);
                                                                return (
                                                                    <motion.div
                                                                        key={task.number}
                                                                        whileHover={{ scale: 1.01, x: 4 }}
                                                                        whileTap={{ scale: 0.99 }}
                                                                        className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors group"
                                                                        onClick={() => toggleTask(stage.id, task.number)}
                                                                    >
                                                                        <div className="flex items-start space-x-3 flex-1">
                                                                            <div className="mt-0.5">
                                                                                {isTaskCompleted ? (
                                                                                    <motion.div
                                                                                        initial={{ scale: 0, rotate: -90 }}
                                                                                        animate={{ scale: 1, rotate: 0 }}
                                                                                        transition={{ type: "spring", stiffness: 200 }}
                                                                                    >
                                                                                        <CheckCircle2 className="h-5 w-5 text-green-500" />
                                                                                    </motion.div>
                                                                                ) : (
                                                                                    <Circle className="h-5 w-5 text-gray-400" />
                                                                                )}
                                                                            </div>
                                                                            <div className="flex flex-col">
                                                                                <div className="flex items-center gap-2">
                                                                                    <span className={`${isTaskCompleted ? 'line-through text-gray-500' : 'text-gray-700'}`}>
                                                                                        {task.text}
                                                                                    </span>

                                                                                    {/* Tooltip */}
                                                                                    {task.tooltip && (
                                                                                        <TooltipProvider>
                                                                                            <Tooltip>
                                                                                                <TooltipTrigger asChild onClick={(e) => e.stopPropagation()}>
                                                                                                    <HelpCircle className="h-4 w-4 text-gray-400 hover:text-orange-500 transition-colors" />
                                                                                                </TooltipTrigger>
                                                                                                <TooltipContent>
                                                                                                    <p className="max-w-xs">{task.tooltip}</p>
                                                                                                </TooltipContent>
                                                                                            </Tooltip>
                                                                                        </TooltipProvider>
                                                                                    )}
                                                                                </div>

                                                                                {/* Reward Badge */}
                                                                                {task.reward_value && task.reward_value > 0 && !isTaskCompleted && (
                                                                                    <div className="flex items-center gap-1 mt-1">
                                                                                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                                                                                            <Clock className="w-3 h-3" />
                                                                                            +{task.reward_value} мин
                                                                                        </span>
                                                                                    </div>
                                                                                )}
                                                                            </div>
                                                                        </div>
                                                                    </motion.div>
                                                                );
                                                            })}
                                                        </div>
                                                    </div>
                                                )}

                                                {/* Progress Bar */}
                                                {stage.progress_percentage > 0 && (
                                                    <div className="pt-4 border-t">
                                                        <div className="flex justify-between items-center mb-2">
                                                            <span className="text-sm font-medium text-gray-700">{t.dashboard.progress.growthPlan.progress}</span>
                                                            <span className={`text-sm font-bold ${getProgressColor(stage.progress_percentage)}`}>
                                                                {stage.progress_percentage}%
                                                            </span>
                                                        </div>
                                                        <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                                                            <motion.div
                                                                className={`h-3 rounded-full ${getProgressBgColor(stage.progress_percentage)}`}
                                                                initial={{ width: 0 }}
                                                                animate={{ width: `${stage.progress_percentage}%` }}
                                                                transition={{ duration: 1, ease: "easeOut" }}
                                                            />
                                                        </div>
                                                    </div>
                                                )}

                                                {/* Motivational Message */}
                                                {isActive && stage.progress_percentage > 0 && stage.progress_percentage < 100 && (
                                                    <div className="p-4 bg-gradient-to-r from-orange-50 to-pink-50 rounded-lg border border-orange-200">
                                                        <p className="text-orange-800 font-medium">
                                                            {stage.progress_percentage >= 75 ? (
                                                                <>{t.dashboard.progress.growthPlan.almostDone.replace('{percent}', String(stage.progress_percentage))}</>
                                                            ) : stage.progress_percentage >= 50 ? (
                                                                <>{t.dashboard.progress.growthPlan.goodJob}</>
                                                            ) : (
                                                                <>{t.dashboard.progress.growthPlan.goodStart}</>
                                                            )}
                                                        </p>
                                                    </div>
                                                )}

                                                {/* Completed Message */}
                                                {isCompleted && (
                                                    <div className="p-4 bg-green-50 rounded-lg border border-green-200">
                                                        <p className="text-green-800 font-medium">
                                                            {t.dashboard.progress.growthPlan.completed}
                                                        </p>
                                                    </div>
                                                )}
                                            </CardContent>
                                        </motion.div>
                                    )}
                                </AnimatePresence>
                            </Card>
                        </motion.div>
                    );
                })}
            </div>

            {/* Empty State */}
            {stages.length === 0 && (
                <Card>
                    <CardContent className="p-12 text-center">
                        <p className="text-gray-500 mb-4">{t.dashboard.progress.growthPlan.noStages}</p>
                        <p className="text-sm text-gray-400">{t.dashboard.progress.growthPlan.contactAdmin}</p>
                    </CardContent>
                </Card>
            )}
        </div>
    );
};
