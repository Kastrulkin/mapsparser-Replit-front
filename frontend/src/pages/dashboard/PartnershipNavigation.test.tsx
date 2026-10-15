import { Profiler } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Outlet, Link, Route, Routes } from 'react-router-dom';
import { expect, it } from 'vitest';
import { LanguageProvider } from '@/i18n/LanguageContext';
import { PartnershipSearchPage } from './PartnershipSearchPage';
it('settles fresh draft arrays and leaves Partnerships without a reload',async()=>{
 let commits=0;const context={currentBusinessId:null,currentBusiness:null,businesses:[],user:{},controlScope:null};
 render(<MemoryRouter><LanguageProvider><Link to="/influencers">Инфлюенсеры</Link><Routes><Route element={<Outlet context={context}/>}><Route index element={<Profiler id="partnerships" onRender={()=>{commits++;if(commits>30)throw new Error('Repeated renders block navigation');}}><PartnershipSearchPage/></Profiler>}/><Route path="/influencers" element={<h1>Работа с инфлюенсерами</h1>}/></Route></Routes></LanguageProvider></MemoryRouter>);
 fireEvent.click(await screen.findByRole('link',{name:'Инфлюенсеры'}));expect(await screen.findByRole('heading',{name:'Работа с инфлюенсерами'})).toBeInTheDocument();expect(commits).toBeLessThan(30);
});
