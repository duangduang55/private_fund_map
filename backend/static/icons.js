/* 私募基金拓客辅助系统 — SVG 图标助手 */
/* 在需要图标替换的页面中引用：<script src="/static/icons.js"></script> */

const ICONS = {
  star: '<svg class="icon icon-sm" viewBox="0 0 24 24" fill="currentColor" style="color:#fbbf24"><use href="/static/icons.svg#icon-star"/></svg>',
  starOutline: '<svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color:#94a3b8"><use href="/static/icons.svg#icon-star-outline"/></svg>',
  check: '<svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><use href="/static/icons.svg#icon-check"/></svg>',
  checkCircle: '<svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><use href="/static/icons.svg#icon-check-circle"/></svg>',
  clock: '<svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><use href="/static/icons.svg#icon-clock"/></svg>',
  x: '<svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><use href="/static/icons.svg#icon-x"/></svg>',
  cart: '<svg class="icon icon-md" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><use href="/static/icons.svg#icon-cart"/></svg>',
  search: '<svg class="icon icon-md" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><use href="/static/icons.svg#icon-search"/></svg>',
  list: '<svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><use href="/static/icons.svg#icon-list"/></svg>',
  document: '<svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><use href="/static/icons.svg#icon-document"/></svg>',
  mapPin: '<svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><use href="/static/icons.svg#icon-map-pin"/></svg>',
  arrowLeft: '<svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><use href="/static/icons.svg#icon-arrow-left"/></svg>',
  print: '<svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><use href="/static/icons.svg#icon-print"/></svg>',
  trash: '<svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><use href="/static/icons.svg#icon-trash"/></svg>',
  home: '<svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><use href="/static/icons.svg#icon-home"/></svg>',
};

/* Helper: SVG icon + text label for status display */
function iconLabel(iconName, label, color) {
  const icon = ICONS[iconName] || '';
  const style = color ? ` style="color:${color}"` : '';
  return `<span${style}>${icon} ${label}</span>`;
}
