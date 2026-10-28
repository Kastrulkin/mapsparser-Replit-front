// @vitest-environment jsdom
import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,render,screen,waitFor} from '@testing-library/react';
import {SavedPostDraft} from './SavedPostDraft';
vi.mock('@/components/operator/OperatorPhotoGallery',()=>({OperatorPhotoPreview:()=> <span>Фото к посту</span>}));
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('shows saved text and attached photo without generating another post',async()=>{
 const fetcher=vi.fn().mockResolvedValue(new Response(JSON.stringify({success:true,draft:{id:'d',business_id:'b',text:'Сохранённый текст',status:'draft',photos:[{asset_id:'p'}]}}),{status:200}));
 vi.stubGlobal('fetch',fetcher);
 render(<SavedPostDraft draftId="d" scope={{kind:'business',id:'b'}}/>);
 await screen.findByText('Сохранённый текст');
 expect(screen.getByText('Фото к посту')).toBeTruthy();
 expect(fetcher).toHaveBeenCalledTimes(1);
 expect(fetcher.mock.calls[0][0]).toContain('scope_id=b');
 expect(screen.getByRole('button',{name:'Скопировать текст'})).toBeTruthy();
});
it('shows an access error instead of another business draft',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({success:false,error:'Черновик недоступен'}),{status:403})));
 render(<SavedPostDraft draftId="d" scope={{kind:'business',id:'other'}}/>);
 await waitFor(()=>expect(screen.getByRole('alert').textContent).toContain('Черновик недоступен'));
 expect(screen.queryByRole('button',{name:'Скопировать текст'})).toBeNull();
});
