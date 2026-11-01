import { useEffect, useRef } from "react";

export default function CompletionDialog({ review, busy, error, onCancel, onConfirm, onAcknowledge }) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialog.showModal();
    return () => {
      if (dialog.open) dialog.close();
      document.body.style.overflow = previous;
    };
  }, []);
  const blocked = review.blocked;
  const gaps = review.missing_count || 0;
  return (
    <dialog ref={ref} className="completion-dialog" aria-labelledby="completion-title"
      onCancel={event => { event.preventDefault(); if (!busy) onCancel(); }}>
      <div className="completion-heading">
        <div><p className="eyebrow">Лист аудита</p>
          <h2 id="completion-title">{blocked ? "Есть наброски наблюдений" : "Завершить проверку?"}</h2></div>
        <button type="button" className="observation-close" disabled={busy} onClick={onCancel} aria-label="Закрыть">×</button>
      </div>
      {error && <p className="notice error" role="alert">{error}</p>}
      {blocked ? <>
        <p>На устройстве остались незафиксированные наброски: <strong>{review.scratch_count}</strong>.</p>
        <p>Откройте «Журнал», зафиксируйте их как наблюдения или удалите ненужные наброски. Затем повторите завершение.</p>
        <p className="muted">Наброски сохранены на устройстве. Проверка пока остаётся черновиком.</p>
      </> : <>
        <p>После подтверждения текущие данные сохранятся на сервере, а в расписании появится статус «Завершена».</p>
        {gaps ? <>
          <p className="completion-gap-summary">Не заполнено: <strong>{gaps}</strong>. Если данные не наблюдались или неприменимы, можно завершить проверку с пропусками.</p>
          <div className="completion-gaps">
            {review.warnings.map((group, index) => <details key={index} open>
              <summary>{group.group} · {group.items.length}</summary>
              <ul>{group.items.map((item, itemIndex) => <li key={itemIndex}>{item}</li>)}</ul>
            </details>)}
          </div>
          <label className="completion-acknowledgement">
            <input type="checkbox" checked={review.acknowledged || false} disabled={busy}
              onChange={event => onAcknowledge(event.target.checked)} />
            <span>Перечень просмотрен. Подтверждаю завершение с указанными пропусками.</span>
          </label>
        </> : <p className="notice">Пропусков по проверяемым полям не найдено.</p>}
        <p className="muted">Для уточнений после обсуждения проверку можно будет вернуть в работу.</p>
      </>}
      <div className="completion-actions">
        <button type="button" className="outline" disabled={busy} onClick={onCancel}>Вернуться к заполнению</button>
        {!blocked && <button type="button" className="primary" disabled={busy || (gaps > 0 && !review.acknowledged)} onClick={onConfirm}>
          {busy ? "Сохраняем и завершаем…" : "Подтвердить завершение"}
        </button>}
      </div>
    </dialog>
  );
}
