import React from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { _itemFilterLabel } from './helpers';
import { ITEM_FILTER_OPTIONS } from './constants';

export const SocialFilterHeader = ({ scope }) => {
  const {
    isRu, selectedItemFilter, setSelectedItemFilter, dateFromFilter, setDateFromFilter, dateToFilter, setDateToFilter, setSortMode,
    itemFilterCounts, resetViewState
  } = scope;
  return (
    <>
              <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-slate-950">
                    {isRu ? 'Показать в очереди' : 'Show in queue'}
                  </div>
                  <div className="mt-1 text-xs leading-5 text-slate-500">
                    {isRu
                      ? 'Выберите состояние и период публикации. Список ниже сразу обновится по календарной дате.'
                      : 'Choose status and publication period. The list below updates by calendar date.'}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {ITEM_FILTER_OPTIONS.map((filterKey) => (
                      <button
                        key={filterKey}
                        type="button"
                        onClick={() => {
                          setSelectedItemFilter(filterKey);
                          setSortMode('date');
                        }}
                        className={[
                          'rounded-full border px-3 py-1.5 text-sm transition-colors',
                          selectedItemFilter === filterKey
                            ? 'border-slate-900 bg-slate-900 text-white'
                            : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
                        ].join(' ')}
                      >
                        {_itemFilterLabel(filterKey, isRu)} · {itemFilterCounts[filterKey]}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="grid gap-3 sm:grid-cols-[minmax(150px,1fr)_minmax(150px,1fr)_auto] sm:items-end">
                  <label className="grid gap-1 text-xs font-medium text-slate-600">
                    <span>{isRu ? 'С даты' : 'From date'}</span>
                    <Input
                      type="date"
                      value={dateFromFilter}
                      onChange={(event) => {
                        setDateFromFilter(event.target.value);
                        setSortMode('date');
                      }}
                      className="bg-white"
                    />
                  </label>
                  <label className="grid gap-1 text-xs font-medium text-slate-600">
                    <span>{isRu ? 'По дату' : 'To date'}</span>
                    <Input
                      type="date"
                      value={dateToFilter}
                      onChange={(event) => {
                        setDateToFilter(event.target.value);
                        setSortMode('date');
                      }}
                      className="bg-white"
                    />
                  </label>
                  <Button type="button" variant="outline" onClick={resetViewState}>
                    {isRu ? 'Сбросить' : 'Reset'}
                  </Button>
                </div>
              </div>
              <div className="mt-3 text-xs text-slate-500">
                <span className="font-medium text-slate-700">
                  {isRu ? 'Сейчас показано:' : 'Current view:'}
                </span>{' '}
                {_itemFilterLabel(selectedItemFilter, isRu)}
                {dateFromFilter || dateToFilter
                  ? ` · ${dateFromFilter || '...'} - ${dateToFilter || '...'}`
                  : ` · ${isRu ? 'все даты' : 'all dates'}`}
              </div>
    </>
  );
};
