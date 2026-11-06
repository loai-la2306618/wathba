// Reicon Outline SVGs, pinned and self-hosted. See assets/reicon/NOTICE.md.
const names=new Set(["arrow-left", "arrow-right-up", "repeat", "clock", "accessibility", "user-scan", "camera", "pause", "play", "skip-next", "skip-prev", "check-circle", "check", "info-circle", "chat-round-line", "sparkles", "upload", "download", "document-text", "stop", "record-circle", "target", "chart-line", "home", "shield-check", "user", "search", "share", "settings", "arrow-right", "heart", "calendar", "notes", "xmark", "more-h"]);
export function icon(name){
 if(!names.has(name))throw Error(`Unknown Reicon icon: ${name}`);
 return `<svg class="reicon" aria-hidden="true" focusable="false"><use href="/assets/reicon/sprite.svg#${name}"></use></svg>`;
}
export function setIcon(element,name){if(element.dataset.icon===name)return;element.innerHTML=icon(name);element.dataset.icon=name;}
