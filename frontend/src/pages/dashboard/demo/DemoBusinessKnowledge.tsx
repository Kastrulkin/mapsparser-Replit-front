import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useLanguage } from '@/i18n/LanguageContext.logic';
import { demoNavigationCopy } from '@/components/guided-tour/demoNavigationCopy';

/** Public, synthetic examples only. Never load the demo owner's private knowledge. */
export default function DemoBusinessKnowledge() {
  const { language } = useLanguage();
  const t = demoNavigationCopy(language);
  return <section data-tour-target="business-knowledge" className="min-w-0 space-y-4">
    <header><h1 className="text-2xl font-semibold">{t.knowledgeTitle}</h1>
      <p className="mt-2 text-sm text-muted-foreground">{t.knowledge}</p></header>
    <p role="note" className="rounded-lg border bg-muted p-4 text-sm">{t.example}</p>
    <Tabs defaultValue="fields">
      <TabsList className="h-auto w-full flex-wrap justify-start">
        <TabsTrigger value="fields" className="whitespace-normal">{t.fields}</TabsTrigger>
        <TabsTrigger value="rules" className="whitespace-normal">{t.rules}</TabsTrigger>
        <TabsTrigger value="documents" className="whitespace-normal">{t.documents}</TabsTrigger>
      </TabsList>
      <TabsContent value="fields" className="rounded-lg border p-4"><dl>
        <dt className="text-sm text-muted-foreground">{t.chairs}</dt><dd className="mt-1 text-lg font-semibold">6</dd>
      </dl></TabsContent>
      <TabsContent value="rules" className="rounded-lg border p-4"><h2 className="font-medium">{t.booking}</h2>
        <p className="mt-2 text-sm">{t.bookingRule}</p></TabsContent>
      <TabsContent value="documents" className="rounded-lg border p-4"><h2 className="break-words font-medium">{t.filename}</h2>
        <p className="mt-2 text-sm text-muted-foreground">{t.example}</p><p className="mt-2 text-sm">{t.bookingRule}</p></TabsContent>
    </Tabs>
  </section>;
}
