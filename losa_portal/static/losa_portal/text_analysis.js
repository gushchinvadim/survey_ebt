document.addEventListener('DOMContentLoaded', () => {
  const source = document.getElementById('source-text');
  const quote = document.getElementById('quote-field');
  const button = document.getElementById('copy-selection');
  let selected = '';
  document.addEventListener('selectionchange', () => {
    const selection = window.getSelection();
    if (selection && selection.rangeCount && source.contains(selection.anchorNode) && source.contains(selection.focusNode)) {
      selected = selection.toString();
    }
  });
  button.addEventListener('click', () => {
    const message = document.getElementById('selection-message');
    if (!selected.trim()) { message.textContent = 'Сначала выделите фрагмент исходного текста.'; return; }
    quote.value = selected;
    message.textContent = 'Фрагмент перенесён в цитату. Выберите темы и характер наблюдения.';
    quote.focus();
  });
});
