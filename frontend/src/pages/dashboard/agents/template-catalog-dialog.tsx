import { useRef, useState, type ComponentProps } from 'react';
import { Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { AgentTemplateGallery } from './template-gallery';
import type { AgentTemplate } from './types';

type CatalogProps = Omit<ComponentProps<typeof AgentTemplateGallery>, 'onUse'> & {
  onUse: (template: AgentTemplate) => Promise<boolean | undefined>;
  error?: string | null;
};

export const AgentTemplateCatalogDialog = ({ onUse, onOpenAdded, error, ...galleryProps }: CatalogProps) => {
  const [open, setOpen] = useState(false);
  const openCompany = useRef(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const ru = galleryProps.language === 'ru';
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button ref={trigger} type="button"><Sparkles className="mr-2 h-4 w-4" />{ru ? 'Добавить агента' : 'Add agent'}</Button>
      </DialogTrigger>
      <DialogContent className="max-h-[88dvh] max-w-5xl overflow-y-auto rounded-2xl p-4 pt-10 sm:p-6 sm:pt-10" onCloseAutoFocus={(event) => {
        event.preventDefault();
        if (openCompany.current) document.getElementById('company-agents-title')?.focus();
        else trigger.current?.focus();
        openCompany.current = false;
      }}>
        <DialogTitle className="sr-only">{ru ? 'Каталог готовых агентов' : 'Ready-made agent catalog'}</DialogTitle>
        <DialogDescription className="sr-only">{ru ? 'Выберите агента для добавления в компанию.' : 'Choose an agent to add to your company.'}</DialogDescription>
        {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
        <AgentTemplateGallery {...galleryProps} onUse={async (template) => {
          const added = await onUse(template);
          if (added) { openCompany.current = true; setOpen(false); }
        }} onOpenAdded={onOpenAdded ? (id) => {
          openCompany.current = true;
          setOpen(false);
          onOpenAdded(id);
        } : undefined} />
      </DialogContent>
    </Dialog>
  );
};
