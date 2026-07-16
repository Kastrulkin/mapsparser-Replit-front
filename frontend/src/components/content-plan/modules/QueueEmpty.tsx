import React from 'react';

export const QueueEmpty = ({ scope }) => {
  const {
    isRu, queueSearch, visibleItems
  } = scope;
  return (
    <>
            {visibleItems.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-6 py-8 text-sm text-slate-600">
                <div className="font-semibold text-slate-950">
                  {isRu ? 'В этом виде ничего не найдено' : 'Nothing found in this view'}
                </div>
                <div className="mt-1 leading-6">
                  {queueSearch.trim()
                    ? (isRu
                      ? 'Очистите поиск или нажмите «Сбросить», чтобы снова увидеть всю очередь выбранного плана.'
                      : 'Clear search or reset the view to see the full selected plan queue again.')
                    : (isRu
                      ? 'Для выбранного состояния или периода пока нет публикаций. Нажмите «Сбросить» или выберите другой период.'
                      : 'There are no items for this status or period yet. Reset the view or choose another period.')}
                </div>
              </div>
            ) : null}
    </>
  );
};
