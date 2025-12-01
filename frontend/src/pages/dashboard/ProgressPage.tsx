import { useOutletContext } from 'react-router-dom';
import ProgressTracker from '@/components/ProgressTracker';

export const ProgressPage = () => {
  const { user, currentBusinessId } = useOutletContext<any>();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Прогресс</h1>
        <p className="text-gray-600 mt-1">Отслеживайте ваш прогресс и достижения</p>
      </div>

      <ProgressTracker />
    </div>
  );
};

