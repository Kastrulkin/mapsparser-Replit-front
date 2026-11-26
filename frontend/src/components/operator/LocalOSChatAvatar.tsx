import logo from '@/assets/images/logo.png';
import { Avatar } from '@/components/ui/avatar';

export function LocalOSChatAvatar() {
  return <Avatar aria-hidden="true" className="h-8 w-8">
    <img src={logo} alt="" className="absolute -top-1.5 left-1/2 h-14 w-14 max-w-none -translate-x-1/2" />
  </Avatar>;
}
