import { useEffect, useState } from 'react';
import { AlertCircle, WifiOff } from 'lucide-react';

export default function MobileShell({ header, error, children, overlay, navigation }: { header: React.ReactNode; error?: string; children: React.ReactNode; overlay?: React.ReactNode; navigation?: React.ReactNode }) {
  const [online, setOnline] = useState(() => typeof navigator === 'undefined' || navigator.onLine);
  useEffect(() => {
    const connect = () => setOnline(true);
    const disconnect = () => setOnline(false);
    window.addEventListener('online', connect);
    window.addEventListener('offline', disconnect);
    return () => {
      window.removeEventListener('online', connect);
      window.removeEventListener('offline', disconnect);
    };
  }, []);
  return <main className="min-h-[100dvh] bg-zinc-950 text-zinc-100 antialiased selection:bg-primary/30"><div className="pointer-events-none fixed inset-x-0 top-0 h-72 bg-[radial-gradient(circle_at_top,rgba(255,92,51,0.16),transparent_68%)]" /><div className="relative mx-auto min-h-[100dvh] max-w-xl pb-[calc(92px+env(safe-area-inset-bottom))]">{header}{!online ? <div role="status" className="mx-4 mb-4 flex min-h-12 items-center gap-3 rounded-[16px] bg-amber-400/[0.08] px-4 text-sm text-amber-100/80 ring-1 ring-inset ring-amber-400/15"><WifiOff className="h-4 w-4 shrink-0 text-amber-300" /><span className="text-pretty">Нет сети. Открытые данные останутся на экране, отправка продолжится после подключения.</span></div> : null}{error ? <div role="alert" className="mx-4 mb-4 flex min-h-12 gap-3 rounded-[16px] bg-rose-500/10 p-4 text-sm text-rose-100 ring-1 ring-inset ring-rose-400/20"><AlertCircle className="h-5 w-5 shrink-0" /><span className="text-pretty">{error}</span></div> : null}{children}{overlay}{navigation}</div></main>;
}
