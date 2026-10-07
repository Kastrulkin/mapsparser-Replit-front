import { useOutletContext } from 'react-router-dom';
import { WorkJournal } from '@/components/WorkJournal';
export default function WorkJournalPage() {
  const { currentBusinessId } = useOutletContext<{ currentBusinessId?: string | null }>();
  return <WorkJournal businessId={currentBusinessId} />;
}
