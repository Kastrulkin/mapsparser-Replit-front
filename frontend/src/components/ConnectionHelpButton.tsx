import { Button } from '@/components/ui/button';

export function ConnectionHelpButton({ business, address, service }: {
  business?: string | null;
  address?: string | null;
  service?: string;
}) {
  const company = business ? ' для компании «' + business + '»' : '';
  const location = address ? ', филиал: ' + address : '';
  const body = 'Здравствуйте! Помогите, пожалуйста, настроить ' + (service || 'подключения') + company + location
    + '.\n\nНа каком шаге нужна помощь: ';
  const href = 'mailto:info@localos.pro?subject=' + encodeURIComponent('Помощь с подключением в LocalOS')
    + '&body=' + encodeURIComponent(body);

  return <Button variant="outline" asChild><a href={href}>Помогите настроить подключение</a></Button>;
}
