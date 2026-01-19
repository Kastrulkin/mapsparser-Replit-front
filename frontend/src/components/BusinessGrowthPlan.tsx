import React, { useState, useEffect } from 'react';
import { useLanguage } from '@/i18n/LanguageContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { CheckCircle2, Circle, Lock, Unlock, ChevronDown, ChevronRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { newAuth } from '@/lib/auth_new';

interface GrowthStage {
    id: string;
    stage_number: number;
    title: string;
    description: string;
    goal: string;
    expected_result: string;
    duration: string;
    tasks: Array<{ number: number; text: string }>;
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

    const toggleStageExpand = (stageId: string) => {
        const newExpanded = new Set(expandedStages);
        if (newExpanded.has(stageId)) {
            newExpanded.delete(stageId);
        } else {
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
            <Card>
                <CardContent className="p-8 text-center text-gray-500">
                    {t.dashboard.progress.growthPlan.title}
                </CardContent>
            </Card>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-orange-500 via-red-500 to-pink-500 p-8 text-white">
                <div className="relative z-10">
                    <h2 className="text-3xl font-bold mb-2">🏆 {t.dashboard.progress.growthPlan.title}</h2>
                    <p className="text-white/90 text-lg">
                        {t.dashboard.progress.growthPlan.subtitle}
                    </p>
                </div>
                <div className="absolute inset-0 bg-gradient-to-t from-black/20 to-transparent" />
            </div>

            {/* Stages */}
            <div className="space-y-4">
                {stages.map((stage, index) => {
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
                            transition={{ delay: index * 0.1 }}
                        >
                            <Card
                                className={`
                  transition-all duration-300
                  ${isActive ? 'border-orange-500 border-2 shadow-xl shadow-orange-500/20' : ''}
                  ${isCompleted ? 'border-green-500 bg-green-50/50' : ''}
                  ${isLocked ? 'opacity-60 blur-[1px]' : ''}
                `}
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
                                                        <CheckCircle2 className="h-8 w-8 text-green-500" />
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
                                                                fill="none"
                                                                className="text-gray-200"
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
                                                    <Lock className="h-8 w-8 text-gray-400" />
                                                )}
                                            </div>

                                            {/* Stage Info */}
                                            <div className="flex-1">
                                                <div className="flex items-center gap-3 mb-1">
                                                    <CardTitle className="text-xl">
                                                        {t.dashboard.progress.growthPlan.stage} {stage.stage_number}: {stage.title}
                                                    </CardTitle>
                                                    {isActive && (
                                                        <span className="px-3 py-1 text-xs font-semibold rounded-full bg-orange-100 text-orange-700">
                                                            🔥 {t.dashboard.progress.growthPlan.active}
                                                        </span>
                                                    )}
                                                </div>
                                                <CardDescription className="text-base">
                                                    {stage.description}
                                                </CardDescription>

                                                {/* Duration & Goal */}
                                                {!isLocked && (
                                                    <div className="mt-3 flex flex-wrap gap-4 text-sm text-gray-600">
                                                        <div>⏱️ {stage.duration}</div>
                                                        <div>🎯 {stage.expected_result}</div>
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
                                                    className="min-w-[120px]"
                                                >
                                                    {unlockingStage === stage.id ? (
                                                        <>🔓 {t.dashboard.progress.growthPlan.unlocking}</>
                                                    ) : (
                                                        <>🔒 {t.dashboard.progress.growthPlan.unlock}</>
                                                    )}
                                                </Button>
                                            ) : (
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() => toggleStageExpand(stage.id)}
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
                                                                        className="flex items-start space-x-3 p-3 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
                                                                        onClick={() => toggleTask(stage.id, task.number)}
                                                                    >
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
                                                                        <span className={`flex-1 ${isTaskCompleted ? 'line-through text-gray-500' : 'text-gray-700'}`}>
                                                                            {task.text}
                                                                        </span>
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
