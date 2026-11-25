import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useLanguage } from '@/i18n/LanguageContext.logic';
import { demoWalkthroughCopy } from './demoWalkthroughCopy';

export function DemoReviews() {
  const { language } = useLanguage();
  const sample = demoWalkthroughCopy(language);
  const isRussian = language === 'ru';

  return (
    <Card>
      <CardHeader>
        <CardTitle>{isRussian ? 'Отзывы без ответа' : 'Unanswered reviews'}</CardTitle>
        <p className="text-sm text-muted-foreground">
          {isRussian
            ? 'Четыре учебных отзыва. В автоматизации можно подготовить и проверить ответы на этом примере.'
            : 'Four sample reviews. Use the automation workspace to prepare and review replies for this example.'}
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <ul className="space-y-3">
          {sample.reviewInputs.map(review => <li key={review} className="rounded-lg border p-3">{review}</li>)}
        </ul>
        <Button asChild>
          <Link to="/dashboard/agents">{isRussian ? 'Открыть автоматизацию ответов' : 'Open reply automation'}</Link>
        </Button>
      </CardContent>
    </Card>
  );
}
