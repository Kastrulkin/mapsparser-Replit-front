import { expect,it,vi } from 'vitest';
import {loadPartnershipDrafts,loadPartnershipBatches} from './partnershipApi';
const request=vi.hoisted(()=>vi.fn().mockResolvedValue({items:[]}));
vi.mock('@/lib/auth_new',()=>({newAuth:{makeRequest:request}}));
it('keeps letters and send batches in the explicitly selected group',async()=>{await loadPartnershipDrafts('business','selected group');await loadPartnershipBatches('business','selected group');expect(request).toHaveBeenCalledWith('/partnership/drafts?business_id=business&search_task_id=selected%20group',{method:'GET'});expect(request).toHaveBeenCalledWith('/partnership/send-batches?business_id=business&search_task_id=selected%20group',{method:'GET'});});
