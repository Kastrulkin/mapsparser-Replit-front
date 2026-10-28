// @vitest-environment jsdom
import {Suspense} from 'react';
import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {ContentModule} from './ContentModule';
const item={id:'qa-item',business_id:'b',title:'Только тестовый пост',draft_text:'Текст',scheduled_for:'2026-10-30',plan_id:'plan',plan_title:'План'};
vi.mock('./useContentResult',()=>({useContentResult:()=>({items:[{id:'qa-item',business_id:'b',title:'Только тестовый пост',draft_text:'Текст',scheduled_for:'2026-10-30',plan_id:'plan',plan_title:'План'}],activeId:'plan',currentId:'plan',plans:[{id:'plan',title:'План'}]})}));
vi.mock('@/components/content-plan/ContentReferences',()=>({ContentReferences:()=>null}));
vi.mock('@/components/content-plan/ContentPersonalization',()=>({ContentPersonalization:()=>null}));
vi.mock('@/components/telegram/WorkDiscussion',()=>({WorkDiscussion:()=>null}));
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('checks one post before deletion and cancellation never confirms it',async()=>{
 const fetcher=vi.fn().mockResolvedValue(new Response(JSON.stringify({success:true,preview:{action_id:'delete-one',capability:'content.item.delete',target_businesses:[],objects:[{id:'qa-item',theme:'Только тестовый пост'}],changes:[{label:'Удалить только тестовый пост'}]}}),{status:200}));
 vi.stubGlobal('fetch',fetcher);
 render(<Suspense fallback={null}><ContentModule scope={{kind:'business',id:'b'}} items={[item]} busy="" generate={vi.fn()} update={vi.fn()} reload={vi.fn()}/></Suspense>);
 expect(screen.queryByRole('button',{name:'Удалить пост «Только тестовый пост»'})).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'Изменить план'}));
 fireEvent.click(await screen.findByRole('button',{name:'Удалить пост «Только тестовый пост»'}));
 await screen.findByRole('button',{name:'Удалить пост',exact:true});
 const request=JSON.parse(fetcher.mock.calls[0][1].body);
 expect(request.capability).toBe('content.item.delete');
 expect(request.input).toEqual({item_id:'qa-item',business_id:'b'});
 fireEvent.click(screen.getByRole('button',{name:'Отмена',exact:true}));
 expect(fetcher).toHaveBeenCalledTimes(1);
});
