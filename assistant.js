(() => {
  'use strict';

  if (window.__zajel_assistant_initialized) return;
  window.__zajel_assistant_initialized = true;

  /* ==========================================================================
     1. أيقونات SVG النقية (بدون أي innerHTML)
     ========================================================================== */
  const SVG_NS = 'http://www.w3.org/2000/svg';

  function createSvg(iconName, size = 16, strokeWidth = 2) {
    const svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('width', String(size));
    svg.setAttribute('height', String(size));
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('fill', 'none');
    svg.setAttribute('stroke', 'currentColor');
    svg.setAttribute('stroke-width', String(strokeWidth));
    svg.setAttribute('stroke-linecap', 'round');
    svg.setAttribute('stroke-linejoin', 'round');
    svg.setAttribute('aria-hidden', 'true');
    svg.classList.add('as-svg-ico');

    const appendPath = (d, fill = 'none') => {
      const path = document.createElementNS(SVG_NS, 'path');
      path.setAttribute('d', d);
      if (fill !== 'none') path.setAttribute('fill', fill);
      svg.appendChild(path);
      return path;
    };

    const appendCircle = (cx, cy, r, fill = 'none') => {
      const c = document.createElementNS(SVG_NS, 'circle');
      c.setAttribute('cx', String(cx));
      c.setAttribute('cy', String(cy));
      c.setAttribute('r', String(r));
      if (fill !== 'none') c.setAttribute('fill', fill);
      svg.appendChild(c);
      return c;
    };

    switch (iconName) {
      case 'queue': // طابور التعقيبات والمهام
        appendPath('M4 6h16');
        appendPath('M4 12h16');
        appendPath('M4 18h10');
        appendPath('M18 16l3 2-3 2v-4z');
        break;

      case 'bot': // مساعد ذكي
        appendPath('M12 2v3');
        appendPath('M8 8a4 4 0 0 1 8 0v1h1a3 3 0 0 1 3 3v4a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3v-4a3 3 0 0 1 3-3h1V8z');
        appendCircle(9, 13, 1.2, 'currentColor');
        appendCircle(15, 13, 1.2, 'currentColor');
        appendPath('M10 16h4');
        break;

      case 'menu': // قائمة الشريط الجانبي ☰
        appendPath('M3 12h18');
        appendPath('M3 6h18');
        appendPath('M3 18h18');
        break;

      case 'chat': // تبويب المحادثات
        appendPath('M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z');
        break;

      case 'brain': // تبويب الذاكرة
        appendPath('M12 2a4 4 0 0 0-4 4v1H7a3 3 0 0 0-3 3v2a3 3 0 0 0 2 2.83V16a4 4 0 0 0 4 4h4a4 4 0 0 0 4-4v-1.17A3 3 0 0 0 20 12v-2a3 3 0 0 0-3-3h-1V6a4 4 0 0 0-4-4z');
        appendPath('M12 8v8');
        appendPath('M8 12h8');
        break;

      case 'spark': // تبويب الأوامر الجاهزة
        appendPath('M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8L12 2z');
        break;

      case 'settings': // ترس الإعدادات
        appendCircle(12, 12, 3);
        appendPath('M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z');
        break;

      case 'star': // نجمة فارغة
        appendPath('M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z');
        break;

      case 'star-filled': // نجمة ممتلئة
        appendPath('M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z', 'currentColor');
        break;

      case 'pin': // دبوس تثبيت مفرغ
        appendPath('M16 12V4a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v8l-2 3v1h5.2v5l.8.8.8-.8v-5H18v-1l-2-3z');
        break;

      case 'pin-filled': // دبوس تثبيت ممتلئ
        appendPath('M16 12V4a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v8l-2 3v1h5.2v5l.8.8.8-.8v-5H18v-1l-2-3z', 'currentColor');
        break;

      case 'refresh': // تحديث دوري
        appendPath('M21.5 2v6h-6');
        appendPath('M21.34 15.57a9 9 0 1 1-.57-8.38l5.67-5.19');
        break;

      case 'copy': // نسخ للحافظة
        appendPath('M9 9h11a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2z');
        appendPath('M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1');
        break;

      case 'check': // نجاح / تم
        appendPath('M20 6L9 17l-5-5');
        break;

      case 'stop': // إيقاف
        appendPath('M6 6h12v12H6z', 'currentColor');
        break;

      case 'plus': // جديد
        appendPath('M12 5v14');
        appendPath('M5 12h14');
        break;

      case 'close': // إغلاق
        appendPath('M18 6L6 18');
        appendPath('M6 6l12 12');
        break;

      case 'send': // إرسال
        appendPath('M22 2L11 13');
        appendPath('M22 2l-7 20-4-9-9-4 20-7z');
        break;

      case 'activity': // الحالة
        appendPath('M22 12h-4l-3 9L9 3l-3 9H2');
        break;

      case 'layers': // العمليات
        appendPath('M12 2L2 7l10 5 10-5-10-5z');
        appendPath('M2 17l10 5 10-5');
        appendPath('M2 12l10 5 10-5');
        break;

      case 'ban': // أوقف الكل
        appendCircle(12, 12, 10);
        appendPath('M4.93 4.93l14.14 14.14');
        break;

      case 'shield-alert': // موافقة مطلوبة
        appendPath('M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z');
        appendPath('M12 8v4');
        appendPath('M12 16h.01');
        break;

      case 'chevron-down': // سهم لأسفل
        appendPath('M6 9l6 6 6-6');
        break;

      case 'swap': // تجربة مصدر آخر
        appendPath('M7 16V4m0 0L3 8m4-4l4 4');
        appendPath('M17 8v12m0 0l4-4m-4 4l-4-4');
        break;

      case 'folder': // مجلد سياق
        appendPath('M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z');
        break;

      case 'search': // بحث
        appendCircle(11, 11, 8);
        appendPath('M21 21l-4.35-4.35');
        break;

      case 'trash': // حذف
        appendPath('M3 6h18');
        appendPath('M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2');
        break;

      case 'edit': // تعديل / إعادة تسمية
        appendPath('M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7');
        appendPath('M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z');
        break;

      case 'maximize': // توسيع
        appendPath('M15 3h6v6');
        appendPath('M9 21H3v-6');
        appendPath('M21 3l-7 7');
        appendPath('M3 21l7-7');
        break;

      case 'minimize': // تصغير
        appendPath('M4 14h6v6');
        appendPath('M20 10h-6V4');
        appendPath('M14 10l7-7');
        appendPath('M10 14L3 21');
        break;

      case 'arrow-down': // إلى الأسفل
        appendPath('M12 5v14');
        appendPath('M19 12l-7 7-7-7');
        break;

      case 'smartphone': // هاتف لاسلكي
        appendPath('M7 2h10a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z');
        appendPath('M11 18h2');
        break;

      case 'clip': // مشبك ورق / إرفاق
        appendPath('M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48');
        break;

      default:
        appendCircle(12, 12, 8);
    }

    return svg;
  }

  /* ==========================================================================
     2. حقن الأنماط (CSS) المتناسقة مع التطبيق في الوضعين الفاتح والداكن
     ========================================================================== */
  const STYLE_ID = 'as-assistant-styles';
  if (!document.getElementById(STYLE_ID)) {
    const styleEl = document.createElement('style');
    styleEl.id = STYLE_ID;
    styleEl.textContent = `
      /* ==========================================================================
         تصميم احترافي هادئ وعصري لمساعد زاجل الذكي (مستوى Linear / Arc)
         نظام تباعد موحد: 4 / 8 / 12 / 16 / 24 | أنصاف أقطار ناعمة | ظلال خفيفة
         ========================================================================== */

      /* زر الشريحة في الشريط العلوي */
      #as-chip {
        cursor: pointer;
        user-select: none;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        position: relative;
        font-weight: 500;
        font-size: 12px;
        padding: 4px 10px;
        border-radius: 6px;
        color: var(--ink);
        background: transparent;
        transition: background-color 0.14s ease, color 0.14s ease, transform 0.1s ease;
      }
      #as-chip:hover {
        background: var(--accp);
        color: var(--acc);
      }
      #as-chip.active {
        background: var(--accp);
        color: var(--acc);
        font-weight: 600;
      }
      #as-chip:active {
        transform: scale(0.96);
      }
      #as-chip.as-alert::after {
        content: "";
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: var(--err);
        display: inline-block;
        margin-inline-start: 4px;
        box-shadow: 0 0 6px var(--err);
        animation: as-pulse 1.4s infinite ease-in-out;
      }
      @keyframes as-pulse {
        0%, 100% { transform: scale(1); opacity: 1; }
        50% { transform: scale(1.3); opacity: 0.6; }
      }

      /* نافذة المساعد الرئيسية */
      .as-panel {
        position: fixed;
        inset-inline-end: 0;
        top: 44px;
        bottom: 0;
        height: calc(100vh - 44px);
        width: 760px;
        max-width: min(1200px, 96vw);
        min-width: 320px;
        z-index: 55;
        background: var(--panel);
        border-inline-start: 1px solid var(--line);
        box-shadow: -4px 0 24px rgba(0, 0, 0, 0.07), -1px 0 3px rgba(0, 0, 0, 0.03);
        display: flex;
        flex-direction: column;
        color: var(--ink);
        box-sizing: border-box;
        font-family: inherit;
        direction: rtl;
        transition: width 0.18s cubic-bezier(0.16, 1, 0.3, 1), transform 0.18s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.15s ease;
        overflow: hidden;
      }
      .as-panel.as-expanded {
        width: min(1200px, 96vw) !important;
      }
      .as-panel[hidden] {
        display: none !important;
      }
      .as-panel.as-resizing {
        transition: none !important;
      }
      body.as-resizing-active,
      body.as-resizing-active * {
        user-select: none !important;
        -webkit-user-select: none !important;
      }
      @media (max-width: 600px) {
        .as-panel {
          width: 100vw !important;
          max-width: 100vw !important;
          border-inline-start: none;
          box-shadow: none;
        }
      }

      /* مقبض سحب الحافة لتغيير الحجم */
      .as-resize-grip {
        position: absolute;
        top: 0;
        bottom: 0;
        inset-inline-start: 0;
        width: 6px;
        cursor: col-resize;
        z-index: 90;
        transition: background 0.14s ease;
      }
      .as-resize-grip::before {
        content: '';
        position: absolute;
        top: 0;
        bottom: 0;
        inset-inline-start: 0;
        width: 2px;
        background: transparent;
        transition: background 0.14s ease, box-shadow 0.14s ease;
      }
      .as-resize-grip:hover::before,
      .as-resize-grip.is-dragging::before {
        background: var(--acc);
        box-shadow: 0 0 6px var(--acc);
      }
      .as-resize-grip:hover,
      .as-resize-grip.is-dragging {
        background: color-mix(in srgb, var(--accp) 50%, transparent);
      }

      /* الزر الدائري الصغير العائم عند التصغير */
      .as-floating-btn {
        position: fixed;
        bottom: 24px;
        inset-inline-end: 24px;
        width: 44px;
        height: 44px;
        border-radius: 50%;
        background: var(--panel);
        border: 1px solid var(--line);
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.12), 0 2px 4px rgba(0, 0, 0, 0.06);
        color: var(--ink);
        cursor: pointer;
        z-index: 1000;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0;
        transition: transform 0.14s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.14s ease, border-color 0.14s ease;
      }
      .as-floating-btn:hover {
        transform: scale(1.07);
        border-color: var(--acc);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.16), 0 2px 6px rgba(0, 0, 0, 0.08);
      }
      .as-floating-btn:active {
        transform: scale(0.96);
      }
      .as-floating-btn[hidden] {
        display: none !important;
      }
      .as-floating-alert-badge {
        position: absolute;
        top: 0px;
        inset-inline-end: 0px;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: var(--err);
        border: 2px solid var(--panel);
        box-shadow: 0 0 6px var(--err);
        animation: as-pulse 1.2s infinite ease-in-out;
      }
      .as-floating-busy-badge {
        position: absolute;
        top: 0px;
        inset-inline-end: 0px;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: var(--acc);
        border: 2px solid var(--panel);
        box-shadow: 0 0 6px var(--acc);
        animation: as-pulse 1.4s infinite ease-in-out;
      }

      /* ترويسة النافذة هادئة وأنيقة */
      .as-head {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 0 12px;
        border-bottom: 1px solid var(--line);
        background: var(--panel);
        flex-shrink: 0;
        height: 44px;
        min-height: 44px;
      }
      .as-head-start {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        flex: none;
      }
      .as-source-badge {
        flex: 1;
        min-width: 0;
        display: inline-flex;
        align-items: center;
        justify-content: space-between;
        gap: 6px;
        padding: 4px 10px;
        background: var(--side);
        border: 1px solid transparent;
        border-radius: 8px;
        font-size: 11.5px;
        color: var(--ink);
        cursor: pointer;
        user-select: none;
        transition: border-color 0.14s ease, background-color 0.14s ease;
      }
      .as-source-badge:hover {
        border-color: var(--line);
        background: color-mix(in srgb, var(--accp) 50%, var(--side));
      }
      .as-source-text {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        direction: ltr;
        unicode-bidi: embed;
        font-weight: 500;
      }
      .as-badge-arrow {
        color: var(--mut);
        flex: none;
        display: inline-flex;
      }
      .as-head-actions {
        display: inline-flex;
        align-items: center;
        gap: 2px;
        flex: none;
      }
      .as-icon-btn {
        border: 1px solid transparent;
        background: transparent;
        color: var(--mut);
        width: 30px;
        height: 30px;
        border-radius: 7px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        padding: 0;
        transition: background-color 0.14s ease, color 0.14s ease, border-color 0.14s ease;
      }
      .as-icon-btn:hover {
        background: var(--side);
        color: var(--ink);
        border-color: var(--line);
      }
      .as-icon-btn:active {
        transform: scale(0.95);
      }
      .as-icon-btn.as-active {
        background: var(--accp);
        color: var(--acc);
      }

      /* جسم النافذة */
      .as-body-layout {
        display: flex;
        flex: 1;
        min-height: 0;
        position: relative;
        overflow: hidden;
      }

      /* الشريط الجانبي */
      .as-sidebar {
        width: 300px;
        max-width: 85vw;
        flex-shrink: 0;
        display: flex;
        flex-direction: column;
        border-inline-end: 1px solid var(--line);
        background: var(--side);
        transition: width 0.18s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.15s ease;
        overflow: hidden;
      }
      .as-sidebar.as-sidebar-closed {
        width: 0 !important;
        border-inline-end: none !important;
        opacity: 0;
        pointer-events: none;
      }
      @media (max-width: 600px) {
        .as-sidebar {
          position: absolute;
          inset: 0;
          width: 100% !important;
          max-width: 100% !important;
          z-index: 20;
          border-inline-end: none;
        }
      }
      /* نافذة ضيقة (أقل من ٧٢٠): الشريط الجانبي يغطي النافذة بدل أن يزاحم المحادثة فيكسر التخطيط */
      .as-panel.as-narrow .as-sidebar {
        position: absolute;
        inset: 0;
        width: 100% !important;
        max-width: 100% !important;
        z-index: 20;
        border-inline-end: none;
      }
      .as-panel.as-narrow .as-sidebar { background: var(--panel); box-shadow: none; }
      .as-panel.as-narrow .as-sidebar.as-sidebar-closed { width: 0 !important; }
      @media (max-width: 600px) { .as-sidebar { background: var(--panel); } }
      .as-panel { min-width: min(240px, 100vw); }
      .as-panel:not(.as-narrow) .as-sidebar { position: relative; }
      .as-sidebar-grip { position: absolute; top: 0; bottom: 0; inset-inline-end: 0; width: 6px; cursor: col-resize; z-index: 6; }
      .as-sidebar-grip:hover, .as-sidebar-grip.is-dragging { background: linear-gradient(90deg, transparent 2px, var(--acc) 2px, var(--acc) 4px, transparent 4px); }

      /* تبويبات الشريط الجانبي */
      .as-side-tabs {
        display: flex;
        border-bottom: 1px solid var(--line);
        background: var(--panel);
        flex-shrink: 0;
        padding: 3px 6px;
        gap: 3px;
      }
      .as-tab-btn {
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 4px;
        padding: 6px 4px;
        background: transparent;
        border: none;
        border-radius: 6px;
        color: var(--mut);
        font-size: 11px;
        font-weight: 500;
        cursor: pointer;
        transition: color 0.14s ease, background-color 0.14s ease;
      }
      .as-tab-btn:hover {
        color: var(--ink);
        background: var(--side);
      }
      .as-tab-btn.as-active-tab {
        color: var(--acc);
        background: var(--accp);
        font-weight: 600;
      }

      /* محتوى التبويب النشط */
      .as-side-content {
        flex: 1;
        min-height: 0;
        overflow-y: auto;
        padding: 10px;
        display: flex;
        flex-direction: column;
        gap: 8px;
        scrollbar-width: thin;
      }

      /* حقول وقوائم الشريط الجانبي */
      .as-side-input, .as-select, .as-input-text {
        width: 100%;
        box-sizing: border-box;
        padding: 7px 10px;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: var(--bg);
        color: var(--ink);
        font-size: 12px;
        outline: none;
        transition: border-color 0.14s ease, box-shadow 0.14s ease;
      }
      .as-side-input:focus, .as-select:focus, .as-input-text:focus {
        border-color: var(--acc);
        box-shadow: 0 0 0 2px var(--accp);
      }

      /* بطاقات المحادثات */
      .as-chat-item {
        border: 1px solid transparent;
        background: var(--panel);
        border-radius: 8px;
        padding: 8px 10px;
        display: flex;
        flex-direction: column;
        gap: 4px;
        cursor: pointer;
        transition: border-color 0.14s ease, background-color 0.14s ease;
        position: relative;
      }
      .as-chat-item:hover {
        border-color: var(--line);
        background: color-mix(in srgb, var(--accp) 35%, var(--panel));
      }
      .as-chat-item.is-current {
        border-color: color-mix(in srgb, var(--acc) 40%, var(--line));
        background: color-mix(in srgb, var(--accp) 65%, var(--panel));
      }
      .as-chat-item-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 6px;
      }
      .as-chat-title-wrap {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        flex: 1;
        min-width: 0;
      }
      .as-active-dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: var(--ok);
        flex-shrink: 0;
      }
      .as-chat-title {
        font-size: 12px;
        font-weight: 500;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        color: var(--ink);
      }
      .as-chat-item-actions {
        display: inline-flex;
        align-items: center;
        gap: 2px;
        flex-shrink: 0;
      }
      .as-item-mini-btn {
        border: none;
        background: transparent;
        color: var(--mut);
        padding: 3px;
        border-radius: 5px;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        transition: color 0.14s ease, background-color 0.14s ease;
      }
      .as-item-mini-btn:hover {
        color: var(--err);
        background: color-mix(in srgb, var(--err) 10%, transparent);
      }
      .as-item-mini-btn.edit-btn:hover {
        color: var(--acc);
        background: var(--accp);
      }
      .as-chat-meta {
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-size: 10.5px;
        color: var(--mut);
        gap: 6px;
      }

      /* بطاقات الذاكرة والأوامر */
      .as-memory-card, .as-prompt-card {
        border: 1px solid var(--line);
        background: var(--panel);
        border-radius: 8px;
        padding: 8px 10px;
        display: flex;
        flex-direction: column;
        gap: 6px;
        font-size: 12px;
        position: relative;
        transition: border-color 0.14s ease, background-color 0.14s ease;
      }
      .as-prompt-card {
        cursor: pointer;
      }
      .as-prompt-card:hover {
        border-color: var(--acc);
        background: var(--accp);
      }
      .as-card-top-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 6px;
      }
      .as-card-body-text {
        font-size: 12px;
        line-height: 1.5;
        color: var(--ink);
        white-space: pre-wrap;
        word-break: break-word;
      }

      /* رأس تبويب الذاكرة وتنسيقاته */
      .as-memory-head-box {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 10px;
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .as-memory-head-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
      }
      .as-memory-desc {
        font-size: 11px;
        line-height: 1.45;
        color: var(--mut);
        flex: 1;
      }
      .as-toggle-label {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        cursor: pointer;
        user-select: none;
        font-size: 11px;
        font-weight: 500;
        color: var(--ink);
        flex-shrink: 0;
      }
      .as-switch-native {
        position: absolute;
        opacity: 0;
        width: 0;
        height: 0;
        pointer-events: none;
      }
      .as-switch-track {
        width: 30px;
        height: 16px;
        background: var(--line);
        border-radius: 10px;
        display: inline-flex;
        align-items: center;
        padding: 2px;
        transition: background-color 0.18s ease;
        box-sizing: border-box;
      }
      .as-toggle-label.is-active .as-switch-track {
        background: var(--acc);
      }
      .as-switch-thumb {
        width: 12px;
        height: 12px;
        background: #ffffff;
        border-radius: 50%;
        box-shadow: 0 1px 2px rgba(0,0,0,0.2);
        margin-inline-start: 0;
        transition: margin-inline-start 0.18s ease;
      }
      .as-toggle-label.is-active .as-switch-thumb {
        margin-inline-start: 14px;
      }
      .as-organize-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        width: 100%;
        padding: 7px 10px;
        font-size: 11.5px;
        font-weight: 500;
        border-radius: 7px;
        background: var(--acc);
        color: #ffffff;
        border: 1px solid var(--acc);
        cursor: pointer;
        transition: opacity 0.14s ease;
      }
      .as-organize-btn:hover:not(:disabled) {
        opacity: 0.92;
      }
      .as-organize-btn:disabled {
        opacity: 0.6;
        cursor: not-allowed;
      }
      .as-organize-status-row {
        display: flex;
        flex-direction: column;
        gap: 4px;
        font-size: 10.5px;
        color: var(--mut);
      }
      .as-organize-note {
        font-size: 10.5px;
        color: var(--ink);
        background: var(--side);
        border-inline-start: 3px solid var(--acc);
        padding: 4px 7px;
        border-radius: 4px;
        line-height: 1.4;
      }
      .as-memory-section {
        display: flex;
        flex-direction: column;
        gap: 5px;
      }
      .as-memory-sec-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 4px 6px;
        border-radius: 6px;
        cursor: pointer;
        user-select: none;
        font-size: 11.5px;
        font-weight: 600;
        color: var(--ink);
        transition: background-color 0.12s ease;
      }
      .as-memory-sec-head:hover {
        background: var(--line);
      }
      .as-memory-sec-title {
        display: inline-flex;
        align-items: center;
        gap: 6px;
      }
      .as-sec-count {
        font-size: 10px;
        font-weight: 500;
        background: color-mix(in srgb, var(--ink) 8%, transparent);
        color: var(--mut);
        padding: 1px 5px;
        border-radius: 10px;
      }
      .as-sec-chevron {
        transition: transform 0.18s ease;
        color: var(--mut);
        display: inline-flex;
      }
      .as-memory-section.is-collapsed .as-sec-chevron {
        transform: rotate(90deg);
      }
      .as-memory-section.is-collapsed .as-memory-sec-list {
        display: none;
      }
      .as-memory-sec-list {
        display: flex;
        flex-direction: column;
        gap: 5px;
      }
      .as-memory-card.is-pinned {
        border-color: color-mix(in srgb, var(--acc) 35%, var(--line));
        background: color-mix(in srgb, var(--acc) 3%, var(--panel));
      }
      .as-pill.pinned {
        background: var(--accp);
        color: var(--acc);
        font-weight: 500;
        display: inline-flex;
        align-items: center;
        gap: 3px;
      }
      .as-pill.uses {
        background: color-mix(in srgb, var(--ink) 6%, transparent);
        color: var(--mut);
      }
      .as-item-mini-btn.pin-btn.is-pinned {
        color: var(--acc);
        background: var(--accp);
      }
      .as-memory-empty {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        padding: 24px 12px;
        gap: 8px;
        color: var(--mut);
        background: var(--panel);
        border: 1px dashed var(--line);
        border-radius: 8px;
      }
      .as-memory-empty-title {
        font-size: 12px;
        font-weight: 600;
        color: var(--ink);
      }
      .as-memory-empty-desc {
        font-size: 11px;
        line-height: 1.45;
        max-width: 250px;
      }
      .as-spin {
        animation: as-spin 1s linear infinite;
        display: inline-block;
      }
      @keyframes as-spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
      }

      /* المنطقة الرئيسية: المحادثة والإدخال */
      .as-main {
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
        background: var(--panel);
        position: relative;
        min-height: 0;
      }

      /* بطاقات الموافقة المعلقة أعلى المحادثة */
      .as-pending-area {
        display: flex;
        flex-direction: column;
        gap: 6px;
        padding: 8px 12px;
        background: var(--side);
        border-bottom: 1px solid var(--line);
        flex-shrink: 0;
        max-height: 200px;
        overflow-y: auto;
      }
      .as-pending-toggle-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-size: 11.5px;
        font-weight: 600;
        color: var(--err);
        cursor: pointer;
      }
      .as-card-pending {
        border: 1px solid var(--err);
        border-radius: 8px;
        padding: 8px 10px;
        background: color-mix(in srgb, var(--err) 5%, var(--panel));
        display: flex;
        flex-direction: column;
        gap: 5px;
        font-size: 11.5px;
      }
      .as-pending-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      .as-pending-title {
        font-weight: 600;
        color: var(--err);
        display: inline-flex;
        align-items: center;
        gap: 5px;
      }
      .as-pending-timer {
        font-size: 10.5px;
        font-family: ui-monospace, SFMono-Regular, monospace;
        background: color-mix(in srgb, var(--err) 12%, transparent);
        color: var(--err);
        padding: 1px 5px;
        border-radius: 4px;
        font-weight: 600;
      }
      .as-pending-body {
        display: flex;
        flex-direction: column;
        gap: 3px;
        font-size: 11.5px;
      }
      .as-pending-row {
        display: flex;
        gap: 5px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .as-pending-row b {
        color: var(--mut);
        font-weight: 500;
        white-space: nowrap;
      }
      .as-pending-row span {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .as-word-box {
        margin-top: 4px;
      }

      /* حاوية المحادثة الفسيحة */
      .as-chat {
        flex: 1;
        overflow-y: auto;
        padding: 16px 20px;
        display: flex;
        flex-direction: column;
        gap: 16px;
        min-height: 0;
        scrollbar-width: thin;
      }

      /* الحالة الترحيبية */
      .as-empty-state {
        margin: auto;
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        max-width: 440px;
        padding: 24px 12px;
        gap: 10px;
        animation: as-msg-fade 0.2s ease-out;
      }
      .as-empty-icon {
        width: 48px;
        height: 48px;
        border-radius: 12px;
        background: var(--side);
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--acc);
      }
      .as-empty-title {
        font-size: 14.5px;
        font-weight: 600;
        color: var(--ink);
      }
      .as-empty-desc {
        font-size: 12px;
        line-height: 1.55;
        color: var(--mut);
      }
      .as-suggestions-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 6px;
        width: 100%;
        margin-top: 6px;
      }
      @media (max-width: 500px) {
        .as-suggestions-grid {
          grid-template-columns: 1fr;
        }
      }
      .as-suggestion-chip {
        padding: 8px 12px;
        border-radius: 8px;
        border: 1px solid var(--line);
        background: var(--side);
        color: var(--ink);
        font-size: 12px;
        text-align: start;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 6px;
        transition: background-color 0.14s ease, border-color 0.14s ease, color 0.14s ease;
      }
      .as-suggestion-chip:hover {
        background: var(--accp);
        border-color: var(--acc);
        color: var(--acc);
      }

      /* زر التمرير إلى الأسفل */
      .as-scroll-bottom {
        position: absolute;
        bottom: 80px;
        inset-inline-start: 50%;
        transform: translateX(50%);
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: var(--panel);
        border: 1px solid var(--line);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
        color: var(--ink);
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        z-index: 25;
        transition: transform 0.14s ease, background-color 0.14s ease;
      }
      .as-scroll-bottom:hover {
        background: var(--side);
        transform: translateX(50%) scale(1.08);
      }
      .as-scroll-bottom[hidden] {
        display: none !important;
      }

      /* فقاعات الرسائل: تصميم هادئ مع مساحة تنفس، بلا أي تمرير داخلي */
      .as-msg {
        border-radius: 10px;
        font-size: 13px;
        line-height: 1.6;
        word-break: break-word;
        box-sizing: border-box;
        animation: as-msg-fade 0.15s ease-out;
      }
      @keyframes as-msg-fade {
        from { opacity: 0; transform: translateY(3px); }
        to { opacity: 1; transform: translateY(0); }
      }
      .as-msg-user {
        align-self: flex-start;
        max-width: 85%;
        background: var(--accp);
        color: var(--ink);
        border: 1px solid color-mix(in srgb, var(--acc) 25%, transparent);
        padding: 9px 13px;
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      .as-msg-bot {
        align-self: flex-start;
        width: 100%;
        background: var(--side);
        color: var(--ink);
        border: 1px solid var(--line);
        padding: 12px 16px;
        display: flex;
        flex-direction: column;
        gap: 8px;
        max-height: none !important;
        overflow: visible !important;
      }
      .as-msg-sys {
        align-self: center;
        background: transparent;
        color: var(--mut);
        font-size: 11px;
        padding: 2px 8px;
        text-align: center;
      }
      .as-msg-err {
        background: color-mix(in srgb, var(--err) 8%, var(--panel));
        border: 1px solid color-mix(in srgb, var(--err) 25%, transparent);
        color: var(--ink);
        padding: 10px 14px;
        border-radius: 8px;
        display: flex;
        flex-direction: column;
        gap: 6px;
      }

      /* وسام الطابور على فقاعة المستخدم */
      .as-queue-pill {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-size: 10px;
        font-weight: 600;
        color: var(--acc);
        background: color-mix(in srgb, var(--accp) 80%, var(--panel));
        border: 1px solid color-mix(in srgb, var(--acc) 30%, transparent);
        padding: 2px 7px;
        border-radius: 99px;
        margin-top: 4px;
        align-self: flex-start;
      }

      /* شريط التعقيبات المنتظرة في الطابور فوق المدخل */
      .as-queued-bar {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 6px 14px;
        background: color-mix(in srgb, var(--accp) 75%, var(--panel));
        border-top: 1px solid color-mix(in srgb, var(--acc) 20%, transparent);
        color: var(--ink);
        font-size: 11.5px;
        font-weight: 500;
        animation: as-msg-fade 0.14s ease-out;
        flex-shrink: 0;
      }
      .as-queued-bar[hidden] {
        display: none !important;
      }
      .as-queued-bar-icon {
        color: var(--acc);
        display: inline-flex;
        align-items: center;
        flex-shrink: 0;
      }
      .as-queued-bar-text {
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      /* تنسيق النصوص داخل الفقاعة */
      .as-msg-body {
        display: flex;
        flex-direction: column;
        gap: 6px;
        max-height: none !important;
        overflow: visible !important;
      }
      .as-para {
        margin: 0;
        line-height: 1.6;
      }
      .as-bullet-list {
        margin: 2px 0;
        padding-inline-start: 18px;
        display: flex;
        flex-direction: column;
        gap: 3px;
      }
      .as-bullet-list li {
        line-height: 1.55;
      }
      .as-inline-code {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-size: 11.5px;
        background: color-mix(in srgb, var(--ink) 7%, transparent);
        padding: 1px 5px;
        border-radius: 4px;
        direction: ltr;
        unicode-bidi: embed;
      }
      .as-code-block {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-size: 12px;
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 8px 12px;
        margin: 4px 0;
        overflow-x: auto;
        direction: ltr;
        text-align: start;
        scrollbar-width: thin;
      }
      .as-code-block code {
        display: block;
        white-space: pre;
      }
      .as-link-text {
        color: var(--acc);
        text-decoration: underline;
        text-underline-offset: 2px;
        direction: ltr;
        unicode-bidi: embed;
      }

      /* شارات وتذييل فقاعة المساعد */
      .as-running-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        font-size: 11.5px;
        color: var(--acc);
        font-weight: 600;
      }
      .as-running-meta {
        display: inline-flex;
        align-items: center;
        gap: 6px;
      }
      .as-typing-pulse {
        display: inline-flex;
        align-items: center;
        gap: 3px;
      }
      .as-typing-dot {
        width: 5px;
        height: 5px;
        border-radius: 50%;
        background: var(--acc);
        animation: as-typing-anim 1s infinite ease-in-out;
      }
      .as-typing-dot:nth-child(2) { animation-delay: 0.2s; }
      .as-typing-dot:nth-child(3) { animation-delay: 0.4s; }
      @keyframes as-typing-anim {
        0%, 100% { transform: scale(0.7); opacity: 0.4; }
        50% { transform: scale(1.2); opacity: 1; }
      }

      .as-steps-timeline {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
        padding: 4px 0;
        border-top: 1px dashed var(--line);
        margin-top: 4px;
      }
      .as-step-badge {
        font-size: 10px;
        padding: 2px 6px;
        border-radius: 99px;
        background: var(--panel);
        border: 1px solid var(--line);
        color: var(--ink);
        display: inline-flex;
        align-items: center;
        gap: 4px;
        white-space: nowrap;
      }
      .as-step-badge b {
        color: var(--acc);
        font-weight: 600;
        direction: ltr;
        unicode-bidi: embed;
      }

      .as-bot-footer {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        padding-top: 6px;
        margin-top: 4px;
        border-top: 1px solid var(--line);
        font-size: 11px;
        color: var(--mut);
      }
      .as-bot-meta-tag {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        direction: ltr;
        unicode-bidi: embed;
      }
      .as-copy-btn {
        border: 1px solid var(--line);
        background: var(--panel);
        border-radius: 6px;
        padding: 2px 7px;
        color: var(--mut);
        cursor: pointer;
        font-size: 10.5px;
        display: inline-flex;
        align-items: center;
        gap: 4px;
        transition: all 0.12s ease;
      }
      .as-copy-btn:hover {
        background: var(--accp);
        border-color: var(--acc);
        color: var(--acc);
      }
      .as-copy-btn.copied {
        border-color: var(--ok);
        color: var(--ok);
        background: color-mix(in srgb, var(--ok) 10%, transparent);
      }

      .as-pill {
        font-size: 10px;
        padding: 1px 6px;
        border-radius: 99px;
        font-weight: 500;
      }
      .as-pill.installed {
        background: color-mix(in srgb, var(--ok) 12%, transparent);
        color: var(--ok);
      }
      .as-pill.missing {
        background: color-mix(in srgb, var(--mut) 12%, transparent);
        color: var(--mut);
      }
      .as-pill.current {
        background: var(--acc);
        color: #fff;
      }
      .as-pill.auto {
        background: color-mix(in srgb, var(--acc) 12%, transparent);
        color: var(--acc);
      }
      .as-pill.stopped {
        background: color-mix(in srgb, var(--mut) 12%, transparent);
        color: var(--mut);
        border: 1px solid color-mix(in srgb, var(--mut) 25%, transparent);
        font-weight: 500;
      }

      /* شارة السياق المدمجة فوق المدخل ونطاق البحث */
      .as-ctx-pill-row {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 4px 14px;
        background: transparent;
        flex-shrink: 0;
        flex-wrap: wrap;
        position: relative;
      }
      .as-ctx-folder-wrap {
        display: inline-flex;
        align-items: center;
        max-width: 100%;
      }
      .as-ctx-folder-wrap:empty {
        display: none;
      }
      .as-ctx-pill {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 3px 8px;
        border-radius: 99px;
        font-size: 11px;
        background: var(--side);
        border: 1px solid var(--line);
        color: var(--ink);
        max-width: 100%;
      }
      .as-ctx-pill-text {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        font-weight: 500;
      }
      .as-ctx-pill-close {
        cursor: pointer;
        color: var(--mut);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 1px;
        border-radius: 50%;
        border: none;
        background: transparent;
      }
      .as-ctx-pill-close:hover {
        color: var(--err);
      }
      .as-ctx-pill-enable {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 2px 7px;
        border-radius: 99px;
        font-size: 10.5px;
        background: transparent;
        border: 1px dashed var(--line);
        color: var(--mut);
        cursor: pointer;
      }
      .as-ctx-pill-enable:hover {
        border-color: var(--acc);
        color: var(--acc);
      }

      /* نطاق البحث والقائمة المنبثقة */
      .as-search-scope-wrap {
        position: relative;
        display: inline-flex;
        align-items: center;
      }
      .as-search-scope-pill {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 3px 8px;
        border-radius: 99px;
        font-size: 11px;
        background: var(--side);
        border: 1px solid var(--line);
        color: var(--ink);
        cursor: pointer;
        user-select: none;
        font-family: inherit;
        transition: background-color 0.14s ease, border-color 0.14s ease, color 0.14s ease;
      }
      .as-search-scope-pill:hover,
      .as-search-scope-pill:focus-visible,
      .as-search-scope-pill.as-active {
        border-color: var(--acc);
        background: var(--accp);
        color: var(--acc);
        outline: none;
      }
      .as-search-scope-text {
        font-weight: 500;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 200px;
      }
      .as-search-scope-popup {
        position: absolute;
        bottom: calc(100% + 6px);
        inset-inline-start: 0;
        min-width: 220px;
        max-width: 320px;
        max-height: 260px;
        overflow-y: auto;
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 8px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.14);
        z-index: 60;
        padding: 6px;
        display: flex;
        flex-direction: column;
        gap: 2px;
        scrollbar-width: thin;
        font-size: 11.5px;
        color: var(--ink);
      }
      .as-search-scope-popup[hidden] {
        display: none !important;
      }
      .as-scope-item {
        display: flex;
        align-items: center;
        gap: 7px;
        padding: 5px 7px;
        border-radius: 6px;
        cursor: pointer;
        user-select: none;
        transition: background-color 0.12s ease;
      }
      .as-scope-item:hover {
        background: var(--accp);
      }
      .as-scope-checkbox {
        cursor: pointer;
        margin: 0;
        accent-color: var(--acc);
        width: 14px;
        height: 14px;
        flex-shrink: 0;
      }
      .as-scope-item-name {
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        font-weight: 500;
      }
      .as-scope-item-tag {
        font-size: 9.5px;
        color: var(--mut);
        background: var(--side);
        border: 1px solid var(--line);
        padding: 1px 5px;
        border-radius: 4px;
        flex-shrink: 0;
      }
      .as-scope-divider {
        height: 1px;
        background: var(--line);
        margin: 3px 0;
        flex-shrink: 0;
      }

      /* شريط الإدخال ومربع النص */
      .as-input-bar {
        display: flex;
        gap: 8px;
        padding: 10px 14px;
        border-top: 1px solid var(--line);
        background: var(--panel);
        flex-shrink: 0;
        align-items: flex-end;
      }
      .as-input-wrap {
        flex: 1;
        position: relative;
        display: flex;
      }
      .as-input {
        width: 100%;
        resize: none;
        height: 38px;
        max-height: 120px;
        min-height: 38px;
        padding: 8px 32px 8px 12px;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: var(--bg);
        color: var(--ink);
        font: inherit;
        font-size: 13px;
        outline: none;
        box-sizing: border-box;
        line-height: 1.5;
        scrollbar-width: thin;
        transition: border-color 0.14s ease, box-shadow 0.14s ease;
      }
      .as-input:focus {
        border-color: var(--acc);
        box-shadow: 0 0 0 2px var(--accp);
      }
      .as-save-prompt-star {
        position: absolute;
        inset-inline-end: 6px;
        bottom: 7px;
        border: none;
        background: transparent;
        color: var(--mut);
        cursor: pointer;
        padding: 4px;
        border-radius: 5px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        transition: color 0.12s ease;
      }
      .as-save-prompt-star:hover {
        color: var(--warn);
      }

      .as-input-actions {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      .as-send-btn {
        padding: 7px 14px;
        font-size: 12px;
        font-weight: 500;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 5px;
        border-radius: 7px;
      }
      .as-stop-btn {
        padding: 4px 8px;
        font-size: 11px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 4px;
        border-radius: 6px;
      }

      /* بطاقات الوكلاء والإعدادات */
      .as-agent-card {
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 9px 10px;
        background: var(--panel);
        display: flex;
        flex-direction: column;
        gap: 6px;
      }
      .as-agent-card.as-active-agent {
        border-color: color-mix(in srgb, var(--acc) 50%, var(--line));
        background: color-mix(in srgb, var(--accp) 40%, var(--panel));
      }
      .as-agent-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 6px;
      }
      .as-agent-title-row {
        display: inline-flex;
        align-items: center;
        gap: 6px;
      }
      .as-agent-name {
        font-weight: 600;
        font-size: 12.5px;
      }
      .as-star-btn {
        border: 1px solid var(--line);
        background: var(--panel);
        color: var(--mut);
        border-radius: 6px;
        padding: 2px 6px;
        font-size: 10.5px;
        display: inline-flex;
        align-items: center;
        gap: 4px;
        cursor: pointer;
      }
      .as-star-btn.is-default {
        border-color: var(--warn);
        color: var(--warn);
        background: var(--warnp);
        font-weight: 500;
      }
      .as-ctrl-row {
        display: flex;
        gap: 6px;
        align-items: center;
      }
      .as-ctrl-lbl {
        font-size: 11px;
        color: var(--mut);
        width: 58px;
        flex: none;
      }
      .as-choose-agent-btn {
        margin-top: 3px;
        width: 100%;
        padding: 5px 8px;
        font-size: 11.5px;
        border-radius: 6px;
        font-weight: 500;
      }
      .as-quick-tools-grid {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr;
        gap: 5px;
        margin-bottom: 6px;
      }
      .as-quick-tools-grid .btn {
        padding: 5px 6px;
        font-size: 11px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 4px;
        white-space: nowrap;
      }
      .as-refresh-models-btn {
        width: 100%;
        padding: 7px 10px;
        font-size: 11.5px;
        font-weight: 500;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        border-radius: 6px;
      }
      .as-refresh-status {
        font-size: 10.5px;
        color: var(--mut);
        text-align: center;
        padding: 3px;
      }

      /* شريط تقدم العمليات */
      .as-op-card {
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 8px 10px;
        background: var(--panel);
        display: flex;
        flex-direction: column;
        gap: 5px;
        font-size: 11.5px;
        margin: 4px 0;
      }
      .as-op-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 6px;
      }
      .as-op-title {
        font-weight: 500;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .as-op-pbar {
        height: 5px;
        border-radius: 3px;
        background: var(--line);
        overflow: hidden;
      }
      .as-op-pbar-fill {
        height: 100%;
        background: var(--acc);
        width: 0%;
        transition: width 0.25s ease;
      }
      .as-op-details {
        display: flex;
        justify-content: space-between;
        color: var(--mut);
        font-size: 10.5px;
        gap: 6px;
        flex-wrap: wrap;
      }
      .as-op-curr {
        font-size: 10.5px;
        color: var(--mut);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        direction: ltr;
        text-align: start;
      }

      /* تبويب الأتمتة والإشعارات وشارات التنبيه وبطاقة الهاتف */
      .as-automation-card {
        border: 1px solid var(--line);
        background: var(--panel);
        border-radius: 8px;
        padding: 9px 11px;
        display: flex;
        flex-direction: column;
        gap: 7px;
        font-size: 12px;
        position: relative;
        transition: border-color 0.14s ease, background-color 0.14s ease;
      }
      .as-automation-card.is-disabled {
        opacity: 0.72;
      }
      .as-auto-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
      }
      .as-auto-name {
        font-weight: 600;
        font-size: 13px;
        color: var(--ink);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .as-auto-desc {
        color: var(--mut);
        font-size: 11.5px;
        line-height: 1.45;
        word-break: break-word;
      }
      .as-auto-meta {
        display: flex;
        flex-direction: column;
        gap: 4px;
        font-size: 11px;
        padding: 6px 8px;
        border-radius: 6px;
        background: var(--side);
        border: 1px solid color-mix(in srgb, var(--line) 60%, transparent);
      }
      .as-auto-meta-row {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 6px;
        flex-wrap: wrap;
      }
      .as-auto-meta-label {
        color: var(--mut);
        font-weight: 500;
      }
      .as-auto-meta-val {
        color: var(--ink);
        font-weight: 500;
      }
      .as-auto-note {
        color: var(--ink);
        font-size: 11px;
        word-break: break-word;
        line-height: 1.4;
      }
      .as-auto-actions {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        gap: 6px;
        margin-top: 2px;
      }
      .as-auto-actions .btn {
        padding: 4px 9px;
        font-size: 11px;
      }
      .as-btn-danger-confirm {
        background: var(--err) !important;
        color: #fff !important;
        border-color: var(--err) !important;
        font-weight: 600 !important;
        animation: as-pulse 1s infinite ease-in-out;
      }

      /* قسم الإشعارات */
      .as-notices-section {
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin-top: 14px;
        padding-top: 12px;
        border-top: 1px dashed var(--line);
      }
      .as-notice-card {
        border: 1px solid var(--line);
        background: var(--panel);
        border-radius: 7px;
        padding: 8px 10px;
        display: flex;
        flex-direction: column;
        gap: 4px;
        font-size: 11.5px;
        position: relative;
        transition: border-color 0.14s ease, background-color 0.14s ease;
      }
      .as-notice-card.is-unread {
        border-color: color-mix(in srgb, var(--acc) 50%, var(--line));
        background: color-mix(in srgb, var(--accp) 35%, var(--panel));
        border-inline-start: 3px solid var(--acc);
      }
      .as-notice-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 6px;
        font-size: 11px;
        color: var(--mut);
      }
      .as-notice-rule {
        font-weight: 600;
        color: var(--ink);
      }
      .as-notice-body {
        color: var(--ink);
        line-height: 1.45;
        word-break: break-word;
      }

      /* الشارات */
      .as-tab-unread-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 16px;
        height: 16px;
        padding: 0 4px;
        border-radius: 8px;
        font-size: 10px;
        font-weight: 700;
        background: var(--err);
        color: #fff;
        line-height: 1;
        margin-inline-start: 2px;
      }
      .as-floating-unread-badge {
        position: absolute;
        top: -3px;
        inset-inline-end: -3px;
        min-width: 18px;
        height: 18px;
        padding: 0 5px;
        border-radius: 9px;
        font-size: 11px;
        font-weight: 700;
        background: var(--err);
        color: #fff;
        border: 2px solid var(--panel);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        line-height: 1;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
      }

      /* بطاقة الهاتف اللاسلكي */
      .as-phone-card {
        border: 1px solid var(--line);
        background: var(--panel);
        border-radius: 8px;
        padding: 10px 11px;
        display: flex;
        flex-direction: column;
        gap: 8px;
        font-size: 12px;
        margin-bottom: 10px;
      }
      .as-phone-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 6px;
      }
      .as-phone-title-row {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-weight: 600;
        font-size: 13px;
        color: var(--ink);
      }
      .as-phone-status-badge {
        font-size: 11px;
        font-weight: 500;
        padding: 2px 7px;
        border-radius: 99px;
        display: inline-flex;
        align-items: center;
        gap: 4px;
      }
      .as-phone-status-badge.is-connected {
        background: color-mix(in srgb, var(--ok) 18%, transparent);
        color: var(--ok);
        border: 1px solid color-mix(in srgb, var(--ok) 35%, transparent);
      }
      .as-phone-status-badge.is-disconnected {
        background: var(--side);
        color: var(--mut);
        border: 1px solid var(--line);
      }
      .as-phone-info-grid {
        display: flex;
        flex-direction: column;
        gap: 4px;
        background: var(--side);
        border: 1px solid color-mix(in srgb, var(--line) 60%, transparent);
        border-radius: 6px;
        padding: 6px 8px;
        font-size: 11px;
      }
      .as-phone-info-row {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 6px;
      }
      .as-phone-info-lbl {
        color: var(--mut);
      }
      .as-phone-info-val {
        color: var(--ink);
        font-weight: 500;
        direction: ltr;
        unicode-bidi: embed;
      }
      .as-phone-pair-box {
        margin-top: 4px;
        padding: 8px;
        border-radius: 6px;
        background: var(--side);
        border: 1px solid var(--line);
        display: flex;
        flex-direction: column;
        gap: 6px;
      }
      .as-phone-guide {
        font-size: 11px;
        color: var(--mut);
        line-height: 1.4;
      }
      .as-phone-inputs-row {
        display: flex;
        gap: 6px;
        align-items: center;
      }
      .as-phone-inp {
        flex: 1;
        padding: 5px 8px;
        font-size: 12px;
        border-radius: 6px;
        border: 1px solid var(--line);
        background: var(--bg);
        color: var(--ink);
        direction: ltr;
        text-align: start;
        outline: none;
      }
      .as-phone-inp:focus {
        border-color: var(--acc);
      }


      /* ===== إعادة تصميم: شريط التبويبات وبطاقة الهاتف ===== */
      .as-side-tabs { padding: 5px 6px 4px; gap: 2px; }
      .as-tab-btn {
        flex-direction: column;
        gap: 3px;
        padding: 7px 1px 6px;
        font-size: 10px;
        line-height: 1.1;
        min-width: 0;
        border-radius: 10px;
        position: relative;
        white-space: nowrap;
      }
      .as-tab-btn.as-active-tab { box-shadow: inset 0 -2px 0 var(--acc); border-radius: 10px 10px 4px 4px; }
      .as-tab-btn .as-tab-unread-badge { position: absolute; top: 1px; inset-inline-end: 8px; margin: 0; }
      .as-phone-card {
        border-radius: 16px;
        padding: 14px;
        gap: 12px;
        background: linear-gradient(180deg, var(--panel), var(--side));
        box-shadow: 0 1px 3px rgba(0,0,0,.06);
      }
      .as-phone-head { gap: 10px; justify-content: flex-start; }
      .as-phone-ico {
        width: 38px; height: 38px; flex-shrink: 0;
        display: grid; place-items: center;
        border-radius: 12px;
        background: var(--accp); color: var(--acc);
      }
      .as-phone-titles { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
      .as-phone-titles .as-phone-title-row { font-size: 14px; }
      .as-phone-sub {
        font-size: 11px; color: var(--mut);
        direction: ltr; text-align: start;
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      }
      .as-phone-status-badge { padding: 4px 10px; font-size: 11px; flex-shrink: 0; gap: 6px; white-space: nowrap; }
      .as-phone-status-badge::before { content: ''; width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
      .as-phone-status-badge.is-connected::before { box-shadow: 0 0 0 3px color-mix(in srgb, var(--ok) 25%, transparent); }
      .as-phone-info-grid { flex-direction: row; gap: 8px; background: none; border: none; padding: 0; }
      .as-phone-info-row {
        flex: 1; min-width: 0;
        flex-direction: column; align-items: flex-start; justify-content: flex-start; gap: 3px;
        background: var(--bg);
        border: 1px solid var(--line);
        border-radius: 11px;
        padding: 8px 10px;
      }
      .as-phone-info-lbl { font-size: 10.5px; }
      .as-phone-info-val { font-size: 12px; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .as-phone-actions { display: grid; grid-template-columns: 1fr; gap: 8px; }
      .as-phone-actions .btn {
        width: 100%; box-sizing: border-box;
        display: inline-flex; align-items: center; justify-content: center; gap: 6px;
        padding: 10px 12px !important; font-size: 12.5px !important;
        border-radius: 11px;
      }
      .as-phone-pair-box { gap: 10px; padding: 12px; border-radius: 12px; background: var(--bg); }
      .as-phone-pair-box[hidden] { display: none; }
      .as-phone-steps { margin: 0; padding: 0; list-style: none; counter-reset: st; display: flex; flex-direction: column; gap: 7px; }
      .as-phone-steps li { counter-increment: st; display: flex; gap: 8px; align-items: flex-start; font-size: 11.5px; line-height: 1.5; color: var(--mut); }
      .as-phone-steps li::before {
        content: counter(st);
        flex-shrink: 0; width: 18px; height: 18px; border-radius: 50%;
        display: grid; place-items: center;
        background: var(--accp); color: var(--acc); font-size: 10.5px; font-weight: 700; margin-top: 1px;
      }
      .as-phone-inputs-row { flex-direction: column; align-items: stretch; gap: 8px; }
      .as-phone-inp { flex: none; width: 100%; box-sizing: border-box; padding: 10px 12px; font-size: 13px; border-radius: 11px; }
      .as-phone-inp.as-phone-code { text-align: center; font-size: 20px; font-weight: 600; letter-spacing: .45em; padding-inline-start: calc(.45em + 12px); }
      .as-phone-submit { width: 100%; box-sizing: border-box; display: inline-flex; align-items: center; justify-content: center; gap: 6px; padding: 10px 12px !important; font-size: 12.5px !important; border-radius: 11px; }
      .as-quick-tools-grid .btn { padding: 8px 6px; border-radius: 11px; }
      .as-refresh-models-btn { padding: 10px 12px; border-radius: 11px; }


      /* ===== نافذة تشغيل السكربت ===== */
      .as-sm-overlay { position: absolute; inset: 0; z-index: 30; background: rgba(0,0,0,.42); backdrop-filter: blur(3px); display: flex; align-items: flex-end; justify-content: center; }
      .as-sm-box { width: 100%; max-height: 94%; overflow: auto; background: var(--bg); border-radius: 18px 18px 0 0; padding: 16px 16px 14px; box-shadow: 0 -8px 30px rgba(0,0,0,.25); display: flex; flex-direction: column; gap: 12px; animation: asSmUp .22s ease; }
      @keyframes asSmUp { from { transform: translateY(24px); opacity: 0; } to { transform: none; opacity: 1; } }
      .as-sm-head { display: flex; align-items: center; gap: 10px; }
      .as-sm-ico { width: 40px; height: 40px; border-radius: 12px; display: grid; place-items: center; background: var(--accp); color: var(--acc); flex-shrink: 0; }
      .as-sm-titles { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
      .as-sm-titles b { font-size: 14.5px; }
      .as-sm-sub { color: var(--mut); font-size: 11px; }
      .as-sm-x { border: none; background: var(--side); color: var(--mut); width: 28px; height: 28px; border-radius: 50%; cursor: pointer; display: grid; place-items: center; }
      .as-sm-desc { font-size: 12px; color: var(--mut); line-height: 1.6; }
      .as-sm-form { display: flex; flex-direction: column; gap: 10px; background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 12px; }
      .as-sm-field { display: flex; flex-direction: column; gap: 5px; }
      .as-sm-lab { font-size: 11.5px; font-weight: 600; color: var(--ink); }
      .as-sm-inp { width: 100%; box-sizing: border-box; padding: 10px 12px; font-size: 13.5px; border-radius: 11px; border: 1px solid var(--line); background: var(--bg); color: var(--ink); outline: none; }
      .as-sm-inp:focus { border-color: var(--acc); box-shadow: 0 0 0 3px var(--accp); }
      .as-sm-inp.ltr { direction: ltr; text-align: start; }
      .as-sm-step { display: flex; align-items: stretch; gap: 6px; }
      .as-sm-step input { text-align: center; flex: 1; }
      .as-sm-step button { width: 40px; border-radius: 11px; border: 1px solid var(--line); background: var(--side); color: var(--ink); font-size: 18px; cursor: pointer; }
      .as-sm-seg { display: flex; gap: 6px; flex-wrap: wrap; }
      .as-sm-seg-btn { border: 1px solid var(--line); background: var(--bg); color: var(--ink); padding: 7px 12px; border-radius: 99px; cursor: pointer; font-size: 12px; }
      .as-sm-seg-btn.on { background: var(--accp); border-color: var(--acc); color: var(--acc); font-weight: 600; }
      .as-sm-err { color: var(--err); font-size: 12px; background: color-mix(in srgb, var(--err) 10%, transparent); padding: 8px 10px; border-radius: 10px; }
      .as-sm-warn { display: flex; align-items: center; gap: 5px; color: #b4561b; background: color-mix(in srgb, #f59e0b 14%, transparent); padding: 8px 10px; border-radius: 10px; font-size: 12px; }
      .as-sm-cmd { direction: ltr; text-align: left; font-family: ui-monospace, Menlo, monospace; font-size: 11.5px; color: var(--mut); background: var(--side); padding: 7px 10px; border-radius: 9px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .as-sm-code summary { cursor: pointer; font-size: 11.5px; color: var(--mut); padding: 4px 0; }
      .as-sm-code pre { max-height: 200px; overflow: auto; direction: ltr; text-align: left; font-size: 11.5px; background: var(--side); padding: 10px; border-radius: 10px; white-space: pre-wrap; margin: 6px 0 0; }
      .as-sm-actions { display: flex; gap: 8px; position: sticky; bottom: 0; }
      .as-sm-go { flex: 1; display: inline-flex; align-items: center; justify-content: center; gap: 6px; padding: 12px !important; font-size: 13.5px !important; border-radius: 12px; }
      .as-sm-cancel { padding: 12px 18px !important; border-radius: 12px; }


      .as-improve-row { padding: 0 10px 4px; display: flex; }
      .as-improve-row[hidden] { display: none; }
      .as-improve-btn { font-size: 12px; padding: 4px 10px; }
      .as-imp-overlay { position: fixed; inset: 0; z-index: 2147483000; background: rgba(0,0,0,.45); display: flex; align-items: center; justify-content: center; padding: 16px; direction: rtl; }
      .as-imp-box { background: var(--bg, #fff); color: var(--fg, #111); border: 1px solid var(--bd, #ccc); border-radius: 12px; width: min(760px, 100%); max-height: 88vh; overflow: auto; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
      .as-imp-head { display: flex; align-items: center; gap: 8px; }
      .as-imp-head b { flex: 1; }
      .as-imp-chip { background: var(--accp, #dbeafe); color: var(--acc, #0a84ff); border-radius: 999px; padding: 2px 10px; font-size: 12px; }
      .as-imp-notes, .as-imp-wait { font-size: 12.5px; color: var(--mut, #666); line-height: 1.6; padding: 6px 2px; }
      .as-imp-sec { border: 1px solid var(--bd, #ccc); border-radius: 10px; overflow: hidden; }
      .as-imp-sec-h { display: flex; align-items: center; justify-content: space-between; padding: 6px 10px; background: rgba(127,127,127,.1); }
      .as-imp-acts { display: inline-flex; gap: 6px; }
      .as-imp-text { padding: 10px; white-space: pre-wrap; font-size: 13px; line-height: 1.7; max-height: 260px; overflow: auto; user-select: text; }
      .as-imp-foot { display: flex; gap: 8px; flex-wrap: wrap; }

      .as-improve-row { align-items: center; gap: 10px; flex-wrap: wrap; }
      .as-clarify-toggle { font-size: 12px; color: var(--mut); display: inline-flex; align-items: center; gap: 4px; cursor: pointer; }
      .as-clarify { margin: 8px 10px; border: 1px solid var(--acc); background: var(--accp); border-radius: 12px; padding: 10px; display: flex; flex-direction: column; gap: 8px; }
      .as-clarify-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
      .as-clarify-q { font-size: 13px; line-height: 1.6; }
      .as-clarify-box { display: flex; flex-direction: column; gap: 6px; }
      .as-clarify-opts { display: flex; gap: 6px; flex-wrap: wrap; }
      .as-clarify-opt.on { background: var(--acc); color: #fff; border-color: var(--acc); }
      .as-min-dash { font-weight: 700; font-size: 15px; line-height: 1; }
      .as-sm-pickrow { display: flex; gap: 6px; align-items: stretch; }
      .as-sm-pickrow .as-sm-inp { flex: 1; min-width: 0; }

      .as-panel.as-floating { transition: none; border: 1px solid var(--line); border-radius: 14px; box-shadow: 0 18px 50px rgba(0,0,0,.28), 0 2px 8px rgba(0,0,0,.12); max-width: none; z-index: 100; }
      .as-panel.as-floating .as-head { cursor: move; user-select: none; }
      .as-panel.as-floating .as-resize-grip { display: none; }
      .as-icon-btn.on { background: var(--accp); color: var(--acc); }
      .as-float-grip { display: none; position: absolute; z-index: 30; }
      .as-panel.as-floating .as-float-grip { display: block; }
      .as-fg-n { top: -3px; left: 14px; right: 14px; height: 8px; cursor: ns-resize; }
      .as-fg-s { bottom: -3px; left: 14px; right: 14px; height: 8px; cursor: ns-resize; }
      .as-fg-e { right: -3px; top: 14px; bottom: 14px; width: 8px; cursor: ew-resize; }
      .as-fg-w { left: -3px; top: 14px; bottom: 14px; width: 8px; cursor: ew-resize; }
      .as-fg-ne { top: -3px; right: -3px; width: 16px; height: 16px; cursor: nesw-resize; }
      .as-fg-nw { top: -3px; left: -3px; width: 16px; height: 16px; cursor: nwse-resize; }
      .as-fg-se { bottom: -3px; right: -3px; width: 16px; height: 16px; cursor: nwse-resize; }
      .as-fg-sw { bottom: -3px; left: -3px; width: 16px; height: 16px; cursor: nesw-resize; }

      /* مربع الإدخال المتجاوب: بطاقة واحدة، النص بعرض كامل وتحته صف الأزرار */
      .as-input-bar { display: block; padding: 8px 10px 10px; }
      .as-composer { container-type: inline-size; display: flex; flex-direction: column; gap: 2px; border: 1px solid var(--line); background: var(--bg); border-radius: 14px; padding: 6px 6px 6px; transition: border-color .14s ease, box-shadow .14s ease; }
      .as-composer:focus-within { border-color: var(--acc); box-shadow: 0 0 0 2px var(--accp); }
      .as-composer .as-input-wrap { display: block; }
      .as-composer .as-input { border: 0; background: transparent; box-shadow: none; border-radius: 8px; padding: 6px 8px; min-height: 44px; max-height: 168px; height: 44px; overflow-y: auto; font-size: 13.5px; line-height: 1.6; }
      .as-composer .as-input:focus { border: 0; box-shadow: none; }
      .as-composer-row { display: flex; align-items: center; gap: 4px; }
      .as-composer-spacer { flex: 1; min-width: 0; }
      .as-composer .as-attach-btn, .as-composer .as-save-prompt-star { position: static; width: 34px; height: 34px; padding: 0; border: 0; border-radius: 10px; background: transparent; display: inline-flex; align-items: center; justify-content: center; flex: none; color: var(--mut); }
      .as-composer .as-attach-btn:hover, .as-composer .as-save-prompt-star:hover { background: var(--accp); color: var(--acc); }
      .as-composer .as-send-btn { height: 34px; padding: 0 16px; border-radius: 10px; font-size: 13px; flex: none; }
      .as-composer .as-stop-btn { height: 34px; padding: 0 12px; border-radius: 10px; font-size: 12px; flex: none; }
      .as-composer .as-stop-btn:disabled { display: none; }
      @container (max-width: 300px) {
        .as-composer .as-btn-label { display: none; }
        .as-composer .as-send-btn, .as-composer .as-stop-btn { padding: 0 11px; }
        .as-composer .as-attach-btn, .as-composer .as-save-prompt-star { width: 32px; }
      }
      @container (min-width: 560px) {
        .as-composer .as-input { min-height: 56px; height: 56px; font-size: 14px; }
        .as-composer .as-send-btn { padding: 0 22px; }
      }
      .as-improve-row { padding: 2px 12px 4px; gap: 6px 12px; justify-content: space-between; }

      /* واجهة المرفقات (المهمة B) */
      .as-attach-btn {
        width: 36px;
        height: 38px;
        padding: 0;
        border-radius: 8px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        color: var(--mut);
        background: var(--bg);
        border: 1px solid var(--line);
        cursor: pointer;
        box-sizing: border-box;
        transition: background-color 0.12s ease, color 0.12s ease, border-color 0.12s ease;
      }
      .as-attach-btn:hover {
        color: var(--acc);
        border-color: var(--acc);
        background: var(--accp);
      }
      .as-drag-overlay {
        position: absolute;
        inset: 0;
        background: rgba(10, 132, 255, 0.14);
        backdrop-filter: blur(4px);
        -webkit-backdrop-filter: blur(4px);
        border: 2px dashed var(--acc);
        border-radius: 12px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 12px;
        z-index: 100;
        pointer-events: none;
        color: var(--ink);
        font-weight: 600;
        font-size: 15px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.18);
        transition: opacity 0.15s ease;
      }
      .as-drag-overlay[hidden] {
        display: none !important;
      }
      .as-drag-overlay-ico {
        width: 48px;
        height: 48px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        color: var(--acc);
      }
      .as-drag-overlay-text {
        padding: 6px 14px;
        background: var(--panel);
        border-radius: 20px;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.12);
      }
      .as-attachments-bar {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        padding: 8px 14px;
        background: var(--panel);
        border-top: 1px solid var(--line);
        max-height: 140px;
        overflow-y: auto;
        scrollbar-width: thin;
      }
      .as-attachments-bar[hidden] {
        display: none !important;
      }
      .as-attach-chip {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 4px 8px;
        background: var(--bg);
        border: 1px solid var(--line);
        border-radius: 8px;
        font-size: 12px;
        max-width: 220px;
        position: relative;
        overflow: hidden;
        user-select: none;
        box-sizing: border-box;
        transition: border-color 0.14s ease, background-color 0.14s ease;
      }
      .as-attach-chip.as-chip-err {
        border-color: var(--err);
        background: rgba(255, 69, 58, 0.08);
      }
      .as-chip-thumb {
        width: 32px;
        height: 32px;
        border-radius: 6px;
        object-fit: cover;
        flex-shrink: 0;
        background: var(--panel);
        display: block;
      }
      .as-chip-kind-ico {
        font-size: 16px;
        line-height: 1;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        border-radius: 6px;
        background: var(--panel);
        flex-shrink: 0;
      }
      .as-chip-info {
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 0;
        flex: 1;
      }
      .as-chip-name {
        font-weight: 500;
        color: var(--ink);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        font-size: 11px;
      }
      .as-chip-size {
        font-size: 10px;
        color: var(--mut);
        direction: rtl;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .as-chip-err-text {
        font-size: 10px;
        color: var(--err);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .as-chip-actions {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        flex-shrink: 0;
      }
      .as-chip-retry-btn, .as-chip-remove-btn {
        border: none;
        background: transparent;
        color: var(--mut);
        cursor: pointer;
        padding: 4px;
        border-radius: 4px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        transition: color 0.12s ease, background 0.12s ease;
      }
      .as-chip-retry-btn:hover {
        color: var(--acc);
        background: var(--accp);
      }
      .as-chip-remove-btn:hover {
        color: var(--err);
        background: rgba(255, 69, 58, 0.15);
      }
      .as-chip-progress-bar {
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: var(--line);
        overflow: hidden;
      }
      .as-chip-progress-fill {
        height: 100%;
        background: var(--acc);
        transition: width 0.18s ease;
      }
      .as-msg-attachments {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 8px;
        padding-top: 6px;
        border-top: 1px solid rgba(255, 255, 255, 0.1);
      }
      .as-msg-attach-img-card {
        position: relative;
        border-radius: 8px;
        overflow: hidden;
        cursor: pointer;
        border: 1px solid rgba(255, 255, 255, 0.18);
        background: rgba(0, 0, 0, 0.2);
        max-width: 140px;
        max-height: 140px;
        transition: transform 0.14s ease, box-shadow 0.14s ease;
      }
      .as-msg-attach-img-card:hover {
        transform: scale(1.02);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
      }
      .as-msg-attach-thumb {
        display: block;
        width: 100%;
        height: 100%;
        max-height: 140px;
        object-fit: cover;
      }
      .as-msg-attach-file-chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 5px 10px;
        border-radius: 6px;
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.14);
        font-size: 12px;
        color: inherit;
        user-select: none;
        text-decoration: none;
        transition: background 0.12s ease;
      }
      .as-msg-attach-file-chip:hover {
        background: rgba(255, 255, 255, 0.16);
      }
      .as-msg-attach-file-ico {
        font-size: 14px;
      }
      .as-msg-attach-file-name {
        max-width: 160px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .as-img-modal {
        position: fixed;
        inset: 0;
        background: rgba(0, 0, 0, 0.82);
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 99999;
        padding: 24px;
        outline: none;
      }
      .as-img-modal-content {
        position: relative;
        max-width: 90vw;
        max-height: 90vh;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 10px;
      }
      .as-img-modal-img {
        max-width: 100%;
        max-height: 82vh;
        object-fit: contain;
        border-radius: 8px;
        box-shadow: 0 12px 36px rgba(0, 0, 0, 0.6);
      }
      .as-img-modal-close {
        position: absolute;
        top: -16px;
        inset-inline-end: -16px;
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: rgba(40, 40, 40, 0.9);
        border: 1px solid rgba(255, 255, 255, 0.2);
        color: #fff;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: background 0.12s ease, transform 0.1s ease;
      }
      .as-img-modal-close:hover {
        background: var(--err);
        transform: scale(1.08);
      }
      .as-img-modal-caption {
        color: #eee;
        font-size: 13px;
        text-align: center;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 80vw;
      }

      /* إمكانية الوصول: تقليل الحركة لمن يفضل ذلك */
      @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
          animation-duration: 0.01ms !important;
          animation-iteration-count: 1 !important;
          transition-duration: 0.01ms !important;
          scroll-behavior: auto !important;
        }
      }
    `;
    document.head.appendChild(styleEl);
  }

  /* ==========================================================================
     3. قواميس الأدوات والترجمات
     ========================================================================== */
  const TOOL_NAMES = {
    places: 'دليل الأماكن',
    status: 'حالة زاجل',
    list_folder: 'عرض المجلد',
    search: 'بحث',
    search_all: 'بحث شامل',
    search_result: 'نتائج البحث',
    folder_size: 'حساب الحجم',
    disk_space: 'المساحة الحرة',
    list_ops: 'العمليات',
    op_details: 'تفاصيل العملية',
    wait_op: 'انتظار العملية',
    list_syncs: 'المزامنات',
    list_migrations: 'قواعد الترحيل',
    favorites: 'المفضلة',
    preview: 'معاينة',
    copy_items: 'نسخ عناصر',
    make_folder: 'مجلد جديد',
    create_sync: 'إنشاء مزامنة',
    run_sync: 'تشغيل مزامنة',
    run_migration: 'تشغيل ترحيل',
    create_migration: 'إنشاء ترحيل',
    pause_op: 'إيقاف مؤقت',
    cancel_op: 'إلغاء عملية',
    move_items: 'نقل عناصر',
    delete_items: 'حذف عناصر',
    rename_items: 'إعادة تسمية',
    update_sync: 'تعديل مزامنة',
    delete_sync: 'حذف مزامنة',
    delete_migration: 'حذف ترحيل',
    uninstall_app: 'حذف تطبيق',
    install_apk: 'تثبيت تطبيق',
    phone_delete: 'حذف نهائي',
    approval_status: 'فحص الموافقة'
  };

  /* ==========================================================================
     4. دوال مساعدة آمنة لإنشاء عناصر DOM وتنسيق النصوص (بدون innerHTML)
     ========================================================================== */
  function el(tag, text, cls, attrs = {}) {
    const element = document.createElement(tag);
    if (text !== undefined && text !== null && text !== '') {
      element.textContent = String(text);
    }
    if (cls) {
      element.className = cls;
    }
    for (const [k, v] of Object.entries(attrs)) {
      if (v !== undefined && v !== null) {
        element.setAttribute(k, String(v));
      }
    }
    return element;
  }

  function btn(text, onClick, cls = 'btn', attrs = {}) {
    const b = el('button', text, cls, attrs);
    b.type = 'button';
    if (typeof onClick === 'function') {
      b.onclick = onClick;
    }
    return b;
  }

  function safeFsize(bytes) {
    if (typeof fsize === 'function') {
      try { return fsize(bytes); } catch (_) {}
    }
    if (bytes == null || isNaN(bytes)) return '—';
    if (bytes >= 1e9) return (bytes / 1e9).toFixed(1) + ' GB';
    if (bytes >= 1e6) return (bytes / 1e6).toFixed(1) + ' MB';
    if (bytes >= 1e3) return Math.round(bytes / 1e3) + ' KB';
    return bytes + ' B';
  }

  function safeNote(msg) {
    if (typeof note === 'function') {
      try { note(msg); return; } catch (_) {}
    }
  }

  function formatRelativeTime(unixSeconds) {
    if (!unixSeconds || unixSeconds <= 0) return 'منذ قليل';
    const now = Math.floor(Date.now() / 1000);
    const diff = Math.max(0, now - unixSeconds);
    if (diff < 60) return 'منذ لحظات';
    const mins = Math.floor(diff / 60);
    if (mins < 60) return 'منذ ' + mins + ' د';
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return 'منذ ' + hrs + ' س';
    const days = Math.floor(hrs / 24);
    return 'منذ ' + days + ' ي';
  }

  /**
   * تحويل النصوص الخفيف الآمن مع دعم **غامق** كعنصر strong حقيقي.
   * خالي تمامًا من innerHTML و eval.
   */
  function renderSafeFormattedText(container, rawText) {
    container.replaceChildren();
    if (!rawText) return;

    // فصل كتل الكود ``` ... ``` عن بقية النص
    const codeBlockRegex = /```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g;
    let lastIndex = 0;
    let match;

    while ((match = codeBlockRegex.exec(rawText)) !== null) {
      if (match.index > lastIndex) {
        renderParagraphsAndLists(container, rawText.substring(lastIndex, match.index));
      }
      const lang = match[1] || '';
      const codeContent = match[2] || '';
      const pre = el('pre', '', 'as-code-block');
      if (lang) pre.setAttribute('data-lang', lang);
      const code = el('code', codeContent.replace(/\n$/, ''));
      pre.appendChild(code);
      container.appendChild(pre);
      lastIndex = codeBlockRegex.lastIndex;
    }

    if (lastIndex < rawText.length) {
      renderParagraphsAndLists(container, rawText.substring(lastIndex));
    }
  }

  function renderParagraphsAndLists(container, text) {
    const lines = text.split('\n');
    let currentUl = null;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const trimmed = line.trim();

      // فحص القائمة النقطية (- أو * أو •)
      const listMatch = trimmed.match(/^([-*•])\s+(.+)$/);
      if (listMatch) {
        if (!currentUl) {
          currentUl = el('ul', '', 'as-bullet-list');
          container.appendChild(currentUl);
        }
        const li = el('li', '');
        renderInlineTokens(li, listMatch[2]);
        currentUl.appendChild(li);
        continue;
      }

      currentUl = null;

      if (!trimmed) {
        continue;
      }

      const p = el('p', '', 'as-para');
      renderInlineTokens(p, line);
      container.appendChild(p);
    }
  }

  function renderInlineTokens(targetEl, text) {
    if (!text) return;
    // دعم: **غامق**، `كود مضمن`، وروابط
    const inlineRegex = /(\*\*([^*]+)\*\*)|(`([^`]+)`)|(https?:\/\/[^\s<]+)/g;
    let lastIdx = 0;
    let m;

    while ((m = inlineRegex.exec(text)) !== null) {
      if (m.index > lastIdx) {
        targetEl.appendChild(document.createTextNode(text.substring(lastIdx, m.index)));
      }

      if (m[1]) {
        // نص غامق **...**
        const strongEl = el('strong', m[2]);
        targetEl.appendChild(strongEl);
      } else if (m[3]) {
        // كود مضمن `...`
        const codeEl = el('code', m[4], 'as-inline-code');
        targetEl.appendChild(codeEl);
      } else if (m[5] || (m[0] && m[0].startsWith('http'))) {
        // رابط
        const linkEl = el('span', m[0], 'as-link-text', {
          title: 'رابط مرجعي غير قابل للنقر'
        });
        targetEl.appendChild(linkEl);
      }

      lastIdx = inlineRegex.lastIndex;
    }

    if (lastIdx < text.length) {
      targetEl.appendChild(document.createTextNode(text.substring(lastIdx)));
    }
  }

  /* ==========================================================================
     5. الحالة العامة والبيانات
     ========================================================================== */
  let isOpen = false;
  let isExpanded = false;
  let isFloating = false;
  let floatGeom = { x: 24, y: 70, w: 460, h: 600 };
  const FLOAT_MIN_W = 300;
  const FLOAT_MIN_H = 260;
  let isSidebarOpen = false;
  let activeTab = 'chats'; // chats | memory | prompts | automations | settings
  let activeWindow = 'assistant';
  let controlActiveTab = 'settings';

  let agentsList = [];
  let currentSettings = { default_agent: 'agy', models: {}, efforts: {} };
  let activeAgentId = '';   // يُحسم من الإعدادات (المصدر الأساسي) عند أول تحميل
  let activeModel = '';

  let currentConversation = '';
  let restoredLast = false;
  let currentJobId = '';
  let activeBotCard = null; // مرجع فقاعة الوكيل الجارية لدعم التعقيب والقطع
  let jobPollTimer = null;
  let pendingPollTimer = null;
  let lastKnownPendingIds = new Set();
  const trackedOps = new Set();
  const inspectedEvents = new Set();
  let messages = []; // حد أقصى 200 رسالة
  const renderedPendingCards = new Map();

  // بيانات التبويبات للتحميل الكسول
  let chatsData = [];
  let chatsLoaded = false;
  let chatSearchQuery = '';

  let memoryList = [];
  let memoryLoaded = false;
  let memoryStatus = { running: false, last: 0, note: '', auto: true };
  let memoryOrganizeTimer = null;
  const memoryCollapsedKinds = new Set();

  let promptsList = [];
  let promptsLoaded = false;

  let automationsRules = [];
  let automationsNotices = [];
  let automationsLoaded = false;
  let automationsPollTimer = null;
  let unreadNoticesCount = 0;
  let automationsTabBadge = null;
  let agentsStats = null;
  let agentsRange = 24;
  let agentsPollTimer = null;
  let agentsLoading = false;

  let sendContextEnabled = true;

  // نطاق البحث في الأماكن المتصلة
  let searchPlacesSelection = []; // مصفوفة معرّفات الأماكن، فارغة = الكل
  let cachedPlacesData = null;
  let isFetchingPlaces = false;
  let isSearchScopeOpen = false;

  // أبعاد النافذة وسحب تغيير الحجم
  let panelWidth = 760;
  const DEFAULT_PANEL_WIDTH = 760;
  const MIN_PANEL_WIDTH = 240;
  const MIN_SIDEBAR_WIDTH = 150;
  const MAX_SIDEBAR_WIDTH = 520;
  let sidebarWidth = 300;

  // استرجاع تفضيلات المستخدم من localStorage بأمان
  try {
    isExpanded = localStorage.getItem('zajel_as_expanded') === 'true';
    isSidebarOpen = localStorage.getItem('zajel_as_sidebar_open') === 'true';
    const savedTab = localStorage.getItem('zajel_as_active_tab');
    if (savedTab && ['chats', 'memory', 'prompts', 'scripts', 'automations', 'agents', 'settings'].includes(savedTab)) {
      if (['chats', 'memory', 'prompts'].includes(savedTab)) activeTab = savedTab;
      else controlActiveTab = savedTab;
    }
    const savedControlTab = localStorage.getItem('zajel_control_active_tab');
    if (savedControlTab && ['settings', 'agents', 'automations', 'scripts', 'terminal'].includes(savedControlTab)) controlActiveTab = savedControlTab;
    const savedPlaces = localStorage.getItem('zajel_as_search_places');
    if (savedPlaces) {
      const parsed = JSON.parse(savedPlaces);
      if (Array.isArray(parsed)) {
        searchPlacesSelection = parsed.filter(x => typeof x === 'string' && x);
      }
    }
    isFloating = localStorage.getItem('zajel_as_float') === 'on';
    try {
      const g = JSON.parse(localStorage.getItem('zajel_as_float_geom') || 'null');
      if (g && [g.x, g.y, g.w, g.h].every(Number.isFinite)) floatGeom = g;
    } catch (_) {}
    const savedSide = parseInt(localStorage.getItem('zajel_as_sidebar_w'), 10);
    if (!isNaN(savedSide) && savedSide >= MIN_SIDEBAR_WIDTH && savedSide <= MAX_SIDEBAR_WIDTH) sidebarWidth = savedSide;
    const savedWidth = parseInt(localStorage.getItem('zajel_as_width'), 10);
    if (!isNaN(savedWidth) && savedWidth >= MIN_PANEL_WIDTH && savedWidth <= 1600) {
      panelWidth = savedWidth;
    }
  } catch (_) {}

  // مراجع عناصر الواجهة
  let chipEl = null;
  let floatingBtn = null;
  let panelEl = null;
  let gripEl = null;
  let minimizeBtn = null;
  let expandBtn = null;
  let floatBtn = null;
  let sidebarEl = null;
  let sideTabsNav = null;
  let sideContentEl = null;
  let assistantContentEl = null;
  let controlContentEl = null;
  let controlTabsNav = null;
  let controlPanelEl = null;
  let controlChipEl = null;
  let controlAutomationBadge = null;
  let sourceBadgeText = null;
  let chatContainer = null;
  let scrollBottomBtn = null;
  let emptyStateEl = null;
  let pendingArea = null;
  let pendingListWrap = null;
  let pendingToggleRow = null;
  let ctxPillBar = null;
  let ctxFolderContainer = null;
  let searchScopeWrap = null;
  let queuedBarEl = null;
  let searchScopeBtn = null;
  let searchScopeTextSpan = null;
  let searchScopePopup = null;
  let inputEl = null;
  let sendBtn = null;
  let stopBtn = null;

  // عناصر وحالة المرفقات (المهمة B)
  let attachBtn = null;
  let fileInputEl = null;
  let attachmentsBarEl = null;
  let dragOverlayEl = null;
  let activeImageModalEl = null;
  let pendingAttachments = [];
  let activeUploadsCount = 0;
  const MAX_CONCURRENT_UPLOADS = 3;
  const MAX_ATTACHMENT_SIZE = 500 * 1024 * 1024; // 500MB
  const MAX_BATCH_FILES = 5;
  const MAX_TOTAL_ATTACHMENTS = 10;

  /* ==========================================================================
     6. فتح وإغلاق النافذة وتغيير الحجم والتصغير والتوسيع
     ========================================================================== */
  function setPanelWidth(width, save = true) {
    const maxW = Math.min(1200, Math.floor(window.innerWidth * 0.96));
    const w = Math.max(MIN_PANEL_WIDTH, Math.min(maxW, Math.round(width)));
    panelWidth = w;
    if (panelEl && !isFloating) {
      panelEl.style.width = w + 'px';
      panelEl.classList.remove('as-expanded');
    }
    if (save) {
      try { localStorage.setItem('zajel_as_width', String(w)); } catch (_) {}
    }
  }

  function minimizeToFloatingBadge() {
    isOpen = false;
    if (panelEl) { panelEl.hidden = true; if (panelEl.__markNarrow) panelEl.__markNarrow(); }
    if (chipEl) chipEl.classList.remove('active');
    if (floatingBtn) {
      floatingBtn.hidden = false;
      updateFloatingBadgeState();
    }
  }

  function updateFloatingBadgeState() {
    if (!floatingBtn) return;
    floatingBtn.replaceChildren(createSvg('bot', 20));

    const hasPending = lastKnownPendingIds && lastKnownPendingIds.size > 0;
    const isWorking = Boolean(currentJobId);

    if (hasPending) {
      const alertDot = el('span', '', 'as-floating-alert-badge', {
        title: 'طلبات موافقة معلقة'
      });
      floatingBtn.appendChild(alertDot);
    } else if (unreadNoticesCount > 0) {
      const countText = unreadNoticesCount > 99 ? '99+' : String(unreadNoticesCount);
      const noticeBadge = el('span', countText, 'as-floating-unread-badge', {
        title: unreadNoticesCount + ' إشعارات غير مقروءة'
      });
      floatingBtn.appendChild(noticeBadge);
    } else if (isWorking) {
      const busyDot = el('span', '', 'as-floating-busy-badge', {
        title: 'المساعد يعمل حالياً'
      });
      floatingBtn.appendChild(busyDot);
    }
  }

  function togglePanel(open) {
    isOpen = typeof open === 'boolean' ? open : !isOpen;
    if (panelEl) {
      panelEl.hidden = !isOpen;
      if (isOpen) {
        if (floatingBtn) floatingBtn.hidden = true;
        if (isSidebarOpen) fitPanelForSidebar();
        if (isFloating) {
          applyPanelMode();
        } else if (isExpanded) {
          panelEl.classList.add('as-expanded');
          panelEl.style.width = '';
        } else {
          panelEl.classList.remove('as-expanded');
          panelEl.style.width = panelWidth + 'px';
        }
      }
    }
    if (typeof panelEl?.__markNarrow === 'function') setTimeout(panelEl.__markNarrow, 0);
    if (chipEl) {
      chipEl.classList.toggle('active', isOpen);
      if (isOpen) {
        chipEl.classList.remove('as-alert');
      }
    }
    if (isOpen) {
      updateContextPill();
      schedulePendingPoll();
      if (inputEl) {
        setTimeout(() => inputEl.focus(), 60);
      }
      if (isSidebarOpen) {
        loadActiveTabData();
      }
      // عند أول فتح بعد تشغيل البرنامج: استأنف آخر محادثة بدل الشاشة الفارغة
      if (!restoredLast) {
        restoredLast = true;
        let last = '';
        try { last = localStorage.getItem('zajel_as_last_chat') || ''; } catch (_) {}
        if (last && !currentConversation && !messages.length) loadChatHistory(last);
      }
    } else {
      schedulePendingPoll();
      stopAutomationsPolling();
      stopAgentsPolling();
    }
  }

  /* النافذة العائمة: تُسحب من الترويسة وتُكبَّر وتُصغَّر من حوافها وزواياها، ولا تزاحم محتوى البرنامج */
  function clampFloat() {
    const vw = window.innerWidth, vh = window.innerHeight;
    floatGeom.w = Math.max(FLOAT_MIN_W, Math.min(vw - 8, Math.round(floatGeom.w)));
    floatGeom.h = Math.max(FLOAT_MIN_H, Math.min(vh - 8, Math.round(floatGeom.h)));
    floatGeom.x = Math.max(0, Math.min(vw - 80, Math.round(floatGeom.x)));
    floatGeom.y = Math.max(0, Math.min(vh - 60, Math.round(floatGeom.y)));
  }

  function applyPanelMode() {
    if (!panelEl) return;
    panelEl.classList.toggle('as-floating', isFloating);
    if (isFloating) {
      panelEl.classList.remove('as-expanded');
      clampFloat();
      Object.assign(panelEl.style, {
        left: floatGeom.x + 'px', top: floatGeom.y + 'px', width: floatGeom.w + 'px', height: floatGeom.h + 'px',
        right: 'auto', bottom: 'auto'
      });
    } else {
      ['left', 'top', 'height', 'right', 'bottom'].forEach(k => { panelEl.style[k] = ''; });
      panelEl.classList.toggle('as-expanded', isExpanded);
      panelEl.style.width = isExpanded ? '' : panelWidth + 'px';
    }
    if (expandBtn) expandBtn.hidden = isFloating;
    if (floatBtn) {
      floatBtn.classList.toggle('on', isFloating);
      floatBtn.title = isFloating ? 'إعادة المساعد إلى اللوحة الجانبية' : 'تحويل المساعد إلى نافذة عائمة';
    }
    if (typeof panelEl.__markNarrow === 'function') panelEl.__markNarrow();
  }

  function setFloating(on) {
    isFloating = on;
    try { localStorage.setItem('zajel_as_float', on ? 'on' : 'off'); } catch (_) {}
    if (on) {
      if (!localStorage.getItem('zajel_as_float_geom')) {
        floatGeom = { x: 24, y: 70, w: 460, h: Math.min(620, window.innerHeight - 100) };
      }
    }
    applyPanelMode();
  }

  function saveFloat() {
    try { localStorage.setItem('zajel_as_float_geom', JSON.stringify(floatGeom)); } catch (_) {}
  }

  function wireFloatInteractions(head) {
    const startDrag = (ev, mode) => {
      if (!isFloating) return;
      ev.preventDefault();
      const start = { px: ev.clientX, py: ev.clientY, g: { ...floatGeom } };
      const target = ev.currentTarget;
      try { target.setPointerCapture(ev.pointerId); } catch (_) {}
      panelEl.classList.add('as-resizing');
      document.body.classList.add('as-resizing-active');
      const move = e => {
        const dx = e.clientX - start.px, dy = e.clientY - start.py;
        const g = { ...start.g };
        if (mode === 'move') { g.x += dx; g.y += dy; }
        else {
          if (mode.includes('e')) g.w = start.g.w + dx;
          if (mode.includes('s')) g.h = start.g.h + dy;
          if (mode.includes('w')) { g.w = start.g.w - dx; g.x = start.g.x + dx; }
          if (mode.includes('n')) { g.h = start.g.h - dy; g.y = start.g.y + dy; }
          if (g.w < FLOAT_MIN_W) { if (mode.includes('w')) g.x -= FLOAT_MIN_W - g.w; g.w = FLOAT_MIN_W; }
          if (g.h < FLOAT_MIN_H) { if (mode.includes('n')) g.y -= FLOAT_MIN_H - g.h; g.h = FLOAT_MIN_H; }
        }
        floatGeom = g;
        applyPanelMode();
      };
      const up = e => {
        try { target.releasePointerCapture(e.pointerId); } catch (_) {}
        target.removeEventListener('pointermove', move);
        target.removeEventListener('pointerup', up);
        target.removeEventListener('pointercancel', up);
        panelEl.classList.remove('as-resizing');
        document.body.classList.remove('as-resizing-active');
        saveFloat();
      };
      target.addEventListener('pointermove', move);
      target.addEventListener('pointerup', up);
      target.addEventListener('pointercancel', up);
    };
    head.addEventListener('pointerdown', ev => {
      if (!isFloating || ev.target.closest('button, input, select, a')) return;
      startDrag(ev, 'move');
    });
    head.addEventListener('dblclick', ev => { if (isFloating && !ev.target.closest('button, input, select, a')) setFloating(false); });
    ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw'].forEach(m => {
      const g = el('div', '', 'as-float-grip as-fg-' + m, { 'aria-hidden': 'true' });
      g.addEventListener('pointerdown', ev => { ev.stopPropagation(); startDrag(ev, m); });
      panelEl.appendChild(g);
    });
  }

  function toggleExpand(expanded) {
    if (isFloating) return;
    isExpanded = typeof expanded === 'boolean' ? expanded : !isExpanded;
    try {
      localStorage.setItem('zajel_as_expanded', isExpanded ? 'true' : 'false');
    } catch (_) {}
    if (panelEl) {
      panelEl.classList.toggle('as-expanded', isExpanded);
      if (!isExpanded) {
        panelEl.style.width = panelWidth + 'px';
      } else {
        panelEl.style.width = '';
      }
    }
    if (expandBtn) {
      expandBtn.replaceChildren(createSvg(isExpanded ? 'minimize' : 'maximize', 15));
      expandBtn.title = isExpanded ? 'استعادة العرض الافتراضي' : 'توسيع العرض';
    }
  }

  function toggleSidebar(open) {
    isSidebarOpen = typeof open === 'boolean' ? open : !isSidebarOpen;
    try {
      localStorage.setItem('zajel_as_sidebar_open', isSidebarOpen ? 'true' : 'false');
    } catch (_) {}
    if (sidebarEl) {
      sidebarEl.classList.toggle('as-sidebar-closed', !isSidebarOpen);
    }
    fitPanelForSidebar();
    if (isSidebarOpen) {
      loadActiveTabData();
    } else {
      stopAutomationsPolling();
      stopAgentsPolling();
    }
  }

  // الشريط الجانبي (٣٠٠) والمحادثة معًا يحتاجان عرضًا كافيًا: نوسّع النافذة مؤقتًا ثم نعيد عرضها عند إغلاقه
  let widthBeforeSidebar = 0;
  function fitPanelForSidebar() {
    if (!panelEl || isExpanded || isFloating || window.innerWidth < 760) return;
    if (isSidebarOpen) {
      // عند فتح الشريط: المجموع ٤٠٪ من الشاشة، منها ٢٠٪ للمحادثة و٢٠٪ للشريط (التصميم الحالي كما هو)
      const share = Math.round(window.innerWidth * 0.20);
      sidebarWidth = Math.max(MIN_SIDEBAR_WIDTH, Math.min(MAX_SIDEBAR_WIDTH, share));
      if (sidebarEl) sidebarEl.style.width = sidebarWidth + 'px';
      if (!widthBeforeSidebar) widthBeforeSidebar = panelWidth;
      setPanelWidth(Math.round(window.innerWidth * 0.40), false);
    } else if (widthBeforeSidebar) {
      setPanelWidth(widthBeforeSidebar, false);
      widthBeforeSidebar = 0;
    }
  }

  function switchTab(tabKey) {
    if (['scripts', 'automations', 'agents', 'settings', 'terminal'].includes(tabKey)) { switchControlTab(tabKey); return; }
    activeWindow = 'assistant';
    sideContentEl = assistantContentEl;
    if (controlPanelEl) { controlPanelEl.hidden = true; controlPanelEl.style.display = 'none'; }
    if (activeWindow === 'control') { stopAutomationsPolling(); stopAgentsPolling(); }
    window.ZajelTerminalUI?.deactivate?.();
    if (activeTab === 'automations' && tabKey !== 'automations') {
      stopAutomationsPolling();
    }
    if (activeTab === 'agents' && tabKey !== 'agents') stopAgentsPolling();
    activeTab = tabKey;
    try {
      localStorage.setItem('zajel_as_active_tab', tabKey);
    } catch (_) {}
    if (!isSidebarOpen) {
      toggleSidebar(true);
    }
    renderActiveTab();
    loadActiveTabData();
  }

  function switchControlTab(tabKey) {
    activeWindow = 'control';
    if (activeTab === 'automations' && tabKey !== 'automations') stopAutomationsPolling();
    if (activeTab === 'agents' && tabKey !== 'agents') stopAgentsPolling();
    activeTab = tabKey;
    controlActiveTab = tabKey;
    sideContentEl = controlContentEl;
    try { localStorage.setItem('zajel_control_active_tab', tabKey); localStorage.setItem('zajel_as_active_tab', tabKey); } catch (_) {}
    if (controlPanelEl) { controlPanelEl.hidden = false; controlPanelEl.style.display = 'flex'; }
    if (assistantContentEl) assistantContentEl.replaceChildren();
    if (controlTabsNav) Array.from(controlTabsNav.children).forEach(b => b.classList.toggle('as-active-tab', b.dataset.tab === tabKey));
    renderActiveTab();
    loadActiveTabData();
  }

  function loadActiveTabData() {
    if (activeWindow === 'control' && activeTab === 'terminal') { window.ZajelTerminalUI?.activate?.(controlContentEl); return; }
    window.ZajelTerminalUI?.deactivate?.();
    if (activeTab === 'chats') {
      loadChats();
    } else if (activeTab === 'memory') {
      loadMemory(true);
    } else if (activeTab === 'scripts') {
      loadScripts();
    } else if (activeTab === 'prompts' && !promptsLoaded) {
      loadPrompts();
    } else if (activeTab === 'automations') {
      loadAutomations();
    } else if (activeTab === 'agents') {
      loadAgentsStats();
    } else if (activeTab === 'settings') {
      renderSettingsTab();
    }
  }

  /* ==========================================================================
     7. شريط سياق المجلد النشط الصغير فوق المدخل «📁 المجلد الحالي ✕»
     ========================================================================== */
  function getActiveContextText() {
    if (typeof P !== 'undefined' && P) {
      const srcName = P.src ? (P.src.label || P.src.id || 'المصدر') : 'المصدر';
      const curPath = P.cur || '/';
      let selCount = 0;
      if (typeof P.S === 'function') {
        try {
          const s = P.S();
          if (s && s.size) selCount = s.size;
        } catch (_) {}
      }
      const selStr = selCount > 0 ? (selCount + ' محدد') : '';
      return srcName + ' : ' + curPath + (selStr ? ' (' + selStr + ')' : '');
    }
    return '';
  }

  function updateContextPill() {
    const targetParent = ctxFolderContainer || ctxPillBar;
    if (!targetParent) return;
    targetParent.replaceChildren();

    const ctxText = getActiveContextText();
    if (!ctxText) return;

    if (sendContextEnabled) {
      const pill = el('div', '', 'as-ctx-pill');
      pill.appendChild(createSvg('folder', 12));
      const span = el('span', ctxText, 'as-ctx-pill-text');
      span.title = 'السياق المرفق مع الطلب: ' + ctxText;
      const closeBtn = el('button', '', 'as-ctx-pill-close', {
        title: 'إلغاء إرسال السياق مع الرسالة',
        type: 'button',
        'aria-label': 'إلغاء إرسال سياق المجلد النشط'
      });
      closeBtn.appendChild(createSvg('close', 11));
      closeBtn.onclick = () => {
        sendContextEnabled = false;
        updateContextPill();
      };
      pill.append(span, closeBtn);
      targetParent.appendChild(pill);
    } else {
      const reEnableBtn = el('button', '', 'as-ctx-pill-enable', {
        type: 'button',
        title: 'إعادة تفعيل إرسال سياق المجلد النشط',
        'aria-label': 'إعادة تفعيل إرسال سياق المجلد النشط'
      });
      reEnableBtn.append(createSvg('folder', 11), document.createTextNode('إرسال السياق معطل (+ تفعيل)'));
      reEnableBtn.onclick = () => {
        sendContextEnabled = true;
        updateContextPill();
      };
      targetParent.appendChild(reEnableBtn);
    }
  }

  /* ==========================================================================
     7ب. نطاق البحث (الأماكن المتصلة، القائمة المنبثقة، والحفظ)
     ========================================================================== */
  function toArabicDigits(num) {
    const digits = ['٠', '١', '٢', '٣', '٤', '٥', '٦', '٧', '٨', '٩'];
    return String(num).replace(/[0-9]/g, d => digits[d]);
  }

  function saveSearchPlacesSelection() {
    try {
      localStorage.setItem('zajel_as_search_places', JSON.stringify(searchPlacesSelection));
    } catch (_) {}
  }

  async function fetchSearchPlaces() {
    if (isFetchingPlaces) return cachedPlacesData;
    isFetchingPlaces = true;
    try {
      const res = await api('/api/assistant/places');
      if (res && typeof res === 'object') {
        cachedPlacesData = res;
      }
    } catch (_) {
      // تجاهل أخطاء الشبكة والاحتفاظ بالبيانات السابقة إن وجدت
    } finally {
      isFetchingPlaces = false;
    }
    return cachedPlacesData;
  }

  function getNormalizedPlacesList(data) {
    const list = [];
    const seen = new Set();

    // الكمبيوتر معرّفه home
    const comp = data?.computer || { id: 'home', name: 'هذا الكمبيوتر' };
    const compId = comp.id || 'home';
    const compName = comp.name || 'هذا الكمبيوتر';
    list.push({ id: compId, name: compName, category: 'computer', labelTag: 'حاسوب' });
    seen.add(compId);

    // الأقراص
    if (Array.isArray(data?.disks)) {
      for (const d of data.disks) {
        if (d && d.place && !seen.has(d.place)) {
          seen.add(d.place);
          list.push({ id: d.place, name: d.name || d.place, category: 'disk', labelTag: 'قرص' });
        }
      }
    }

    // السحابية
    if (Array.isArray(data?.clouds)) {
      for (const c of data.clouds) {
        if (c && c.place && !seen.has(c.place)) {
          seen.add(c.place);
          list.push({ id: c.place, name: c.name || c.place, category: 'cloud', labelTag: 'سحابة' });
        }
      }
    }

    // الأجهزة المتصلة فقط
    if (Array.isArray(data?.devices)) {
      for (const dev of data.devices) {
        if (dev && dev.connected && dev.place && !seen.has(dev.place)) {
          seen.add(dev.place);
          list.push({ id: dev.place, name: dev.name || dev.place, category: 'device', labelTag: 'متصل' });
        }
      }
    }

    return list;
  }

  function getSearchScopeBadgeLabel() {
    if (!searchPlacesSelection || searchPlacesSelection.length === 0) {
      return 'الكل';
    }
    if (searchPlacesSelection.length === 1) {
      const singleId = searchPlacesSelection[0];
      const places = getNormalizedPlacesList(cachedPlacesData);
      const found = places.find(p => p.id === singleId);
      if (found && found.name) return found.name;
      if (singleId === 'home') return 'هذا الكمبيوتر';
      return singleId;
    }
    const count = searchPlacesSelection.length;
    return toArabicDigits(count) + ' أماكن';
  }

  function updateSearchScopeBadge() {
    if (!searchScopeTextSpan) return;
    const label = getSearchScopeBadgeLabel();
    searchScopeTextSpan.textContent = 'البحث: ' + label;
    if (searchScopeBtn) {
      const tooltip = 'نطاق البحث: ' + (searchPlacesSelection.length === 0 ? 'الكل (الأصل)' : label);
      searchScopeBtn.title = tooltip;
      searchScopeBtn.setAttribute('aria-label', tooltip);
    }
  }

  function updatePopupCheckboxes() {
    if (!searchScopePopup) return;
    const isAll = searchPlacesSelection.length === 0;
    const allCb = searchScopePopup.querySelector('.as-scope-all-cb');
    if (allCb) allCb.checked = isAll;

    const placeCbs = searchScopePopup.querySelectorAll('.as-scope-place-cb');
    for (let i = 0; i < placeCbs.length; i++) {
      const cb = placeCbs[i];
      const pid = cb.getAttribute('data-place-id');
      cb.checked = !isAll && searchPlacesSelection.includes(pid);
    }
  }

  function renderSearchScopePopup() {
    if (!searchScopePopup) return;
    searchScopePopup.replaceChildren();

    const places = getNormalizedPlacesList(cachedPlacesData);
    const isAllSelected = searchPlacesSelection.length === 0;

    // خيار «الكل (الأصل)» أعلى القائمة
    const allItem = el('label', '', 'as-scope-item');
    const allCheckbox = el('input', '', 'as-scope-checkbox as-scope-all-cb', {
      type: 'checkbox',
      'aria-label': 'الكل (الأصل)'
    });
    allCheckbox.checked = isAllSelected;

    allCheckbox.onchange = () => {
      searchPlacesSelection = [];
      saveSearchPlacesSelection();
      updateSearchScopeBadge();
      updatePopupCheckboxes();
    };

    const allName = el('span', 'الكل (الأصل)', 'as-scope-item-name');
    allItem.append(allCheckbox, allName);
    searchScopePopup.appendChild(allItem);

    // خط فاصل
    const divider = el('div', '', 'as-scope-divider');
    searchScopePopup.appendChild(divider);

    if (places.length === 0 && isFetchingPlaces) {
      const loading = el('div', 'جاري جلب الأماكن…', 'as-scope-loading');
      searchScopePopup.appendChild(loading);
      return;
    }

    // خيارات الأماكن المتصلة
    for (const place of places) {
      const item = el('label', '', 'as-scope-item');
      const cb = el('input', '', 'as-scope-checkbox as-scope-place-cb', {
        type: 'checkbox',
        'data-place-id': place.id,
        'aria-label': place.name
      });
      cb.checked = !isAllSelected && searchPlacesSelection.includes(place.id);

      cb.onchange = () => {
        if (cb.checked) {
          // اختيار مكان أو أكثر يلغي «الكل»
          if (!searchPlacesSelection.includes(place.id)) {
            searchPlacesSelection.push(place.id);
          }
        } else {
          // إلغاء تحديد المكان
          searchPlacesSelection = searchPlacesSelection.filter(id => id !== place.id);
        }

        // إلغاء كل الخانات يعيد «الكل» تلقائيًا
        saveSearchPlacesSelection();
        updateSearchScopeBadge();
        updatePopupCheckboxes();
      };

      const nameSpan = el('span', place.name, 'as-scope-item-name');
      item.append(cb, nameSpan);

      if (place.labelTag) {
        const tag = el('span', place.labelTag, 'as-scope-item-tag');
        item.appendChild(tag);
      }

      searchScopePopup.appendChild(item);
    }
  }

  function toggleSearchScopePopup(force) {
    const nextState = typeof force === 'boolean' ? force : !isSearchScopeOpen;
    if (nextState === isSearchScopeOpen) return;
    isSearchScopeOpen = nextState;

    if (searchScopePopup) {
      searchScopePopup.hidden = !isSearchScopeOpen;
    }
    if (searchScopeBtn) {
      searchScopeBtn.classList.toggle('as-active', isSearchScopeOpen);
      searchScopeBtn.setAttribute('aria-expanded', String(isSearchScopeOpen));
    }

    if (isSearchScopeOpen) {
      renderSearchScopePopup();
      fetchSearchPlaces().then(() => {
        if (isSearchScopeOpen) {
          renderSearchScopePopup();
          updateSearchScopeBadge();
        }
      });
    }
  }

  function closeSearchScopePopup() {
    toggleSearchScopePopup(false);
  }

  function buildSearchScopeUI() {
    const wrap = el('div', '', 'as-search-scope-wrap');

    searchScopeBtn = el('button', '', 'as-ctx-pill as-search-scope-pill', {
      type: 'button',
      'aria-haspopup': 'dialog',
      'aria-expanded': 'false',
      'aria-label': 'تحديد نطاق البحث'
    });

    const searchIcon = createSvg('search', 12);
    searchScopeTextSpan = el('span', 'البحث: ' + getSearchScopeBadgeLabel(), 'as-search-scope-text');

    searchScopeBtn.append(searchIcon, searchScopeTextSpan);
    searchScopeBtn.title = 'تحديد نطاق الأماكن المتصلة للبحث';

    searchScopeBtn.onclick = (e) => {
      e.stopPropagation();
      toggleSearchScopePopup();
    };

    searchScopePopup = el('div', '', 'as-search-scope-popup', {
      role: 'dialog',
      'aria-label': 'تحديد نطاق البحث'
    });
    searchScopePopup.hidden = true;

    searchScopePopup.onclick = (e) => {
      e.stopPropagation();
    };

    wrap.append(searchScopeBtn, searchScopePopup);
    return wrap;
  }

  /* ==========================================================================
     8. إدارة الرسائل والواجهة الفارغة وزر التمرير إلى الأسفل
     ========================================================================== */
  function updateEmptyStateVisibility() {
    if (!emptyStateEl) return;
    const hasVisibleMessages = messages.length > 0;
    emptyStateEl.hidden = hasVisibleMessages;
  }

  function checkScrollPosition() {
    if (!chatContainer || !scrollBottomBtn) return;
    const distanceToBottom = chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight;
    scrollBottomBtn.hidden = distanceToBottom <= 120;
  }

  function scrollToChatBottom(smooth = true) {
    if (!chatContainer) return;
    chatContainer.scrollTo({
      top: chatContainer.scrollHeight,
      behavior: smooth ? 'smooth' : 'auto'
    });
  }

  const CHOICES_RE = /\[\[\s*(?:خيارات|options)\s*:\s*([^\]]+?)\s*\]\]/i;
  // الأسئلة ذات الخيارات: يكتب الوكيل [[خيارات: أ | ب | ج]] في آخر ردّه فتظهر أزرارًا؛ الضغط يرسل النص المختار
  function renderWithChoices(container, raw, final) {
    let text = String(raw || '');
    const m = text.match(CHOICES_RE);
    text = text.replace(CHOICES_RE, '').replace(/\[\[\s*(?:خيارات|options)[^\]]*$/i, '').trimEnd();
    renderSafeFormattedText(container, text);
    if (!m || !final) return;
    const opts = m[1].split('|').map(x => x.trim()).filter(Boolean).slice(0, 6).map(x => x.slice(0, 60));
    if (!opts.length) return;
    const row = el('div', '', 'as-choices');
    row.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px;margin-top:10px';
    opts.forEach((label, i) => {
      const b = btn(label, () => {
        row.querySelectorAll('button').forEach(x => { x.disabled = true; });
        b.classList.add('pri');
        if (inputEl) { inputEl.value = label; sendMsg(); }
      }, 'btn' + (i === 0 ? ' pri' : ''));
      row.appendChild(b);
    });
    container.appendChild(row);
  }

  function addMessage(type, contentText, attachmentsList = null) {
    if (!chatContainer) return null;
    const msgEl = el('div', '', 'as-msg as-msg-' + type);

    if (type === 'bot' || type === 'user') {
      const body = el('div', '', 'as-msg-body');
      renderSafeFormattedText(body, contentText);
      msgEl.appendChild(body);

      if (type === 'user' && Array.isArray(attachmentsList) && attachmentsList.length > 0) {
        const attsWrap = renderMessageAttachments(attachmentsList);
        if (attsWrap) msgEl.appendChild(attsWrap);
      }
    } else {
      msgEl.textContent = contentText || '';
    }

    chatContainer.appendChild(msgEl);
    scrollToChatBottom(true);

    messages.push({ type, element: msgEl });
    trimMessages();
    updateEmptyStateVisibility();
    return msgEl;
  }

  function trimMessages() {
    while (messages.length > 200) {
      const old = messages.shift();
      if (old && old.element && old.element.parentNode) {
        old.element.remove();
      }
    }
    updateEmptyStateVisibility();
  }

  function newChat() {
    try { localStorage.setItem('zajel_as_last_chat', ''); } catch (_) {}
    currentConversation = '';
    if (currentJobId) {
      api('/api/assistant/stop', { id: currentJobId }).catch(() => {});
      currentJobId = '';
    }
    if (activeBotCard) {
      activeBotCard.markStopped('أُوقفت لبدء محادثة جديدة');
      activeBotCard = null;
    }
    if (stopBtn) stopBtn.disabled = true;
    updateSendButtonState();

    if (chatContainer) {
      const toRemove = [];
      for (const ch of chatContainer.children) {
        if (ch !== emptyStateEl) toRemove.push(ch);
      }
      toRemove.forEach(c => c.remove());
    }
    messages = [];
    updateEmptyStateVisibility();
    addMessage('sys', 'بدأت محادثة جديدة عبر ' + getActiveSourceLabel() + '.');
    if (chatsLoaded) renderChatsTab();
  }

  function fillInput(text) {
    if (!inputEl) return;
    inputEl.value = text;
    autoResizeInput();
    inputEl.focus();
    inputEl.setSelectionRange(text.length, text.length);
  }

  /* سجل الطلبات المرسلة: ↑ يرجع إلى الأقدم و↓ إلى الأحدث، وآخر ↓ يعيد ما كنت تكتبه */
  const HISTORY_KEY = 'zajel_as_history';
  let sendHistory = [];
  let historyIdx = -1;
  let historyDraft = '';
  try { sendHistory = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]').filter(x => typeof x === 'string'); } catch (_) { sendHistory = []; }

  function rememberSent(text) {
    const t = String(text || '').trim();
    historyIdx = -1;
    if (!t) return;
    sendHistory = sendHistory.filter(x => x !== t);
    sendHistory.push(t);
    if (sendHistory.length > 60) sendHistory = sendHistory.slice(-60);
    try { localStorage.setItem(HISTORY_KEY, JSON.stringify(sendHistory)); } catch (_) {}
  }

  function stepHistory(dir) {
    if (!sendHistory.length || !inputEl) return false;
    if (historyIdx === -1) {
      if (dir > 0) return false;
      historyDraft = inputEl.value;
      historyIdx = sendHistory.length;
    }
    const next = historyIdx + dir;
    if (next < 0) return true;
    historyIdx = next;
    inputEl.value = next >= sendHistory.length ? historyDraft : sendHistory[next];
    if (next >= sendHistory.length) historyIdx = -1;
    autoResizeInput();
    updateImproveBtn();
    const end = inputEl.value.length;
    inputEl.setSelectionRange(end, end);
    return true;
  }

  let improveRowEl = null;
  let improveBtnEl = null;
  function updateImproveBtn() {
    if (!improveBtnEl || !inputEl) return;
    improveBtnEl.hidden = inputEl.value.trim().length < 6;
  }

  function copyPlain(text, okMsg) {
    const done = () => safeNote(okMsg || 'تم النسخ');
    const fallback = () => {
      try {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.cssText = 'position:fixed;opacity:0;top:0;left:0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        ta.remove();
        done();
      } catch (_) { safeNote('تعذر النسخ'); }
    };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done).catch(fallback);
    else fallback();
  }

  async function showImproveModal() {
    const raw = inputEl ? inputEl.value.trim() : '';
    if (raw.length < 4) { safeNote('اكتب طلبًا أولًا.'); return; }
    const old = document.querySelector('.as-imp-overlay');
    if (old) old.remove();
    const overlay = el('div', '', 'as-imp-overlay');
    const box = el('div', '', 'as-imp-box');
    overlay.appendChild(box);
    overlay.addEventListener('mousedown', e => { if (e.target === overlay) { token++; overlay.remove(); } });
    document.body.appendChild(overlay);
    let token = 0;

    const render = d => {
      box.replaceChildren();
      const head = el('div', '', 'as-imp-head');
      head.append(el('b', '✨ الطلب بعد التحسين'), el('span', d.type_ar || 'عام', 'as-imp-chip'));
      if (d.source) head.appendChild(el('span', 'بواسطة ' + d.source, 'as-imp-chip'));
      const x = btn('✕', () => { token++; overlay.remove(); }, 'btn as-imp-x', { 'aria-label': 'إغلاق' });
      head.appendChild(x);
      box.appendChild(head);
      if (d.notes) box.appendChild(el('div', d.notes, 'as-imp-notes'));
      if (Array.isArray(d.missing) && d.missing.length) {
        const mq = el('div', '', 'as-imp-notes');
        mq.appendChild(el('b', 'تفاصيل ناقصة يفيد أن تضيفها: '));
        d.missing.forEach(q => mq.appendChild(el('div', '• ' + q)));
        box.appendChild(mq);
      }
      const section = (title, text, dir, useMsg) => {
        const sec = el('div', '', 'as-imp-sec');
        const h = el('div', '', 'as-imp-sec-h');
        h.appendChild(el('b', title));
        const acts = el('span', '', 'as-imp-acts');
        acts.append(
          btn('نسخ', () => copyPlain(text, 'نُسخ ' + title), 'btn'),
          btn('استعمله في المربع', () => { fillInput(text); overlay.remove(); safeNote(useMsg); }, 'btn')
        );
        h.appendChild(acts);
        const pre = el('div', text || '(لا نص)', 'as-imp-text');
        pre.dir = dir;
        sec.append(h, pre);
        return sec;
      };
      box.append(section('العربية', d.ar, 'rtl', 'وُضعت النسخة العربية في المربع'), section('English', d.en, 'ltr', 'وُضعت النسخة الإنجليزية في المربع'));
      const foot = el('div', '', 'as-imp-foot');
      foot.append(
        btn('نسخ الكل (عربي + English)', () => copyPlain('=== العربية ===\n' + d.ar + '\n\n=== English ===\n' + d.en, 'نُسخ الموجّه كاملًا بالعربية والإنجليزية'), 'btn pri'),
        btn('إعادة التحسين', () => run(), 'btn'),
        btn('إغلاق', () => { token++; overlay.remove(); }, 'btn')
      );
      const altKeys = Object.keys(d.alts || {});
      if (altKeys.length) {
        altKeys.forEach(k => foot.appendChild(btn('قارن بنسخة ' + d.alts[k].source, () => render(Object.assign({}, d.alts[k], { alts: { _: Object.assign({}, d, { alts: {} }) } })), 'btn')));
      } else if (d.pending > 0) {
        foot.appendChild(el('span', '⏳ يجري جلب نسخة ثانية للمقارنة…', 'as-imp-notes'));
      }
      box.appendChild(foot);
      if (d.pending > 0 && d.id) {
        const my = token;
        setTimeout(async () => {
          if (my !== token || !document.body.contains(box)) return;
          try {
            const v = await api('/api/assistant/improve/get?id=' + encodeURIComponent(d.id));
            if (my === token && document.body.contains(box)) {
              if (v.state === 'done' && Object.keys(v.alts || {}).length) render(Object.assign({}, v, { id: d.id }));
              else if (v.pending > 0) render(Object.assign({}, d, { pending: v.pending }));
              else render(Object.assign({}, d, { pending: 0 }));
            }
          } catch (_) {}
        }, 4000);
      }
    };

    const fail = msg => {
      box.replaceChildren(el('div', 'تعذّر تحسين الطلب: ' + msg, 'as-imp-notes'));
      const foot = el('div', '', 'as-imp-foot');
      foot.append(btn('حاول مرة أخرى', () => run(), 'btn pri'), btn('إغلاق', () => overlay.remove(), 'btn'));
      box.appendChild(foot);
    };

    const run = async () => {
      const my = ++token;
      box.replaceChildren(el('div', '⏳ جارٍ تحويل طلبك إلى موجّه احترافي… قد يستغرق دقيقة.', 'as-imp-wait'));
      try {
        const r = await api('/api/assistant/improve', { text: raw });
        for (let i = 0; i < 150; i++) {
          await new Promise(res => setTimeout(res, 2000));
          if (my !== token) return;
          const v = await api('/api/assistant/improve/get?id=' + encodeURIComponent(r.id));
          if (v.state === 'done') { render(Object.assign({}, v, { id: r.id })); return; }
          if (v.state === 'error') { fail(v.error || 'خطأ'); return; }
        }
        fail('انتهت المهلة.');
      } catch (e) {
        if (my === token) fail(e.message || 'خطأ');
      }
    };
    run();
  }

  function autoResizeInput() {
    if (!inputEl) return;
    inputEl.style.height = 'auto';
    const newHeight = Math.min(inputEl.scrollHeight, 168);
    inputEl.style.height = Math.max(newHeight, 44) + 'px';
  }

  function updateQueuedBar(queuedItems) {
    if (!queuedBarEl) return;
    const items = Array.isArray(queuedItems) ? queuedItems.filter(Boolean) : [];
    if (!items.length) {
      queuedBarEl.hidden = true;
      queuedBarEl.replaceChildren();
      return;
    }
    queuedBarEl.hidden = false;
    queuedBarEl.replaceChildren();

    const iconSpan = el('span', '', 'as-queued-bar-icon');
    iconSpan.appendChild(createSvg('queue', 13));

    const count = items.length;
    let label = '';
    if (count === 1) {
      label = 'في الطابور: تعقيب واحد سيُنفَّذ بعد المهمة الحالية';
    } else if (count === 2) {
      label = 'في الطابور: ٢ تعقيبات سيُنفَّذان معًا بعد المهمة الحالية';
    } else if (count >= 3 && count <= 10) {
      label = 'في الطابور: ' + count + ' تعقيبات سيُنفَّذان معًا بعد المهمة الحالية';
    } else {
      label = 'في الطابور: ' + count + ' تعقيبًا سيُنفَّذون معًا بعد المهمة الحالية';
    }

    const textSpan = el('span', label, 'as-queued-bar-text');
    queuedBarEl.append(iconSpan, textSpan);
  }

  function updateSendButtonState() {
    if (!sendBtn) return;
    const isWorking = Boolean(currentJobId);
    const hasUploading = pendingAttachments.some(a => a.status === 'uploading');
    const hasReadyAttachments = pendingAttachments.some(a => a.status === 'done');
    const hasText = Boolean(inputEl && inputEl.value.trim());

    sendBtn.replaceChildren(
      createSvg('send', 14),
      el('span', isWorking ? 'أضف للطابور' : 'أرسل', 'as-btn-label')
    );

    if (hasUploading) {
      sendBtn.disabled = true;
      sendBtn.title = 'جارٍ رفع المرفقات… يرجى الانتظار';
    } else {
      sendBtn.disabled = !hasText && !hasReadyAttachments;
      sendBtn.title = isWorking ? 'إضافة تعقيب إلى طابور المساعد' : 'إرسال الطلب (Enter)';
    }

    updateFloatingBadgeState();
  }

  /* ==========================================================================
     8ب. دوال إدارة المرفقات (رفع، شرائح، معاينة، وحجم) — المهمة B
     ========================================================================== */
  function detectKindFromExtension(fileName, mimeType = '') {
    if (mimeType) {
      if (mimeType.startsWith('image/')) return 'image';
      if (mimeType.startsWith('audio/')) return 'audio';
      if (mimeType.startsWith('video/')) return 'video';
      if (mimeType === 'application/pdf') return 'pdf';
    }
    const ext = (fileName || '').split('.').pop().toLowerCase();
    if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'avif', 'heic', 'heif'].includes(ext)) return 'image';
    if (['mp3', 'wav', 'ogg', 'm4a', 'aac', 'flac', 'opus'].includes(ext)) return 'audio';
    if (['mp4', 'mkv', 'webm', 'mov', 'avi', 'flv'].includes(ext)) return 'video';
    if (ext === 'pdf') return 'pdf';
    if (['doc', 'docx', 'odt', 'rtf'].includes(ext)) return 'doc';
    if (['xls', 'xlsx', 'csv', 'ods'].includes(ext)) return 'sheet';
    if (['ppt', 'pptx', 'odp'].includes(ext)) return 'slides';
    if (['txt', 'md', 'py', 'js', 'json', 'html', 'css', 'ts', 'sh', 'yaml', 'yml', 'xml', 'c', 'cpp', 'h'].includes(ext)) return 'text';
    return 'other';
  }

  function getKindEmoji(kind) {
    switch (kind) {
      case 'audio': return '🎵';
      case 'video': return '🎬';
      case 'pdf': return '📄';
      case 'sheet': return '📊';
      case 'slides': return '📊';
      case 'doc':
      case 'text': return '📝';
      default: return '📎';
    }
  }

  function formatAttachmentSize(bytes) {
    if (bytes == null || isNaN(bytes)) return '—';
    if (bytes >= 1e9) {
      const v = (bytes / 1e9).toFixed(1).replace(/\.0$/, '');
      return toArabicDigits(v) + ' غ.ب';
    }
    if (bytes >= 1e6) {
      const v = (bytes / 1e6).toFixed(1).replace(/\.0$/, '');
      return toArabicDigits(v) + ' م.ب';
    }
    if (bytes >= 1e3) {
      const v = Math.round(bytes / 1e3);
      return toArabicDigits(v) + ' ك.ب';
    }
    return toArabicDigits(bytes) + ' ب';
  }

  function handleFilesAdded(fileList) {
    if (!fileList || !fileList.length) return;
    const files = Array.from(fileList);

    // ١. رفض مبكر للملفات التي تتجاوز 500MB
    const validFiles = [];
    for (const file of files) {
      if (file.size > MAX_ATTACHMENT_SIZE) {
        safeNote('الملف «' + file.name + '» يتجاوز الحد الأقصى المسموح به (500 ميغابايت).');
        continue;
      }
      validFiles.push(file);
    }
    if (!validFiles.length) return;

    // ٢. فحص حد الدفعة (٥ ملفات كحد أقصى)
    let batch = validFiles;
    if (batch.length > MAX_BATCH_FILES) {
      safeNote('الحد الأقصى للإرفاق هو ٥ ملفات في الدفعة الواحدة.');
      batch = batch.slice(0, MAX_BATCH_FILES);
    }

    // ٣. فحص الحد الإجمالي للمرفقات (١٠ ملفات بالمجموع)
    const currentCount = pendingAttachments.filter(a => !a.ref).length;
    if (currentCount >= MAX_TOTAL_ATTACHMENTS) {
      safeNote('الحد الأقصى للمرفقات هو ١٠ ملفات للرسالة الواحدة.');
      return;
    }
    if (currentCount + batch.length > MAX_TOTAL_ATTACHMENTS) {
      safeNote('تم قبول المرفقات حتى الحد الأقصى (١٠ ملفات).');
      const allowed = MAX_TOTAL_ATTACHMENTS - currentCount;
      batch = batch.slice(0, allowed);
    }

    for (const file of batch) {
      const kind = detectKindFromExtension(file.name, file.type);
      let previewUrl = '';
      if (kind === 'image') {
        try {
          previewUrl = URL.createObjectURL(file);
        } catch (_) {}
      }
      const item = {
        id: 'att_' + Date.now() + '_' + Math.random().toString(36).slice(2, 7),
        file,
        name: file.name,
        size: file.size,
        kind,
        status: 'uploading',
        path: '',
        error: '',
        previewUrl,
        uploadingStarted: false
      };
      pendingAttachments.push(item);
    }

    renderAttachmentsBar();
    updateSendButtonState();
    uploadQueuePump();
  }

  function uploadQueuePump() {
    while (activeUploadsCount < MAX_CONCURRENT_UPLOADS) {
      const nextItem = pendingAttachments.find(a => a.status === 'uploading' && !a.uploadingStarted);
      if (!nextItem) break;
      startUploadItem(nextItem);
    }
  }

  async function startUploadItem(item) {
    activeUploadsCount++;
    item.uploadingStarted = true;
    renderAttachmentsBar();
    updateSendButtonState();

    try {
      const uploadUrl = '/api/assistant/upload?name=' + encodeURIComponent(item.name);
      const res = await fetch(uploadUrl, {
        method: 'POST',
        body: item.file
      });
      const data = await res.json();
      if (data && data.ok) {
        item.status = 'done';
        item.path = data.path || '';
        item.id = data.id || item.id;
        if (data.name) item.name = data.name;
        if (data.kind) item.kind = data.kind;
        if (typeof data.size === 'number') item.size = data.size;
        item.error = '';
      } else {
        item.status = 'error';
        item.error = data?.error || 'فشل رفع الملف';
      }
    } catch (err) {
      item.status = 'error';
      item.error = err.message || 'تعذر الاتصال بالخادم';
    } finally {
      activeUploadsCount = Math.max(0, activeUploadsCount - 1);
      renderAttachmentsBar();
      updateSendButtonState();
      uploadQueuePump();
    }
  }

  /* عناصر نتائج البحث المحددة تصير مرفقات مرجعية (لا تُنسخ ولا تُرفع): المساعد يعمل عليها في أماكنها */
  const refPanels = new Map();
  function setRefAttachments(panelId, items) {
    pendingAttachments = pendingAttachments.filter(a => a.panel !== panelId);
    const others = pendingAttachments.filter(a => a.ref).length;
    items.slice(0, Math.max(0, 100 - others)).forEach(it => {
      pendingAttachments.push({ id: 'ref_' + Math.random().toString(36).slice(2, 9), ref: true, panel: panelId, key: it.sid + '|' + it.path, sid: it.sid, path: it.path, name: it.name, size: it.size,
        is_dir: !!it.is_dir, kind: it.is_dir ? 'folder' : detectKindFromExtension(it.name), status: 'done', previewUrl: (typeof entryThumb === 'function' && !it.is_dir) ? (entryThumb(it.sid, it) || '') : '' });
    });
    renderAttachmentsBar();
    updateSendButtonState();
  }
  function removeRefAttachments() {
    pendingAttachments = pendingAttachments.filter(a => !a.ref);
    renderAttachmentsBar();
    updateSendButtonState();
    refPanels.forEach(f => f());
  }

  function removeAttachment(itemId) {
    const idx = pendingAttachments.findIndex(a => a.id === itemId);
    if (idx !== -1) {
      const item = pendingAttachments[idx];
      if (item.previewUrl) {
        try { URL.revokeObjectURL(item.previewUrl); } catch (_) {}
      }
      pendingAttachments.splice(idx, 1);
      renderAttachmentsBar();
      updateSendButtonState();
      uploadQueuePump();
    }
  }

  function retryAttachment(itemId) {
    const item = pendingAttachments.find(a => a.id === itemId);
    if (!item) return;
    item.status = 'uploading';
    item.error = '';
    item.uploadingStarted = false;
    renderAttachmentsBar();
    updateSendButtonState();
    uploadQueuePump();
  }

  function clearAttachments() {
    pendingAttachments.forEach(it => {
      if (it.previewUrl) {
        try { URL.revokeObjectURL(it.previewUrl); } catch (_) {}
      }
    });
    pendingAttachments = [];
    renderAttachmentsBar();
    updateSendButtonState();
    refPanels.forEach(f => f());
  }

  function renderAttachmentsBar() {
    if (!attachmentsBarEl) return;
    if (inputEl) {
      const rn = pendingAttachments.filter(a => a.ref).length;
      inputEl.placeholder = rn ? 'اكتب ما تريده لهذه الملفات (' + rn + ')… نسخ، تحليل، جمع، إرسال…' : 'اكتب طلبك هنا…';
    }
    if (!pendingAttachments.length) {
      attachmentsBarEl.hidden = true;
      attachmentsBarEl.replaceChildren();
      return;
    }
    attachmentsBarEl.hidden = false;
    attachmentsBarEl.replaceChildren();

    const refItems = pendingAttachments.filter(a => a.ref);
    if (refItems.length) {                       // عناصر محددة من نتائج البحث: بطاقة واحدة مجمّعة
      const g = el('div', '', 'as-attach-chip as-ref-group');
      const th = el('div', '', 'as-ref-thumbs');
      refItems.slice(0, 3).forEach(it => {
        if (it.previewUrl) { const im = el('img', '', 'as-chip-thumb', { src: it.previewUrl, alt: it.name, loading: 'lazy' }); im.onerror = () => { im.replaceWith(el('span', getKindEmoji(it.kind), 'as-chip-kind-ico')); }; th.appendChild(im); }
        else th.appendChild(el('span', it.is_dir ? '📁' : getKindEmoji(it.kind), 'as-chip-kind-ico'));
      });
      const gi = el('div', '', 'as-chip-info');
      gi.append(el('span', refItems.length + ' ' + (refItems.length > 2 ? 'عنصرًا محددًا' : 'عنصر محدد') + ' من النتائج', 'as-chip-name'),
                el('span', refItems.slice(0, 3).map(i => i.name).join('، ') + (refItems.length > 3 ? '…' : ''), 'as-chip-size', { title: refItems.map(i => i.name).join('\n') }));
      const rm = el('button', '✕', 'as-chip-remove-btn', { type: 'button', title: 'إزالة التحديد', 'aria-label': 'إزالة العناصر المحددة' });
      rm.onclick = e => { e.stopPropagation(); removeRefAttachments(); };
      const ac = el('div', '', 'as-chip-actions'); ac.appendChild(rm);
      g.append(th, gi, ac);
      attachmentsBarEl.appendChild(g);
    }

    pendingAttachments.filter(a => !a.ref).forEach(item => {
      const isErr = item.status === 'error';
      const isUp = item.status === 'uploading';
      const chip = el('div', '', 'as-attach-chip' + (isErr ? ' as-chip-err' : ''), {
        role: 'group',
        'aria-label': 'مرفق: ' + item.name + (isErr ? ' - خطأ: ' + item.error : isUp ? ' - جارٍ الرفع' : '')
      });

      if (item.kind === 'image') {
        const thumbSrc = item.path ? ('/api/assistant/upload/file?path=' + encodeURIComponent(item.path)) : (item.previewUrl || '');
        if (thumbSrc) {
          const img = el('img', '', 'as-chip-thumb', {
            src: thumbSrc,
            alt: item.name
          });
          img.onerror = () => {
            img.style.display = 'none';
          };
          chip.appendChild(img);
        } else {
          chip.appendChild(el('span', '🖼️', 'as-chip-kind-ico'));
        }
      } else {
        chip.appendChild(el('span', getKindEmoji(item.kind), 'as-chip-kind-ico'));
      }

      const info = el('div', '', 'as-chip-info');
      const nameEl = el('span', item.name, 'as-chip-name', { title: item.name });
      info.appendChild(nameEl);

      if (isErr) {
        const errEl = el('span', item.error || 'فشل الرفع', 'as-chip-err-text', { title: item.error });
        info.appendChild(errEl);
      } else if (isUp) {
        const statEl = el('span', 'جارٍ الرفع… (' + formatAttachmentSize(item.size) + ')', 'as-chip-size');
        info.appendChild(statEl);
      } else {
        const sizeEl = el('span', formatAttachmentSize(item.size), 'as-chip-size');
        info.appendChild(sizeEl);
      }
      chip.appendChild(info);

      const actions = el('div', '', 'as-chip-actions');
      if (isErr) {
        const retryBtn = el('button', '↻', 'as-chip-retry-btn', {
          type: 'button',
          title: 'إعادة محاولة الرفع',
          'aria-label': 'إعادة محاولة رفع ' + item.name
        });
        retryBtn.onclick = (e) => {
          e.stopPropagation();
          retryAttachment(item.id);
        };
        actions.appendChild(retryBtn);
      }

      const removeBtn = el('button', '✕', 'as-chip-remove-btn', {
        type: 'button',
        title: 'إزالة المرفق',
        'aria-label': 'إزالة ' + item.name
      });
      removeBtn.onclick = (e) => {
        e.stopPropagation();
        removeAttachment(item.id);
      };
      actions.appendChild(removeBtn);
      chip.appendChild(actions);

      if (isUp) {
        const pbar = el('div', '', 'as-chip-progress-bar');
        const fill = el('div', '', 'as-chip-progress-fill');
        fill.style.width = '65%';
        pbar.appendChild(fill);
        chip.appendChild(pbar);
      }

      attachmentsBarEl.appendChild(chip);
    });
  }

  function renderMessageAttachments(attachmentsList) {
    if (!Array.isArray(attachmentsList) || !attachmentsList.length) return null;
    const container = el('div', '', 'as-msg-attachments');
    const refsHere = attachmentsList.filter(a => a && a.ref);
    if (refsHere.length) {
      container.appendChild(el('div', '📎 ' + refsHere.length + ' من النتائج: ' + refsHere.slice(0, 3).map(r => r.name).join('، ') + (refsHere.length > 3 ? '…' : ''), 'as-msg-ref', { title: refsHere.map(r => r.name).join('\n') }));
      attachmentsList = attachmentsList.filter(a => !(a && a.ref));
    }

    attachmentsList.forEach(att => {
      if (!att) return;
      const attName = att.name || 'ملف مرفق';
      const attKind = att.kind || detectKindFromExtension(attName);
      const isImg = attKind === 'image';

      if (isImg && att.path) {
        const card = el('div', '', 'as-msg-attach-img-card', {
          title: 'انقر لتكبير صورة: ' + attName,
          role: 'button',
          tabindex: '0',
          'aria-label': 'عرض صورة مكبرة: ' + attName
        });
        const imgSrc = '/api/assistant/upload/file?path=' + encodeURIComponent(att.path);
        const img = el('img', '', 'as-msg-attach-thumb', {
          src: imgSrc,
          alt: attName
        });
        card.appendChild(img);
        const openModal = () => showImageModal(imgSrc, attName);
        card.onclick = openModal;
        card.onkeydown = (e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            openModal();
          }
        };
        container.appendChild(card);
      } else {
        const chip = el('div', '', 'as-msg-attach-file-chip', {
          title: attName,
          'aria-label': 'مرفق: ' + attName
        });
        const ico = el('span', getKindEmoji(attKind), 'as-msg-attach-file-ico');
        const nameSpan = el('span', attName, 'as-msg-attach-file-name');
        chip.append(ico, nameSpan);
        if (att.path) {
          chip.style.cursor = 'pointer';
          chip.onclick = () => {
            const fileUrl = '/api/assistant/upload/file?path=' + encodeURIComponent(att.path);
            window.open(fileUrl, '_blank');
          };
        }
        container.appendChild(chip);
      }
    });

    return container;
  }

  function showImageModal(imgSrc, captionText) {
    if (activeImageModalEl) {
      activeImageModalEl.remove();
      activeImageModalEl = null;
    }
    const modal = el('div', '', 'as-img-modal', {
      role: 'dialog',
      'aria-label': 'معاينة الصورة المكبرة',
      tabindex: '-1'
    });
    const content = el('div', '', 'as-img-modal-content');
    const closeBtn = el('button', '✕', 'as-img-modal-close', {
      type: 'button',
      title: 'إغلاق المعاينة (Esc)',
      'aria-label': 'إغلاق المعاينة'
    });
    const img = el('img', '', 'as-img-modal-img', {
      src: imgSrc,
      alt: captionText || 'صورة مكبرة'
    });
    content.append(closeBtn, img);

    if (captionText) {
      const caption = el('div', captionText, 'as-img-modal-caption');
      content.appendChild(caption);
    }
    modal.appendChild(content);

    const closeModal = () => {
      modal.remove();
      if (activeImageModalEl === modal) activeImageModalEl = null;
    };

    closeBtn.onclick = (e) => {
      e.stopPropagation();
      closeModal();
    };

    modal.onclick = (e) => {
      if (e.target === modal || e.target === content) {
        closeModal();
      }
    };

    document.body.appendChild(modal);
    activeImageModalEl = modal;
    modal.focus();
  }

  /* ==========================================================================
     9. شارة المصدر والنموذج في الترويسة
     ========================================================================== */
  function getActiveSourceLabel() {
    const ag = agentsList.find(a => a.id === activeAgentId);
    const agName = ag ? ag.name : activeAgentId;
    const curModel = activeModel || (ag ? ag.model : '');
    if (!curModel) return agName;
    const shortModel = curModel.length > 26 ? curModel.slice(0, 24) + '…' : curModel;
    return agName + ' · ' + shortModel;
  }

  function updateSourceBadge() {
    if (!sourceBadgeText) return;
    const label = getActiveSourceLabel();
    sourceBadgeText.textContent = label;
    sourceBadgeText.title = 'المصدر الحالي: ' + label + ' (انقر للإعدادات والتبديل)';
  }

  /* ==========================================================================
     10. تبويب «المحادثات»: استرجاع، بحث فلتري، إعادة تسمية، وحذف
     ========================================================================== */
  async function loadChats() {
    try {
      const res = await api('/api/assistant/chats');
      chatsData = Array.isArray(res?.chats) ? res.chats : [];
      chatsLoaded = true;
      renderChatsTab();
    } catch (err) {
      chatsLoaded = true;
      renderChatsTab(err.message);
    }
  }

  function renderChatsTab(errorMsg = '') {
    if (activeTab !== 'chats' || !sideContentEl) return;
    sideContentEl.replaceChildren();

    // رأس التبويب وزر محادثة جديدة
    const headRow = el('div', '', 'as-tab-head-row');
    const title = el('span', 'سجل المحادثات', 'as-tab-head-title');
    const newBtn = btn('', () => newChat(), 'btn', {
      title: 'بدء محادثة جديدة'
    });
    newBtn.style.padding = '3px 7px';
    newBtn.style.fontSize = '11px';
    newBtn.append(createSvg('plus', 12), document.createTextNode('جديدة'));
    headRow.append(title, newBtn);
    sideContentEl.appendChild(headRow);

    // حقل البحث الفلتري المحلي
    const searchInp = el('input', '', 'as-side-input', {
      placeholder: 'بحث في المحادثات…',
      type: 'text'
    });
    searchInp.value = chatSearchQuery;
    searchInp.oninput = () => {
      chatSearchQuery = searchInp.value.trim().toLowerCase();
      renderChatList(listWrap);
    };
    sideContentEl.appendChild(searchInp);

    if (errorMsg) {
      sideContentEl.appendChild(el('div', 'تعذر تحميل المحادثات: ' + errorMsg, 'as-card-err'));
      return;
    }

    const listWrap = el('div', '', 'as-tab-list-wrap');
    listWrap.style.display = 'flex';
    listWrap.style.flexDirection = 'column';
    listWrap.style.gap = '6px';
    sideContentEl.appendChild(listWrap);

    renderChatList(listWrap);
  }

  function renderChatList(container) {
    container.replaceChildren();

    let filtered = chatsData.slice();
    if (chatSearchQuery) {
      filtered = filtered.filter(c => (c.title || '').toLowerCase().includes(chatSearchQuery));
    }

    // ترتيب بالأحدث
    filtered.sort((a, b) => (b.updated || 0) - (a.updated || 0));

    if (filtered.length === 0) {
      const emptyNotice = el('div', chatSearchQuery ? 'لا توجد محادثات مطابقة للبحث.' : 'لا توجد محادثات محفوظة بعد.', 'as-memory-hint');
      emptyNotice.style.textAlign = 'center';
      container.appendChild(emptyNotice);
      return;
    }

    filtered.forEach(chat => {
      const isCurrent = chat.id === currentConversation;
      const itemEl = el('div', '', 'as-chat-item' + (isCurrent ? ' is-current' : ''));

      const head = el('div', '', 'as-chat-item-head');
      const titleWrap = el('div', '', 'as-chat-title-wrap');

      if (isCurrent) {
        const dot = el('span', '', 'as-active-dot', { title: 'المحادثة المفتوحة حاليًا' });
        titleWrap.appendChild(dot);
      }

      const titleTxt = el('span', chat.title || 'محادثة بلا عنوان', 'as-chat-title');
      titleWrap.appendChild(titleTxt);

      // أزرار إعادة التسمية والحذف
      const actions = el('div', '', 'as-chat-item-actions');

      const renameBtn = el('button', '', 'as-item-mini-btn edit-btn', {
        title: 'إعادة تسمية المحادثة',
        type: 'button'
      });
      renameBtn.appendChild(createSvg('edit', 12));
      renameBtn.onclick = async (e) => {
        e.stopPropagation();
        const newTitle = window.prompt('أدخل العنوان الجديد للمحادثة:', chat.title || '');
        if (!newTitle || !newTitle.trim() || newTitle.trim() === chat.title) return;
        try {
          await api('/api/assistant/chat/rename', { id: chat.id, title: newTitle.trim() });
          chat.title = newTitle.trim();
          renderChatList(container);
          safeNote('تم تغيير عنوان المحادثة');
        } catch (err) {
          safeNote('تعذر إعادة التسمية: ' + (err.message || ''));
        }
      };

      const delBtn = el('button', '', 'as-item-mini-btn', {
        title: 'حذف المحادثة',
        type: 'button'
      });
      delBtn.appendChild(createSvg('trash', 12));
      delBtn.onclick = async (e) => {
        e.stopPropagation();
        if (!window.confirm('هل أنت متأكد من حذف هذه المحادثة نهائيًا؟')) return;
        try {
          await api('/api/assistant/chat/delete', { id: chat.id });
          chatsData = chatsData.filter(c => c.id !== chat.id);
          renderChatList(container);
          if (chat.id === currentConversation) {
            newChat();
          }
          safeNote('تم حذف المحادثة');
        } catch (err) {
          safeNote('تعذر حذف المحادثة: ' + (err.message || ''));
        }
      };

      actions.append(renameBtn, delBtn);
      head.append(titleWrap, actions);

      const meta = el('div', '', 'as-chat-meta');
      const timeStr = formatRelativeTime(chat.updated);
      const countStr = (chat.count || 0) + ' رسائل';
      meta.append(el('span', timeStr), el('span', countStr));

      itemEl.append(head, meta);

      // النقر يحمل المحادثة كاملة
      itemEl.onclick = () => loadChatHistory(chat.id);

      container.appendChild(itemEl);
    });
  }

  async function loadChatHistory(chatId) {
    try {
      const data = await api('/api/assistant/chat/get?id=' + encodeURIComponent(chatId));
      if (!data) return;

      currentConversation = data.id || chatId;
      try { localStorage.setItem('zajel_as_last_chat', currentConversation); } catch (_) {}
      if (data.agent) activeAgentId = data.agent;
      if (data.model) activeModel = data.model;
      updateSourceBadge();

      // تفريغ المحادثة وعرض الرسائل
      if (chatContainer) {
        const toRemove = [];
        for (const ch of chatContainer.children) {
          if (ch !== emptyStateEl) toRemove.push(ch);
        }
        toRemove.forEach(c => c.remove());
      }
      messages = [];

      const msgList = Array.isArray(data.messages) ? data.messages : [];
      msgList.forEach(m => {
        if (m.role === 'user') {
          addMessage('user', m.text, m.attachments);
        } else if (m.role === 'assistant') {
          if (m.error) {
            renderErrorMessage(m.error);
          } else {
            renderHistoricBotMessage(m);
          }
        }
      });

      updateEmptyStateVisibility();
      scrollToChatBottom(false);

      if (window.innerWidth < 600) {
        toggleSidebar(false);
      }
      renderChatsTab();
    } catch (err) {
      safeNote('تعذر استرجاع المحادثة: ' + (err.message || ''));
    }
  }

  function renderHistoricBotMessage(data) {
    if (!chatContainer) return;
    const card = el('div', '', 'as-msg as-msg-bot');
    const bodyText = el('div', '', 'as-msg-body');
    const finalText = data.text || '';
    renderWithChoices(bodyText, finalText, false);

    // تذييل الرسالة مع وسم «قُطعت بتعقيب» إن كانت حالتها stopped
    const footer = el('div', '', 'as-bot-footer');
    const metaTag = el('div', '', 'as-bot-meta-tag');

    if (data.state === 'stopped') {
      const stoppedPill = el('span', 'قُطعت بتعقيب', 'as-pill stopped');
      metaTag.appendChild(stoppedPill);
    }

    const ag = agentsList.find(a => a.id === data.agent);
    const agName = ag ? ag.name : (data.agent || activeAgentId);
    const modName = data.model || '';
    const durStr = data.secs != null ? (data.secs + ' ث') : '';
    metaTag.appendChild(document.createTextNode(agName + (modName ? ' · ' + modName : '') + (durStr ? ' · ' + durStr : '')));

    const copyBtn = btn('', () => {
      try {
        navigator.clipboard.writeText(finalText);
        copyBtn.classList.add('copied');
        copyBtn.replaceChildren(createSvg('check', 12), document.createTextNode('تم النسخ'));
        setTimeout(() => {
          copyBtn.classList.remove('copied');
          copyBtn.replaceChildren(createSvg('copy', 12), document.createTextNode('نسخ'));
        }, 2000);
      } catch (_) {
        safeNote('تم نسخ النص');
      }
    }, 'as-copy-btn');
    copyBtn.append(createSvg('copy', 12), document.createTextNode('نسخ'));

    footer.append(metaTag, copyBtn);
    card.append(bodyText, footer);

    chatContainer.appendChild(card);
    messages.push({ type: 'bot', element: card });
    trimMessages();
  }

  /* ==========================================================================
     11. تبويب «الذاكرة»: قائمة بيضاء أنيقة، إضافة معلومة، وحذف
     ========================================================================== */
  let memoryBudget = { used: 0, limit: 2200 };

  async function loadMemory(silent = false) {
    try {
      const res = await api('/api/assistant/memory');
      memoryList = Array.isArray(res?.memory) ? res.memory : [];
      memoryBudget = res?.budget || memoryBudget;
      if (res?.status && typeof res.status === 'object') {
        memoryStatus = { ...memoryStatus, ...res.status };
      }
      memoryLoaded = true;
      renderMemoryTab();
      if (memoryStatus.running && !memoryOrganizeTimer) {
        startOrganizePolling();
      }
    } catch (err) {
      memoryLoaded = true;
      if (!silent) renderMemoryTab(err.message);
    }
  }

  function startOrganizePolling() {
    if (memoryOrganizeTimer) return;
    memoryOrganizeTimer = setInterval(async () => {
      try {
        const res = await api('/api/assistant/memory');
        if (Array.isArray(res?.memory)) memoryList = res.memory;
        memoryBudget = res?.budget || memoryBudget;
        if (res?.status && typeof res.status === 'object') {
          memoryStatus = { ...memoryStatus, ...res.status };
        }
        if (!memoryStatus.running) {
          stopOrganizePolling();
          safeNote('اكتمل تنظيم الذاكرة');
        }
        if (activeTab === 'memory') {
          renderMemoryTab();
        }
      } catch (_) {}
    }, 2000);
  }

  function stopOrganizePolling() {
    if (memoryOrganizeTimer) {
      clearInterval(memoryOrganizeTimer);
      memoryOrganizeTimer = null;
    }
  }

  async function renderMemoryImportPanel() {
    const panel = el('div', '', 'as-memory-import-panel');
    panel.style.cssText = 'border:1px solid var(--line);border-radius:12px;padding:10px;margin:6px 0;background:var(--surface)';
    panel.appendChild(el('div', 'استيراد من وكيل', 'as-card-title'));
    const source = el('select', '', 'as-select');
    const hermes = el('option', 'Hermes'); hermes.value = 'hermes'; source.appendChild(hermes);
    const scanBtn = btn('افحص الذاكرة', async () => {
      scanBtn.disabled = true;
      try {
        const res = await api('/api/assistant/memory/import/scan', { agent: source.value });
        const candidates = Array.isArray(res?.candidates) ? res.candidates : [];
        const table = el('div', ''); table.style.cssText = 'display:flex;flex-direction:column;gap:5px;margin-top:8px';
        candidates.forEach((candidate, index) => {
          const row = el('label', '', 'as-memory-import-row'); row.style.cssText = 'display:flex;gap:7px;align-items:flex-start;padding:6px;border-bottom:1px solid var(--line)';
          const checkbox = el('input', '', '', { type: 'checkbox' }); checkbox.checked = candidate.status === 'new'; checkbox.disabled = candidate.status !== 'new'; checkbox.dataset.index = String(index);
          const status = candidate.status === 'dup' ? 'مكرر' : candidate.status === 'secret' ? 'سر محجوب' : 'جديد';
          row.append(checkbox, el('span', candidate.text || ''), el('span', status, 'as-pill')); table.appendChild(row);
        });
        const commitBtn = btn('احفظ المحدد', async () => {
          const texts = [...table.querySelectorAll('input[type="checkbox"]:checked')].map(input => candidates[Number(input.dataset.index)]?.text).filter(Boolean);
          if (!texts.length) { safeNote('حدد عناصر جديدة للحفظ'); return; }
          commitBtn.disabled = true;
          try { await api('/api/assistant/memory/import/commit', { agent: source.value, texts }); await loadMemory(true); safeNote('تم حفظ العناصر المحددة'); }
          catch (err) { safeNote('تعذر الاستيراد: ' + (err.message || '')); }
          finally { commitBtn.disabled = false; }
        }, 'btn pri');
        panel.replaceChildren(el('div', 'استيراد من وكيل', 'as-card-title'), source, scanBtn, table, commitBtn);
      } catch (err) { safeNote('تعذر فحص المصدر: ' + (err.message || '')); }
      finally { scanBtn.disabled = false; }
    }, 'btn');
    panel.append(source, scanBtn);
    const addBox = sideContentEl.querySelector('.as-add-memory-box');
    if (addBox) addBox.before(panel); else sideContentEl.appendChild(panel);
  }

  function formatUses(n) {
    if (n === 1) return 'استُعمل مرة واحدة';
    if (n === 2) return 'استُعمل مرتان';
    if (n >= 3 && n <= 10) return 'استُعمل ' + n + ' مرات';
    return 'استُعمل ' + n + ' مرة';
  }

  function renderMemoryTab(errorMsg = '') {
    if (activeTab !== 'memory' || !sideContentEl) return;
    sideContentEl.replaceChildren();

    // ١) رأس يشرح بسطر مع مفتاح تبديل التعلم التلقائي وزر التنظيم
    const headBox = el('div', '', 'as-memory-head-box');

    const topRow = el('div', '', 'as-memory-head-top');
    const descEl = el('div', 'يتعلم المساعد من محادثاتك تلقائيًا، ويدمج المكرر ويحدّث القديم ويحذف البالي.', 'as-memory-desc');

    const toggleLabel = el('label', '', 'as-toggle-label');
    const isAuto = memoryStatus.auto !== false;
    if (isAuto) toggleLabel.classList.add('is-active');

    const toggleNative = el('input', '', 'as-switch-native', { type: 'checkbox' });
    toggleNative.checked = isAuto;

    const toggleText = el('span', 'التعلم التلقائي');
    const switchTrack = el('span', '', 'as-switch-track');
    const switchThumb = el('span', '', 'as-switch-thumb');
    switchTrack.appendChild(switchThumb);

    toggleNative.onchange = async () => {
      const targetVal = toggleNative.checked;
      toggleNative.disabled = true;
      try {
        const res = await api('/api/assistant/settings', { auto_learn: targetVal });
        memoryStatus.auto = targetVal;
        if (res?.settings && typeof res.settings.auto_learn !== 'undefined') {
          memoryStatus.auto = !!res.settings.auto_learn;
        }
        toggleNative.checked = !!memoryStatus.auto;
        toggleLabel.classList.toggle('is-active', !!memoryStatus.auto);
        safeNote(memoryStatus.auto ? 'تم تفعيل التعلم التلقائي' : 'تم تعطيل التعلم التلقائي');
      } catch (err) {
        toggleNative.checked = !targetVal;
        toggleLabel.classList.toggle('is-active', toggleNative.checked);
        safeNote('تعذر تعديل الإعداد: ' + (err.message || ''));
      } finally {
        toggleNative.disabled = false;
      }
    };

    toggleLabel.append(toggleNative, toggleText, switchTrack);
    topRow.append(descEl, toggleLabel);
    headBox.appendChild(topRow);

    const budget = memoryBudget || { used: 0, limit: 2200 };
    const budgetWrap = el('div', '', 'as-memory-budget');
    budgetWrap.style.cssText = 'margin-top:8px';
    budgetWrap.appendChild(el('div', 'ميزانية الذاكرة: ' + Number(budget.used || 0).toLocaleString('ar') + ' / ' + Number(budget.limit || 2200).toLocaleString('ar'), 'as-memory-desc'));
    const budgetTrack = el('div', ''); budgetTrack.style.cssText = 'height:5px;background:var(--line);border-radius:5px;overflow:hidden;margin-top:4px';
    const budgetFill = el('div', ''); budgetFill.style.cssText = 'height:100%;width:' + Math.min(100, Math.max(0, Number(budget.used || 0) / Math.max(1, Number(budget.limit || 2200)) * 100)) + '%;background:var(--acc)';
    budgetTrack.appendChild(budgetFill); budgetWrap.appendChild(budgetTrack); headBox.appendChild(budgetWrap);
    const importBtn = btn('استيراد من وكيل', () => renderMemoryImportPanel(), 'btn');
    importBtn.style.cssText = 'margin-top:7px;font-size:11.5px;padding:6px 10px;border-radius:10px'; headBox.appendChild(importBtn);

    // ٢) زر بارز «رتّب الذاكرة الآن»
    const organizeBtn = btn('', async () => {
      if (memoryStatus.running) return;
      organizeBtn.disabled = true;
      try {
        const res = await api('/api/assistant/memory/organize', {});
        memoryStatus.running = true;
        if (res?.status && typeof res.status === 'object') {
          memoryStatus = { ...memoryStatus, ...res.status };
        }
        renderMemoryTab();
        startOrganizePolling();
      } catch (err) {
        safeNote('تعذر بدء التنظيم: ' + (err.message || ''));
        organizeBtn.disabled = false;
      }
    }, 'as-organize-btn');

    if (memoryStatus.running) {
      organizeBtn.disabled = true;
      const spinIco = createSvg('refresh', 13);
      spinIco.classList.add('as-spin');
      organizeBtn.append(spinIco, document.createTextNode('جارٍ التنظيم…'));
    } else {
      organizeBtn.disabled = false;
      organizeBtn.append(createSvg('spark', 13), document.createTextNode('رتّب الذاكرة الآن'));
    }
    headBox.appendChild(organizeBtn);

    // تصدير الذاكرة بعد ترتيبها: ملف Markdown أو JSON في «المستندات/ذاكرة المساعد»، أو نسخ النص، أو رتّب ثم صدّر
    const exportRow = el('div', '', 'as-export-row');
    exportRow.style.cssText = 'display:flex;gap:6px;flex-wrap:wrap;margin-top:8px';
    const doExport = async (fmt, copyOnly) => {
      try {
        const res = await api('/api/assistant/memory/export', { format: fmt });
        if (copyOnly) {
          try { await navigator.clipboard.writeText(res.text || ''); safeNote('نُسخت الذاكرة (' + res.count + ' عنصرًا) إلى الحافظة'); } catch (_) { safeNote('تعذر النسخ إلى الحافظة؛ الملف محفوظ في: ' + res.path); }
        } else {
          safeNote('صُدِّرت الذاكرة (' + res.count + ' عنصرًا) إلى: ' + res.path);
        }
        return res;
      } catch (err) {
        safeNote('تعذر التصدير: ' + (err.message || ''));
        return null;
      }
    };
    const mkExp = (label, fn, cls) => { const b = btn(label, fn, cls || 'btn'); b.style.cssText = 'font-size:11.5px;padding:6px 10px;border-radius:10px'; return b; };
    const orgThenExport = mkExp('رتّب ثم صدّر', async () => {
      if (memoryStatus.running) { safeNote('التنظيم جارٍ الآن؛ انتظر انتهاءه ثم صدّر'); return; }
      orgThenExport.disabled = true;
      orgThenExport.textContent = 'يرتّب…';
      try {
        await api('/api/assistant/memory/organize', {});
        for (let i = 0; i < 90; i++) {
          await new Promise(r => setTimeout(r, 2000));
          const st = await api('/api/assistant/memory');
          if (!(st && st.status && st.status.running)) break;
        }
        await doExport('md', false);
        loadMemory(true);
      } catch (err) {
        safeNote('تعذر الترتيب: ' + (err.message || ''));
      } finally {
        orgThenExport.disabled = false;
        orgThenExport.textContent = 'رتّب ثم صدّر';
      }
    }, 'btn pri');
    exportRow.append(
      mkExp('⤓ تصدير Markdown', () => doExport('md', false)),
      mkExp('⤓ JSON', () => doExport('json', false)),
      mkExp('📋 نسخ', () => doExport('md', true)),
      orgThenExport
    );
    headBox.appendChild(exportRow);

    const statusRow = el('div', '', 'as-organize-status-row');
    let lastTimeText = 'آخر تنظيم: لم يُنظَّم بعد';
    if (memoryStatus.last && memoryStatus.last > 0) {
      lastTimeText = 'آخر تنظيم: ' + formatRelativeTime(memoryStatus.last);
    }
    const timeEl = el('div', lastTimeText);
    statusRow.appendChild(timeEl);

    if (memoryStatus.note && String(memoryStatus.note).trim()) {
      const noteEl = el('div', String(memoryStatus.note).trim(), 'as-organize-note');
      statusRow.appendChild(noteEl);
    }
    headBox.appendChild(statusRow);
    sideContentEl.appendChild(headBox);

    // ٤) حقل إضافة يدوي مع قائمة منسدلة صغيرة لاختيار النوع
    const addBox = el('div', '', 'as-add-memory-box');
    addBox.style.display = 'flex';
    addBox.style.flexDirection = 'column';
    addBox.style.gap = '5px';
    addBox.style.margin = '4px 0';

    const memInp = el('input', '', 'as-side-input', {
      placeholder: 'أضف معلومة جديدة للذاكرة…',
      type: 'text'
    });

    const addRow = el('div', '');
    addRow.style.display = 'flex';
    addRow.style.gap = '5px';
    addRow.style.alignItems = 'center';

    const kindSelect = el('select', '', 'as-select');
    kindSelect.style.flex = '1';
    kindSelect.style.padding = '4px 7px';
    kindSelect.style.fontSize = '11.5px';

    const kindOpts = [
      { val: 'fact',       text: 'معلومات' },
      { val: 'preference', text: 'تفضيلات' },
      { val: 'alias',      text: 'أسماء مختصرة' },
      { val: 'place',      text: 'أماكن' },
      { val: 'routine',    text: 'روتينات متكررة' },
      { val: 'decision', text: 'قرار معتمد' },
      { val: 'question', text: 'سؤال مفتوح' }
    ];
    kindOpts.forEach(k => {
      const opt = el('option', k.text);
      opt.value = k.val;
      kindSelect.appendChild(opt);
    });

    const addBtn = btn('', async () => {
      const txt = memInp.value.trim();
      if (!txt) return;
      addBtn.disabled = true;
      try {
        const res = await api('/api/assistant/memory/add', { text: txt, kind: kindSelect.value, reason: kindSelect.value === 'decision' ? reasonInput.value.trim() : '' });
        if (Array.isArray(res?.memory)) memoryList = res.memory;
        else await loadMemory(true);
        memInp.value = '';
        reasonInput.value = '';
        renderMemoryTab();
        safeNote('تمت إضافة المعلومة إلى الذاكرة');
      } catch (err) {
        safeNote('تعذر الحفظ: ' + (err.message || ''));
      } finally {
        addBtn.disabled = false;
      }
    }, 'btn pri');
    addBtn.style.padding = '5px 12px';
    addBtn.style.fontSize = '11.5px';
    addBtn.append(createSvg('plus', 13), document.createTextNode('أضف'));

    memInp.onkeydown = (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        addBtn.click();
      }
    };

    addRow.append(kindSelect, addBtn);
    const reasonInput = el('input', '', 'as-side-input as-memory-reason', { placeholder: 'السبب (اختياري)', type: 'text' });
    reasonInput.style.display = 'none';
    kindSelect.onchange = () => { reasonInput.style.display = kindSelect.value === 'decision' ? '' : 'none'; };
    addBox.append(memInp, reasonInput, addRow);
    sideContentEl.appendChild(addBox);

    if (errorMsg) {
      sideContentEl.appendChild(el('div', 'تعذر جلب الذاكرة: ' + errorMsg, 'as-card-err'));
      return;
    }

    // ٥) حالة فارغة لطيفة
    if (memoryList.length === 0) {
      const emptyWrap = el('div', '', 'as-memory-empty');
      const emptyIcon = createSvg('brain', 32);
      emptyIcon.style.opacity = '0.5';
      const emptyTitle = el('div', 'الذاكرة فارغة حالياً', 'as-memory-empty-title');
      const emptyDesc = el('div', 'يتعلم المساعد من محادثاتك تلقائيًا ويدمج المعلومات، أو يمكنك إضافة ما تريده يدويًا من الأعلى.', 'as-memory-empty-desc');
      emptyWrap.append(emptyIcon, emptyTitle, emptyDesc);
      sideContentEl.appendChild(emptyWrap);
      return;
    }

    // ٣) العناصر مجمّعة في أقسام بعناوين عربية حسب kind
    const listWrap = el('div', '');
    listWrap.style.display = 'flex';
    listWrap.style.flexDirection = 'column';
    listWrap.style.gap = '8px';
    sideContentEl.appendChild(listWrap);

    const KIND_SECTIONS = [
      { kind: 'preference', title: 'تفضيلات' },
      { kind: 'alias',      title: 'أسماء مختصرة' },
      { kind: 'place',      title: 'أماكن' },
      { kind: 'routine',    title: 'روتينات متكررة' },
      { kind: 'decision',   title: 'قرار معتمد' },
      { kind: 'question',   title: 'سؤال مفتوح' },
      { kind: 'fact',       title: 'معلومات' }
    ];

    const grouped = {
      preference: [],
      alias: [],
      place: [],
      routine: [],
      decision: [],
      question: [],
      fact: []
    };

    memoryList.forEach(item => {
      const k = (item.kind && grouped[item.kind]) ? item.kind : 'fact';
      grouped[k].push(item);
    });

    KIND_SECTIONS.forEach(sec => {
      const items = grouped[sec.kind];
      if (!items || items.length === 0) return;

      // المثبّت في أعلى قسمه، ثم الأحدث
      items.sort((a, b) => {
        const pinA = a.pinned ? 1 : 0;
        const pinB = b.pinned ? 1 : 0;
        if (pinA !== pinB) return pinB - pinA;
        return (b.t || 0) - (a.t || 0);
      });

      const secWrap = el('div', '', 'as-memory-section');
      if (memoryCollapsedKinds.has(sec.kind)) {
        secWrap.classList.add('is-collapsed');
      }

      // ترويسة القسم قابلة للطي
      const headEl = el('div', '', 'as-memory-sec-head');

      const titleWrap = el('div', '', 'as-memory-sec-title');
      const titleText = el('span', sec.title);
      const countBadge = el('span', String(items.length), 'as-sec-count');
      titleWrap.append(titleText, countBadge);

      const chevron = el('span', '', 'as-sec-chevron');
      chevron.appendChild(createSvg('chevron-down', 13));

      headEl.append(titleWrap, chevron);

      headEl.onclick = () => {
        if (memoryCollapsedKinds.has(sec.kind)) {
          memoryCollapsedKinds.delete(sec.kind);
          secWrap.classList.remove('is-collapsed');
        } else {
          memoryCollapsedKinds.add(sec.kind);
          secWrap.classList.add('is-collapsed');
        }
      };

      secWrap.appendChild(headEl);

      const cardList = el('div', '', 'as-memory-sec-list');

      items.forEach(item => {
        const card = el('div', '', 'as-memory-card' + (item.pinned ? ' is-pinned' : '') + (Number(item.rating) === -1 ? ' is-dimmed' : ''));
        if (Number(item.rating) === -1) card.style.opacity = '0.48';

        const topRow = el('div', '', 'as-card-top-row');
        const badges = el('div', '');
        badges.style.display = 'inline-flex';
        badges.style.gap = '5px';
        badges.style.alignItems = 'center';
        badges.style.flexWrap = 'wrap';

        if (item.pinned) {
          const pinBadge = el('span', '', 'as-pill pinned');
          pinBadge.append(createSvg('pin-filled', 10), document.createTextNode('مثبّت'));
          badges.appendChild(pinBadge);
        }
        if (item.auto) {
          badges.appendChild(el('span', 'تلقائي', 'as-pill auto'));
        }
        if (item.uses && item.uses > 0) {
          badges.appendChild(el('span', formatUses(item.uses), 'as-pill uses'));
        }
        if (item.t) {
          badges.appendChild(el('span', formatRelativeTime(item.t), 'as-pill'));
        }

        const actions = el('div', '');
        actions.style.display = 'inline-flex';
        actions.style.gap = '3px';
        actions.style.alignItems = 'center';

        const rateBtn = el('button', '', 'as-item-mini-btn', { title: Number(item.rating) === 1 ? 'إلغاء التقييم' : 'مفيد', type: 'button' });
        rateBtn.appendChild(createSvg('check', 12));
        rateBtn.style.color = Number(item.rating) === 1 ? 'var(--acc)' : '';
        rateBtn.onclick = async () => { try { const res = await api('/api/assistant/memory/rate', { id: item.id, rating: Number(item.rating) === 1 ? 0 : 1 }); if (Array.isArray(res?.memory)) memoryList = res.memory; renderMemoryTab(); } catch (err) { safeNote('تعذر تقييم المعلومة: ' + (err.message || '')); } };
        const downBtn = el('button', '', 'as-item-mini-btn', { title: Number(item.rating) === -1 ? 'إلغاء التقييم' : 'غير مفيد', type: 'button' });
        downBtn.appendChild(createSvg('ban', 12)); downBtn.style.color = Number(item.rating) === -1 ? 'var(--err)' : '';
        downBtn.onclick = async () => { try { const res = await api('/api/assistant/memory/rate', { id: item.id, rating: Number(item.rating) === -1 ? 0 : -1 }); if (Array.isArray(res?.memory)) memoryList = res.memory; renderMemoryTab(); } catch (err) { safeNote('تعذر تقييم المعلومة: ' + (err.message || '')); } };
        const editBtn = el('button', '', 'as-item-mini-btn', { title: 'تعديل', type: 'button' }); editBtn.appendChild(createSvg('edit', 12));
        editBtn.onclick = () => { const editor = el('textarea', item.text, 'as-side-input'); editor.style.cssText = 'width:100%;min-height:64px;margin-top:6px'; const save = btn('حفظ', async () => { const text = editor.value.trim(); if (!text) return; try { const res = await api('/api/assistant/memory/update', { id: item.id, text }); if (Array.isArray(res?.memory)) memoryList = res.memory; else item.text = text; renderMemoryTab(); safeNote('تم تعديل المعلومة'); } catch (err) { safeNote('تعذر التعديل: ' + (err.message || '')); } }, 'btn pri'); card.append(editor, save); editor.focus(); };

        // زر الدبوس لتثبيت / إلغاء تثبيت
        const pinBtn = el('button', '', 'as-item-mini-btn pin-btn' + (item.pinned ? ' is-pinned' : ''), {
          title: item.pinned ? 'إلغاء التثبيت' : 'تثبيت (لا يمسّه المنظِّم)',
          type: 'button'
        });
        pinBtn.appendChild(createSvg(item.pinned ? 'pin-filled' : 'pin', 12));
        pinBtn.onclick = async () => {
          pinBtn.disabled = true;
          const targetPinned = !item.pinned;
          try {
            const res = await api('/api/assistant/memory/pin', { id: item.id, pinned: targetPinned });
            if (Array.isArray(res?.memory)) memoryList = res.memory;
            else item.pinned = targetPinned;
            renderMemoryTab();
            safeNote(targetPinned ? 'تم تثبيت المعلومة' : 'تم إلغاء التثبيت');
          } catch (err) {
            safeNote('تعذر تعديل التثبيت: ' + (err.message || ''));
          } finally {
            pinBtn.disabled = false;
          }
        };

        // زر الحذف
        const delBtn = el('button', '', 'as-item-mini-btn', {
          title: 'حذف هذه المعلومة',
          type: 'button'
        });
        delBtn.appendChild(createSvg('trash', 12));
        delBtn.onclick = async () => {
          delBtn.disabled = true;
          try {
            const res = await api('/api/assistant/memory/delete', { id: item.id });
            if (Array.isArray(res?.memory)) memoryList = res.memory;
            else memoryList = memoryList.filter(m => m.id !== item.id);
            renderMemoryTab();
            safeNote('تم حذف المعلومة');
          } catch (err) {
            safeNote('تعذر الحذف: ' + (err.message || ''));
          } finally {
            delBtn.disabled = false;
          }
        };

        actions.append(rateBtn, downBtn, editBtn, pinBtn, delBtn);
        topRow.append(badges, actions);

        const bodyTxt = el('div', item.text, 'as-card-body-text');
        card.append(topRow, bodyTxt);
        if (item.kind === 'decision' && item.reason) card.appendChild(el('div', 'السبب: ' + item.reason, 'as-card-meta'));
        cardList.appendChild(card);
      });

      secWrap.appendChild(cardList);
      listWrap.appendChild(secWrap);
    });
  }

  /* ==========================================================================
     12. تبويب «الأوامر الجاهزة»: قائمة، إضافة، تعديل، حذف، واستخدام فوري
     ========================================================================== */
  /* ==========================================================================
     مكتبة السكربتات: كل ما كتبه المساعد، بعناوين ووسوم، لإعادة تشغيله بنقرة بلا طلب جديد
     ========================================================================== */
  let scriptsList = [];
  let scriptsLoaded = false;
  let scriptsFilter = '';

  async function loadScripts() {
    try {
      const res = await api('/api/assistant/scripts');
      scriptsList = Array.isArray(res?.scripts) ? res.scripts : [];
      scriptsLoaded = true;
      renderScriptsTab();
    } catch (err) {
      scriptsLoaded = true;
      renderScriptsTab(err.message);
    }
  }

  function scriptAgo(t) {
    if (!t) return 'لم يُشغَّل بعد';
    const m = Math.round((Date.now() / 1000 - t) / 60);
    return m < 1 ? 'شُغّل الآن' : m < 60 ? 'آخر تشغيل قبل ' + m + ' دقيقة' : m < 1440 ? 'آخر تشغيل قبل ' + Math.round(m / 60) + ' ساعة' : 'آخر تشغيل قبل ' + Math.round(m / 1440) + ' يومًا';
  }

  async function showScriptRunModal(item) {
    let data;
    try {
      data = await api('/api/assistant/scripts/get?name=' + encodeURIComponent(item.name));
    } catch (err) {
      safeNote('تعذر فتح السكربت: ' + (err.message || ''));
      return;
    }
    const params = Array.isArray(data.params) ? data.params : [];
    const overlay = el('div', '', 'as-sm-overlay');
    const box = el('div', '', 'as-sm-box');
    const close = () => { overlay.remove(); document.removeEventListener('keydown', onKey, true); };
    const onKey = (ev) => { if (ev.key === 'Escape') { ev.stopPropagation(); close(); } };
    document.addEventListener('keydown', onKey, true);

    // الرأس
    const head = el('div', '', 'as-sm-head');
    const ico = el('div', '', 'as-sm-ico');
    ico.appendChild(createSvg('layers', 20));
    const titles = el('div', '', 'as-sm-titles');
    titles.append(el('b', data.title || data.name), el('small', (data.runs ? 'شُغّل ' + data.runs + ' مرة · ' : 'لم يُشغَّل من قبل · ') + scriptAgo(data.last_run), 'as-sm-sub'));
    const x = el('button', '', 'as-sm-x', { type: 'button', title: 'إغلاق (Esc)' });
    x.appendChild(createSvg('close', 14));
    x.onclick = close;
    head.append(ico, titles, x);
    box.appendChild(head);
    if (data.desc) box.appendChild(el('div', data.desc, 'as-sm-desc'));

    // نموذج المعطيات
    const inputs = {};
    const form = el('div', '', 'as-sm-form');
    const errEl = el('div', '', 'as-sm-err');
    errEl.hidden = true;
    const preview = el('div', '', 'as-sm-cmd');
    const valuesNow = () => {
      const v = {};
      params.forEach(p => { v[p.name] = (inputs[p.name] ? inputs[p.name].value : '').trim(); });
      return v;
    };
    const updatePreview = () => {
      const vals = params.length ? params.map(p => (valuesNow()[p.name] || p.default || '')) : [freeInp ? freeInp.value.trim() : ''];
      preview.textContent = '$ ' + data.name + ' ' + vals.filter((v, i, a) => v !== '' || i < a.length - 1).map(v => /[\s"']/.test(v) ? '"' + v.replace(/"/g, '\\"') + '"' : v).join(' ');
    };
    let freeInp = null;
    if (params.length) {
      params.forEach(p => {
        const row = el('label', '', 'as-sm-field');
        const lab = el('span', p.label + (p.required ? ' *' : ''), 'as-sm-lab');
        let inp;
        if (p.type === 'choice' && (p.options || []).length) {
          inp = el('input', '', '', { type: 'hidden' });
          inp.value = p.default || p.options[0];
          const seg = el('div', '', 'as-sm-seg');
          p.options.forEach(o => {
            const b = el('button', o, 'as-sm-seg-btn' + (inp.value === o ? ' on' : ''), { type: 'button' });
            b.onclick = () => { inp.value = o; seg.querySelectorAll('button').forEach(z => z.classList.toggle('on', z === b)); updatePreview(); };
            seg.appendChild(b);
          });
          row.append(lab, seg, inp);
        } else if (p.type === 'number') {
          inp = el('input', '', 'as-sm-inp', { type: 'number', inputmode: 'numeric', min: '0', placeholder: p.placeholder || '' });
          inp.value = p.default || '';
          const step = el('div', '', 'as-sm-step');
          const mk = (t, d) => { const b = el('button', t, '', { type: 'button' }); b.onclick = () => { inp.value = Math.max(0, (parseInt(inp.value || p.default || '0', 10) || 0) + d); updatePreview(); }; return b; };
          step.append(mk('−', -10), inp, mk('+', 10));
          row.append(lab, step);
        } else {
          inp = el('input', '', 'as-sm-inp' + (p.type === 'folder' ? ' ltr' : ''), { type: 'text', placeholder: p.placeholder || (p.type === 'folder' ? 'مسار المجلد' : '') });
          inp.value = p.default || '';
          if (p.type === 'folder') {
            const pick = btn('📁 اختر مجلدًا…', async () => {
              pick.disabled = true;
              try {
                const r = await api('/api/choose-folder', {});
                if (r && r.path) { inp.value = r.path.replace(/\/$/, ''); updatePreview(); }
              } catch (e) {
                safeNote('تعذر فتح نافذة اختيار المجلد: ' + (e.message || ''));
              } finally {
                pick.disabled = false;
              }
            }, 'btn');
            const wrap = el('div', '', 'as-sm-pickrow');
            wrap.append(inp, pick);
            row.append(lab, wrap);
          } else {
            row.append(lab, inp);
          }
        }
        inp.addEventListener('input', updatePreview);
        inp.addEventListener('keydown', ev => { if (ev.key === 'Enter') { ev.preventDefault(); go.click(); } });
        inputs[p.name] = inp;
        form.appendChild(row);
      });
    } else {
      const row = el('label', '', 'as-sm-field');
      freeInp = el('input', '', 'as-sm-inp', { type: 'text', placeholder: 'معطيات اختيارية (مفصولة بمسافات)' });
      freeInp.addEventListener('input', updatePreview);
      freeInp.addEventListener('keydown', ev => { if (ev.key === 'Enter') { ev.preventDefault(); go.click(); } });
      row.append(el('span', 'معطيات (اختياري)', 'as-sm-lab'), freeInp);
      form.appendChild(row);
    }
    box.append(form, errEl);

    // الأمان: التنبيهات والكود
    if (data.flags && data.flags.length) {
      const w = el('div', '', 'as-sm-warn');
      w.append(createSvg('shield-alert', 14), document.createTextNode(' يفعل: ' + data.flags.join('، ')));
      box.appendChild(w);
    }
    const det = document.createElement('details');
    det.className = 'as-sm-code';
    det.open = !data.runs || !!(data.flags && data.flags.length);
    const sum = document.createElement('summary');
    sum.textContent = 'نصّ الكود — يعمل بصلاحياتك الكاملة، فاقرأه قبل التشغيل';
    const pre = document.createElement('pre');
    pre.textContent = data.code || '';
    det.append(sum, pre);
    box.append(preview, det);
    updatePreview();

    const actions = el('div', '', 'as-sm-actions');
    const go = btn('', async () => {
      go.disabled = true;
      errEl.hidden = true;
      try {
        const payload = { name: data.name, sha: data.sha };
        if (params.length) payload.values = valuesNow(); else payload.args = freeInp ? freeInp.value.trim() : '';
        await api('/api/assistant/scripts/run', payload);
        close();
        safeNote('بدأ السكربت «' + (data.title || data.name) + '»؛ تابعه في لوحة العمليات');
        loadScripts();
      } catch (e) {
        errEl.textContent = e.message || 'تعذر التشغيل';
        errEl.hidden = false;
        go.disabled = false;
      }
    }, 'btn pri as-sm-go');
    go.append(createSvg('send', 14), document.createTextNode(' تشغيل الآن'));
    actions.append(go, btn('إلغاء', close, 'btn as-sm-cancel'));
    box.appendChild(actions);
    overlay.appendChild(box);
    overlay.addEventListener('mousedown', ev => { if (ev.target === overlay) close(); });
    panelEl.appendChild(overlay);
    const first = form.querySelector('input:not([type=hidden])');
    if (first) setTimeout(() => first.focus(), 50);
  }

  function showScriptEdit(item, card) {
    card.replaceChildren();
    const t = el('input', '', 'as-word-input', { placeholder: 'العنوان' });
    t.value = item.title || '';
    const d = el('input', '', 'as-word-input', { placeholder: 'الوصف' });
    d.value = item.desc || '';
    const g = el('input', '', 'as-word-input', { placeholder: 'وسوم مفصولة بفاصلة' });
    g.value = (item.tags || []).join('، ');
    [t, d, g].forEach(x => { x.style.marginBottom = '5px'; card.appendChild(x); });
    const row = el('div', '', 'as-pending-actions');
    row.append(btn('حفظ', async () => {
      try {
        const res = await api('/api/assistant/scripts/meta', { name: item.name, title: t.value, description: d.value, tags: g.value.split(/[,،]/).map(x => x.trim()).filter(Boolean) });
        scriptsList = res.scripts || scriptsList;
        renderScriptsTab();
      } catch (e) {
        safeNote('تعذر الحفظ: ' + (e.message || ''));
      }
    }, 'btn pri'), btn('إلغاء', () => renderScriptsTab(), 'btn'));
    card.appendChild(row);
  }

  function renderScriptsTab(errorMsg = '') {
    if (activeTab !== 'scripts' || !sideContentEl) return;
    sideContentEl.replaceChildren();
    const headRow = el('div', '', 'as-tab-head-row');
    headRow.append(el('span', 'مكتبة السكربتات', 'as-tab-head-title'), btn('', () => loadScripts(), 'btn', { title: 'تحديث' }));
    headRow.lastChild.appendChild(createSvg('refresh', 12));
    sideContentEl.appendChild(headRow);
    if (errorMsg) {
      sideContentEl.appendChild(el('div', 'تعذر جلب المكتبة: ' + errorMsg, 'as-card-err'));
      return;
    }
    const search = el('input', '', 'as-word-input', { placeholder: 'ابحث بالعنوان أو الوصف أو الوسم…' });
    search.value = scriptsFilter;
    search.style.marginBottom = '8px';
    sideContentEl.appendChild(search);
    const listWrap = el('div', '');
    listWrap.style.cssText = 'display:flex;flex-direction:column;gap:6px';
    sideContentEl.appendChild(listWrap);
    const draw = () => {
      listWrap.replaceChildren();
      const q = scriptsFilter.trim().toLowerCase();
      const rows = scriptsList.filter(x => !q || (x.title + ' ' + x.desc + ' ' + (x.tags || []).join(' ') + ' ' + x.name).toLowerCase().includes(q));
      if (!rows.length) {
        const n = el('div', scriptsList.length ? 'لا نتائج مطابقة.' : 'لا سكربتات بعد. حين يكتب المساعد سكربتًا لعمل كبير يُحفظ هنا بعنوانه فتعيد تشغيله بنقرة.', 'as-memory-hint');
        n.style.textAlign = 'center';
        listWrap.appendChild(n);
        return;
      }
      rows.forEach(item => {
        const card = el('div', '', 'as-prompt-card');
        const top = el('div', '', 'as-card-top-row');
        const ttl = el('b', item.title || item.name);
        ttl.style.cssText = 'font-size:12.5px;color:var(--acc)';
        const acts = el('div', '', 'as-chat-item-actions');
        const mk = (icon, tip, fn) => {
          const b = el('button', '', 'as-item-mini-btn', { title: tip, type: 'button' });
          b.appendChild(createSvg(icon, 12));
          b.onclick = e => { e.stopPropagation(); fn(); };
          return b;
        };
        acts.append(
          mk('edit', 'تعديل العنوان والوصف والوسوم', () => showScriptEdit(item, card)),
          mk('trash', 'حذف السكربت', async () => {
            if (!window.confirm('حذف السكربت «' + (item.title || item.name) + '» من المكتبة؟')) return;
            try {
              const res = await api('/api/assistant/scripts/delete', { name: item.name });
              scriptsList = res.scripts || [];
              draw();
            } catch (e) {
              safeNote('تعذر الحذف: ' + (e.message || ''));
            }
          })
        );
        top.append(ttl, acts);
        card.appendChild(top);
        card.appendChild(el('div', item.desc || '', 'as-memory-hint'));
        if ((item.tags || []).length) {
          const tg = el('div', '');
          tg.style.cssText = 'display:flex;flex-wrap:wrap;gap:4px;margin:4px 0';
          item.tags.forEach(x => {
            const c = el('span', x);
            c.style.cssText = 'font-size:10.5px;padding:1px 7px;border-radius:9px;background:rgba(127,127,127,.18);cursor:pointer';
            c.onclick = () => { scriptsFilter = x; search.value = x; draw(); };
            tg.appendChild(c);
          });
          card.appendChild(tg);
        }
        const st = item.last_state === 'done' ? ' ✓' : item.last_state === 'error' ? ' ✗' : item.last_state === 'running' ? ' ⏳' : '';
        card.appendChild(el('small', (item.runs ? 'شُغّل ' + item.runs + ' مرة · ' : '') + scriptAgo(item.last_run) + st, 'as-memory-hint'));
        const row = el('div', '', 'as-pending-actions');
        row.style.marginTop = '6px';
        row.append(
          btn('▶ تشغيل', () => showScriptRunModal(item), 'btn pri'),
          btn('في المحادثة', () => { fillInput('شغّل السكربت «' + (item.title || item.name) + '» (' + item.name + ')'); }, 'btn')
        );
        card.appendChild(row);
        listWrap.appendChild(card);
      });
    };
    search.oninput = () => { scriptsFilter = search.value; draw(); };
    draw();
  }

  async function loadPrompts() {
    try {
      const res = await api('/api/assistant/prompts');
      promptsList = Array.isArray(res?.prompts) ? res.prompts : [];
      promptsLoaded = true;
      renderPromptsTab();
    } catch (err) {
      promptsLoaded = true;
      renderPromptsTab(err.message);
    }
  }

  function renderPromptsTab(errorMsg = '') {
    if (activeTab !== 'prompts' || !sideContentEl) return;
    sideContentEl.replaceChildren();

    const headRow = el('div', '', 'as-tab-head-row');
    const title = el('span', 'الأوامر الجاهزة', 'as-tab-head-title');
    const newBtn = btn('', () => showPromptModal(), 'btn pri', {
      title: 'إضافة أمر جاهز جديد'
    });
    newBtn.style.padding = '3px 8px';
    newBtn.style.fontSize = '11px';
    newBtn.append(createSvg('plus', 12), document.createTextNode('أمر جديد'));
    headRow.append(title, newBtn);
    sideContentEl.appendChild(headRow);

    if (errorMsg) {
      sideContentEl.appendChild(el('div', 'تعذر جلب الأوامر: ' + errorMsg, 'as-card-err'));
      return;
    }

    const listWrap = el('div', '');
    listWrap.style.display = 'flex';
    listWrap.style.flexDirection = 'column';
    listWrap.style.gap = '6px';
    sideContentEl.appendChild(listWrap);

    if (promptsList.length === 0) {
      const emptyNote = el('div', 'لا توجد أوامر محفوظة بعد. انقر «+ أمر جديد» أو استخدم زر النجمة في مربع الإدخال.', 'as-memory-hint');
      emptyNote.style.textAlign = 'center';
      listWrap.appendChild(emptyNote);
      return;
    }

    promptsList.forEach(item => {
      const card = el('div', '', 'as-prompt-card', {
        title: 'انقر لوضع نص الأمر في مربع الإدخال'
      });

      const topRow = el('div', '', 'as-card-top-row');
      const pTitle = el('b', item.title || 'أمر جاهز');
      pTitle.style.fontSize = '12px';
      pTitle.style.color = 'var(--acc)';

      const actions = el('div', '', 'as-chat-item-actions');

      const editBtn = el('button', '', 'as-item-mini-btn edit-btn', {
        title: 'تعديل الأمر',
        type: 'button'
      });
      editBtn.appendChild(createSvg('edit', 12));
      editBtn.onclick = (e) => {
        e.stopPropagation();
        showPromptModal(item);
      };

      const delBtn = el('button', '', 'as-item-mini-btn', {
        title: 'حذف الأمر',
        type: 'button'
      });
      delBtn.appendChild(createSvg('trash', 12));
      delBtn.onclick = async (e) => {
        e.stopPropagation();
        if (!window.confirm('هل أنت متأكد من حذف هذا الأمر؟')) return;
        try {
          const res = await api('/api/assistant/prompts/delete', { id: item.id });
          if (res?.prompts) promptsList = res.prompts;
          else promptsList = promptsList.filter(p => p.id !== item.id);
          renderPromptsTab();
          safeNote('تم حذف الأمر الجاهز');
        } catch (err) {
          safeNote('تعذر حذف الأمر: ' + (err.message || ''));
        }
      };

      actions.append(editBtn, delBtn);
      topRow.append(pTitle, actions);

      const bodyTxt = el('div', item.text, 'as-card-body-text');
      bodyTxt.style.color = 'var(--ink)';

      card.append(topRow, bodyTxt);

      // النقر يضع النص في مربع الإدخال الرئيسي ولا يرسل
      card.onclick = () => {
        fillInput(item.text);
        if (window.innerWidth < 600) {
          toggleSidebar(false);
        }
      };

      listWrap.appendChild(card);
    });
  }

  function showPromptModal(existing = null) {
    const titleVal = window.prompt('عنوان الأمر الجاهز:', existing ? existing.title : '');
    if (titleVal === null) return;
    const cleanTitle = titleVal.trim();
    if (!cleanTitle) {
      safeNote('يجب تحديد عنوان للأمر');
      return;
    }

    const textVal = window.prompt('نص الأمر:', existing ? existing.text : (inputEl ? inputEl.value : ''));
    if (textVal === null) return;
    const cleanText = textVal.trim();
    if (!cleanText) {
      safeNote('يجب تحديد نص للأمر');
      return;
    }

    const payload = { title: cleanTitle, text: cleanText };
    if (existing?.id) payload.id = existing.id;

    api('/api/assistant/prompts/save', payload)
      .then(res => {
        if (res?.prompts) promptsList = res.prompts;
        else loadPrompts();
        renderPromptsTab();
        safeNote('تم حفظ الأمر الجاهز بنجاح');
      })
      .catch(err => {
        safeNote('تعذر حفظ الأمر: ' + (err.message || ''));
      });
  }

  /* ==========================================================================
     13. تبويب «الأتمتة»: قواعد المراقبة والنقل، الإشعارات، والشارات
     ========================================================================== */
  function formatRuleDescription(rule) {
    const parts = [];
    const ev = Number(rule?.every) || 20;
    parts.push('كل ' + ev + ' دقيقة');

    const w = rule?.watch || {};
    const watchTarget = w.path || w.place || 'المجلد';
    parts.push('مراقبة: ' + watchTarget);

    const actions = Array.isArray(rule?.actions) ? rule.actions : [];
    if (actions.length > 0) {
      const actParts = actions.map(act => {
        const dest = act.to_path || act.to_place || '';
        if (act.type === 'move') {
          return dest ? 'نقل إلى ' + dest : 'نقل';
        } else if (act.type === 'copy') {
          return dest ? 'نسخ إلى ' + dest : 'نسخ';
        } else if (act.type === 'notify') {
          return 'إشعار';
        }
        return act.type || 'إجراء';
      });
      parts.push(actParts.join('، '));
    }
    return parts.join(' · ');
  }

  function formatFutureRelativeTime(unixSeconds) {
    if (!unixSeconds || unixSeconds <= 0) return '—';
    const now = Math.floor(Date.now() / 1000);
    const diff = Math.floor(unixSeconds - now);
    if (diff <= 5) return 'الآن';
    if (diff < 60) return 'بعد لحظات';
    const mins = Math.floor(diff / 60);
    if (mins < 60) return 'بعد ' + mins + ' دقيقة';
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return 'بعد ' + hrs + ' ساعة';
    const days = Math.floor(hrs / 24);
    return 'بعد ' + days + ' يوم';
  }

  function startAutomationsPolling() {
    stopAutomationsPolling();
    automationsPollTimer = setInterval(() => {
      if ((isOpen && isSidebarOpen || activeWindow === 'control' && controlPanelEl && !controlPanelEl.hidden) && activeTab === 'automations') {
        loadAutomations(true);
      } else {
        stopAutomationsPolling();
      }
    }, 30000);
  }

  function stopAutomationsPolling() {
    if (automationsPollTimer) {
      clearInterval(automationsPollTimer);
      automationsPollTimer = null;
    }
  }

  function updateUnreadNoticesBadge(count) {
    unreadNoticesCount = Math.max(0, count || 0);
    updateFloatingBadgeState();
    updateAutomationsTabBadge();
  }

  function updateAutomationsTabBadge() {
    [automationsTabBadge, controlAutomationBadge].forEach(badge => {
      if (!badge) return;
      if (unreadNoticesCount > 0) { badge.textContent = unreadNoticesCount > 99 ? '99+' : String(unreadNoticesCount); badge.hidden = false; }
      else badge.hidden = true;
    });
    if (controlChipEl) controlChipEl.classList.toggle('as-alert', unreadNoticesCount > 0);
  }

  async function checkAutomationsNoticeBadge() {
    try {
      const res = await api('/api/assistant/automations');
      if (res && Array.isArray(res.notices)) {
        const unread = res.notices.filter(n => !n.read).length;
        updateUnreadNoticesBadge(unread);
      }
    } catch (_) {
      // استعلام خفيف لا يتسبب في أخطاء إن فشل
    }
  }

  async function loadAutomations(silent = false) {
    if (!silent && sideContentEl && activeTab === 'automations') {
      if (!automationsLoaded) {
        sideContentEl.replaceChildren();
        const loadingBox = el('div', 'جارٍ تحميل قواعد الأتمتة والإشعارات…', 'as-card-body-text');
        loadingBox.style.padding = '16px';
        loadingBox.style.textAlign = 'center';
        loadingBox.style.color = 'var(--mut)';
        sideContentEl.appendChild(loadingBox);
      }
    }
    try {
      const res = await api('/api/assistant/automations');
      automationsRules = Array.isArray(res?.rules) ? res.rules : [];
      automationsNotices = Array.isArray(res?.notices) ? res.notices : [];
      automationsLoaded = true;
      const unread = automationsNotices.filter(n => !n.read).length;
      updateUnreadNoticesBadge(unread);
      if (activeTab === 'automations') {
        renderAutomationsTab();
      }
      if (isOpen && isSidebarOpen && activeTab === 'automations') {
        startAutomationsPolling();
      }
    } catch (err) {
      automationsLoaded = true;
      if (activeTab === 'automations') {
        renderAutomationsTab(err.message || 'تعذر جلب الأتمتة');
      }
    }
  }

  function renderAutomationsTab(errorMsg = '') {
    if (activeTab !== 'automations' || !sideContentEl) return;
    sideContentEl.replaceChildren();

    // ١) ترويسة التبويب
    const headRow = el('div', '', 'as-tab-head-row');
    const title = el('span', 'الأتمتة والمراقبة', 'as-tab-head-title');
    const refreshBtn = btn('', () => loadAutomations(), 'btn', {
      title: 'تحديث فوري'
    });
    refreshBtn.style.padding = '3px 8px';
    refreshBtn.style.fontSize = '11px';
    refreshBtn.append(createSvg('refresh', 12), document.createTextNode(' تحديث'));
    headRow.append(title, refreshBtn);
    sideContentEl.appendChild(headRow);

    if (errorMsg) {
      sideContentEl.appendChild(el('div', 'تعذر جلب الأتمتة: ' + errorMsg, 'as-card-err'));
      return;
    }

    // ٢) قسم «القواعد»
    const rulesSec = el('div', '');
    rulesSec.style.display = 'flex';
    rulesSec.style.flexDirection = 'column';
    rulesSec.style.gap = '8px';

    const rulesHead = el('div', '', 'as-ctrl-row');
    rulesHead.style.marginBottom = '2px';
    const rulesTitle = el('span', 'القواعد النشطة (' + automationsRules.length + ')', 'as-ctrl-lbl');
    rulesTitle.style.fontWeight = '600';
    rulesHead.appendChild(rulesTitle);
    rulesSec.appendChild(rulesHead);

    if (automationsRules.length === 0) {
      // حالة فارغة مفيدة
      const emptyBox = el('div', '', 'as-automation-card');
      emptyBox.style.padding = '14px 12px';
      emptyBox.style.textAlign = 'center';
      emptyBox.style.gap = '10px';

      const emptyText = el('div', 'لا قواعد بعد. اطلب من المساعد مثلًا: راقب مجلد التنزيلات كل 20 دقيقة وانقل المجلدات الجديدة إلى …', 'as-card-body-text');
      emptyText.style.color = 'var(--mut)';
      emptyText.style.lineHeight = '1.6';

      const exampleText = 'راقب مجلد التنزيلات كل 20 دقيقة وانقل المجلدات الجديدة إلى …';
      const useExBtn = btn('', () => {
        fillInput(exampleText);
        if (window.innerWidth < 600) {
          toggleSidebar(false);
        }
      }, 'btn pri');
      useExBtn.style.alignSelf = 'center';
      useExBtn.style.padding = '5px 12px';
      useExBtn.append(createSvg('spark', 13), document.createTextNode(' كتابة هذا الأمر في الإدخال'));

      emptyBox.append(emptyText, useExBtn);
      rulesSec.appendChild(emptyBox);
    } else {
      automationsRules.forEach(rule => {
        const card = el('div', '', 'as-automation-card' + (rule.enabled ? '' : ' is-disabled'));

        // الرأس: الاسم + المفتاح
        const head = el('div', '', 'as-auto-head');
        const name = el('span', rule.name || 'قاعدة بدون اسم', 'as-auto-name');
        name.title = rule.name || '';

        // مفتاح تشغيل/إيقاف
        const toggleLabel = el('label', '', 'as-toggle-label');
        if (rule.enabled) toggleLabel.classList.add('is-active');

        const toggleNative = el('input', '', 'as-switch-native', { type: 'checkbox' });
        toggleNative.checked = !!rule.enabled;

        const switchTrack = el('span', '', 'as-switch-track');
        const switchThumb = el('span', '', 'as-switch-thumb');
        switchTrack.appendChild(switchThumb);

        toggleNative.onchange = async () => {
          const targetVal = toggleNative.checked;
          toggleNative.disabled = true;
          try {
            await api('/api/assistant/automations/toggle', { id: rule.id, enabled: targetVal });
            rule.enabled = targetVal;
            toggleLabel.classList.toggle('is-active', targetVal);
            card.classList.toggle('is-disabled', !targetVal);
            safeNote(targetVal ? 'تم تفعيل القاعدة: ' + rule.name : 'تم إيقاف القاعدة: ' + rule.name);
            renderAutomationsTab();
          } catch (err) {
            toggleNative.checked = !targetVal;
            toggleLabel.classList.toggle('is-active', toggleNative.checked);
            safeNote('تعذر تعديل حالة القاعدة: ' + (err.message || ''));
          } finally {
            toggleNative.disabled = false;
          }
        };

        toggleLabel.append(toggleNative, switchTrack);
        head.append(name, toggleLabel);

        // سطر الوصف بالعربية
        const descRow = el('div', formatRuleDescription(rule), 'as-auto-desc');

        // صندوق البيانات: موعد الفحص القادم + آخر ما وجدت
        const metaBox = el('div', '', 'as-auto-meta');

        const nextRow = el('div', '', 'as-auto-meta-row');
        const nextLbl = el('span', 'الفحص القادم:', 'as-auto-meta-label');
        const nextValText = !rule.enabled ? 'معطّلة حالياً' : formatFutureRelativeTime(rule.next_run);
        const nextVal = el('span', nextValText, 'as-auto-meta-val');
        nextRow.append(nextLbl, nextVal);

        const noteRow = el('div', '', 'as-auto-meta-row');
        const noteLbl = el('span', 'آخر فحص:', 'as-auto-meta-label');
        const noteVal = el('span', rule.last_note || 'لم تسجل ملاحظة بعد', 'as-auto-note');
        noteRow.append(noteLbl, noteVal);

        metaBox.append(nextRow, noteRow);

        // شريط الأزرار: افحص الآن + حذف بتأكيد مرتين داخل البطاقة
        const actions = el('div', '', 'as-auto-actions');

        const runBtn = btn('', async () => {
          runBtn.disabled = true;
          runBtn.textContent = 'جارٍ الفحص…';
          try {
            const res = await api('/api/assistant/automations/run', { id: rule.id });
            const noteText = res?.note || 'تم الفحص بنجاح';
            safeNote(noteText);
            await loadAutomations(true);
          } catch (err) {
            safeNote('تعذر فحص القاعدة: ' + (err.message || ''));
          } finally {
            runBtn.disabled = false;
            runBtn.replaceChildren(createSvg('refresh', 12), document.createTextNode(' افحص الآن'));
          }
        }, 'btn');
        runBtn.append(createSvg('refresh', 12), document.createTextNode(' افحص الآن'));

        let deleteConfirmTimer = null;
        let isConfirmingDelete = false;

        const delBtn = btn('', async () => {
          if (!isConfirmingDelete) {
            isConfirmingDelete = true;
            delBtn.classList.add('as-btn-danger-confirm');
            delBtn.replaceChildren(createSvg('trash', 12), document.createTextNode(' تأكيد الحذف؟'));
            deleteConfirmTimer = setTimeout(() => {
              isConfirmingDelete = false;
              delBtn.classList.remove('as-btn-danger-confirm');
              delBtn.replaceChildren(createSvg('trash', 12), document.createTextNode(' حذف'));
            }, 4000);
          } else {
            clearTimeout(deleteConfirmTimer);
            delBtn.disabled = true;
            delBtn.textContent = 'جارٍ الحذف…';
            try {
              await api('/api/assistant/automations/delete', { id: rule.id });
              safeNote('تم حذف القاعدة بنجاح');
              await loadAutomations(true);
            } catch (err) {
              delBtn.disabled = false;
              delBtn.replaceChildren(createSvg('trash', 12), document.createTextNode(' حذف'));
              safeNote('تعذر حذف القاعدة: ' + (err.message || ''));
            }
          }
        }, 'btn');
        delBtn.style.color = 'var(--err)';
        delBtn.append(createSvg('trash', 12), document.createTextNode(' حذف'));

        actions.append(runBtn, delBtn);

        card.append(head, descRow, metaBox, actions);
        rulesSec.appendChild(card);
      });
    }

    sideContentEl.appendChild(rulesSec);

    // ٣) قسم «الإشعارات»
    const noticesSec = el('div', '', 'as-notices-section');

    const noticesHead = el('div', '', 'as-ctrl-row');
    noticesHead.style.justifyContent = 'space-between';
    const noticesTitle = el('span', 'الإشعارات (' + automationsNotices.length + ')', 'as-ctrl-lbl');
    noticesTitle.style.fontWeight = '600';

    const unreadCount = automationsNotices.filter(n => !n.read).length;
    const markReadBtn = btn('', async () => {
      markReadBtn.disabled = true;
      try {
        await api('/api/assistant/notices/read', {});
        automationsNotices.forEach(n => { n.read = true; });
        updateUnreadNoticesBadge(0);
        renderAutomationsTab();
        safeNote('تم تعليم جميع الإشعارات كمقروءة');
      } catch (err) {
        safeNote('تعذر تعليم الإشعارات: ' + (err.message || ''));
      } finally {
        markReadBtn.disabled = false;
      }
    }, 'btn');
    markReadBtn.style.fontSize = '11px';
    markReadBtn.style.padding = '2px 8px';
    markReadBtn.append(createSvg('check', 12), document.createTextNode(' تعليم الكل كمقروء'));
    if (unreadCount === 0) {
      markReadBtn.style.opacity = '0.6';
    }

    noticesHead.append(noticesTitle, markReadBtn);
    noticesSec.appendChild(noticesHead);

    if (automationsNotices.length === 0) {
      const emptyNotices = el('div', 'لا توجد إشعارات حتى الآن.', 'as-card-body-text');
      emptyNotices.style.color = 'var(--mut)';
      emptyNotices.style.padding = '8px 4px';
      noticesSec.appendChild(emptyNotices);
    } else {
      const noticesList = el('div', '');
      noticesList.style.display = 'flex';
      noticesList.style.flexDirection = 'column';
      noticesList.style.gap = '6px';

      automationsNotices.forEach(nt => {
        const nCard = el('div', '', 'as-notice-card' + (nt.read ? '' : ' is-unread'));

        const nHead = el('div', '', 'as-notice-head');
        const ruleName = el('span', nt.rule || 'تنبيه أتمتة', 'as-notice-rule');
        const timeSpan = el('span', formatRelativeTime(nt.t));
        nHead.append(ruleName, timeSpan);

        const nBody = el('div', nt.text || '', 'as-notice-body');

        nCard.append(nHead, nBody);
        noticesList.appendChild(nCard);
      });

      noticesSec.appendChild(noticesList);
    }

    sideContentEl.appendChild(noticesSec);
  }

  /* ==========================================================================
     بطاقة الهاتف اللاسلكي أعلى تبويب الإعدادات
     ========================================================================== */
  async function renderPhoneCard(container) {
    const card = el('div', '', 'as-phone-card');

    // رأس البطاقة: أيقونة + عنوان + سطر العنوان الحالي + شارة الحالة
    const head = el('div', '', 'as-phone-head');
    const ico = el('div', '', 'as-phone-ico');
    ico.appendChild(createSvg('smartphone', 20));
    const titles = el('div', '', 'as-phone-titles');
    const titleRow = el('div', 'الهاتف اللاسلكي', 'as-phone-title-row');
    const subEl = el('div', 'جارٍ التحقق…', 'as-phone-sub');
    titles.append(titleRow, subEl);
    const statusBadge = el('span', 'جارٍ التحقق…', 'as-phone-status-badge is-disconnected');
    head.append(ico, titles, statusBadge);

    // بطاقتان صغيرتان: العنوان المحفوظ وآخر ملاحظة
    const infoGrid = el('div', '', 'as-phone-info-grid');
    const savedIpRow = el('div', '', 'as-phone-info-row');
    savedIpRow.append(el('span', 'العنوان المحفوظ', 'as-phone-info-lbl'), el('span', '—', 'as-phone-info-val'));
    const noteRow = el('div', '', 'as-phone-info-row');
    noteRow.append(el('span', 'آخر ملاحظة', 'as-phone-info-lbl'), el('span', '—', 'as-phone-info-val'));
    infoGrid.append(savedIpRow, noteRow);

    // الأزرار
    const actionsRow = el('div', '', 'as-phone-actions');
    const connectBtn = btn('', null, 'btn pri');
    connectBtn.append(createSvg('refresh', 14), document.createTextNode(' اتصل بالهاتف الآن'));
    const pairToggleBtn = btn('', null, 'btn');
    pairToggleBtn.append(createSvg('swap', 14), document.createTextNode(' اقتران جديد (مرة واحدة)'));
    actionsRow.append(connectBtn, pairToggleBtn);

    // قسم الاقتران (مخفي افتراضيًا): خطوات مرقمة ثم الحقلان متراصّان
    const pairBox = el('div', '', 'as-phone-pair-box');
    pairBox.hidden = true;
    const guideText = el('ol', '', 'as-phone-steps');
    ['في الهاتف: الإعدادات ← خيارات المطور ← التصحيح اللاسلكي.',
     'اختر «الاقتران برمز الاقتران» فيظهر عنوان ورمز من ست خانات.',
     'اكتبهما هنا ثم اضغط إتمام الاقتران (مرة واحدة فقط، بعدها يتصل تلقائيًا).'].forEach(t => guideText.appendChild(el('li', t)));

    const inputsRow = el('div', '', 'as-phone-inputs-row');
    const addrInp = el('input', '', 'as-phone-inp', {
      type: 'text',
      inputmode: 'decimal',
      placeholder: 'عنوان الاقتران، مثل 192.168.1.20:37099',
      title: 'عنوان الاقتران والمنفذ الظاهر في نافذة الهاتف'
    });
    const codeInp = el('input', '', 'as-phone-inp as-phone-code', {
      type: 'text',
      inputmode: 'numeric',
      autocomplete: 'off',
      placeholder: '------',
      maxlength: '6',
      title: 'رمز الاقتران المكون من ستة أرقام'
    });
    inputsRow.append(addrInp, codeInp);

    const pairSubmitBtn = btn('', null, 'btn pri as-phone-submit');
    pairSubmitBtn.append(createSvg('check', 14), document.createTextNode(' إتمام الاقتران والاتصال'));

    const pairMsg = el('div', '', 'as-card-body-text');
    pairMsg.style.fontSize = '11.5px';

    pairBox.append(guideText, inputsRow, pairSubmitBtn, pairMsg);

    card.append(head, infoGrid, actionsRow, pairBox);
    container.appendChild(card);

    // دالة تحديث بيانات البطاقة
    async function updatePhoneData() {
      try {
        const data = await api('/api/assistant/phone');
        if (!data) return;

        let stateText = 'غير متصل';
        let isConn = false;
        let detailText = '';

        if (data.wireless) {
          stateText = 'متصل لاسلكيًا';
          isConn = true;
          detailText = data.wireless;
        } else if (data.usb && data.usb.length > 0) {
          stateText = 'متصل بالكابل (USB)';
          isConn = true;
          detailText = data.usb[0];
        } else if (data.connected) {
          stateText = 'متصل';
          isConn = true;
        }

        statusBadge.textContent = stateText;
        subEl.textContent = detailText || (isConn ? '' : 'لا جهاز متصل الآن');
        statusBadge.className = 'as-phone-status-badge ' + (isConn ? 'is-connected' : 'is-disconnected');

        const ipVal = savedIpRow.children[1];
        if (ipVal) {
          ipVal.textContent = data.saved_ip || data.saved_serial || 'لا يوجد';
        }

        const nVal = noteRow.children[1];
        if (nVal) {
          nVal.textContent = data.last_note || '—';
        }
      } catch (err) {
        statusBadge.textContent = 'تعذر الجلب';
        subEl.textContent = '';
        statusBadge.className = 'as-phone-status-badge is-disconnected';
      }
    }

    // ربط الأحداث
    connectBtn.onclick = async () => {
      connectBtn.disabled = true;
      connectBtn.textContent = 'جارٍ الاتصال…';
      try {
        const res = await api('/api/assistant/phone', {});
        safeNote('تم الاتصال بالهاتف بنجاح: ' + (res?.connected || ''));
        await updatePhoneData();
      } catch (err) {
        safeNote('تعذر الاتصال بالهاتف: ' + (err.message || ''));
      } finally {
        connectBtn.disabled = false;
        connectBtn.replaceChildren(createSvg('refresh', 14), document.createTextNode(' اتصل بالهاتف الآن'));
      }
    };

    pairToggleBtn.onclick = () => {
      pairBox.hidden = !pairBox.hidden;
      if (!pairBox.hidden) {
        pairMsg.textContent = '';
        addrInp.focus();
      }
    };

    pairSubmitBtn.onclick = async () => {
      const pAddr = addrInp.value.trim();
      const pCode = codeInp.value.trim();
      if (!pAddr || !pCode) {
        pairMsg.style.color = 'var(--err)';
        pairMsg.textContent = 'يجب كتابة عنوان الاقتران والرمز المكون من 6 أرقام.';
        return;
      }
      pairSubmitBtn.disabled = true;
      pairSubmitBtn.textContent = 'جارٍ الاقتران…';
      pairMsg.textContent = '';
      try {
        const res = await api('/api/assistant/phone', { pair_addr: pAddr, pair_code: pCode });
        codeInp.value = ''; // تفريغ الرمز فوراً لعدم تخزينه
        pairMsg.style.color = 'var(--ok)';
        pairMsg.textContent = 'تم الاقتران والاتصال بنجاح!';
        safeNote('تم اقتران الهاتف واتصاله بنجاح: ' + (res?.connected || ''));
        pairBox.hidden = true;
        await updatePhoneData();
      } catch (err) {
        codeInp.value = ''; // تفريغ الرمز فوراً حتى عند الخطأ
        pairMsg.style.color = 'var(--err)';
        pairMsg.textContent = 'فشل الاقتران: ' + (err.message || 'تأكد من الرمز والعنوان');
        safeNote('فشل اقتران الهاتف: ' + (err.message || ''));
      } finally {
        pairSubmitBtn.disabled = false;
        pairSubmitBtn.replaceChildren(createSvg('check', 14), document.createTextNode(' إتمام الاقتران والاتصال'));
      }
    };

    // جلب أولي
    updatePhoneData();
  }

  /* ==========================================================================
     14. تبويب «الإعدادات»: الهاتف اللاسلكي، الحالة، العمليات، أوقف الكل، والوكلاء والنماذج
     ========================================================================= */
  async function loadAgents() {
    try {
      const data = await api('/api/assistant/agents');
      if (data?.settings) {
        currentSettings = data.settings;
      }
      agentsList = Array.isArray(data?.agents) ? data.agents : [];

      const defId = currentSettings?.default_agent || agentsList.find(a => a.default)?.id || 'agy';
      if (!activeAgentId) {
        activeAgentId = defId;
      }
      const curAg = agentsList.find(a => a.id === activeAgentId) || agentsList.find(a => a.id === defId) || agentsList[0];
      if (curAg) {
        activeAgentId = curAg.id;
        activeModel = curAg.model || '';
      }

      updateSourceBadge();
      if (activeTab === 'settings') {
        renderSettingsTab();
      }
    } catch (err) {
      safeNote('تعذر تحميل إعدادات المساعد: ' + (err.message || ''));
    }
  }

  async function refreshModelsList(btnEl, statusEl) {
    if (btnEl) btnEl.disabled = true;
    if (statusEl) {
      statusEl.textContent = 'جارٍ استقدام أحدث قوائم النماذج من الوكلاء…';
    }
    try {
      const res = await api('/api/assistant/models/refresh', {});
      if (res?.agents) {
        agentsList = res.agents;
      } else {
        await loadAgents();
      }

      const results = res?.result || {};
      const summary = [];
      for (const [aid, info] of Object.entries(results)) {
        const ag = agentsList.find(x => x.id === aid);
        const name = ag ? ag.name : aid;
        if (info.ok) {
          summary.push(name + ': ' + info.count + ' نموذج');
        } else {
          summary.push(name + ': (' + (info.error || 'فشل') + ')');
        }
      }

      if (statusEl) {
        statusEl.textContent = 'اكتمل التحديث: ' + summary.join(' | ');
      }
      renderSettingsTab();
      updateSourceBadge();
    } catch (err) {
      if (statusEl) {
        statusEl.textContent = 'تعذر تحديث النماذج: ' + (err.message || 'خطأ');
      }
    } finally {
      if (btnEl) btnEl.disabled = false;
    }
  }

  function renderSettingsTab() {
    if (activeTab !== 'settings' || !sideContentEl) return;
    sideContentEl.replaceChildren();

    // تحديث البرنامج والمزامنة الشخصية
    const makeSettingsCard = (title, description) => {
      const card = el('section', '', 'as-agent-card');
      card.style.cssText = 'margin-bottom:8px;padding:10px;border:1px solid var(--line);border-radius:10px;background:var(--panel);color:var(--ink)';
      const heading = el('div', title, 'as-agent-name');
      const desc = el('div', description, 'as-memory-desc');
      desc.style.cssText = 'margin:5px 0;color:var(--muted)';
      const status = el('div', 'جارٍ التحميل…', 'as-memory-desc');
      status.style.cssText = 'margin:5px 0;color:var(--muted);overflow-wrap:anywhere';
      const actions = el('div', '');
      actions.style.cssText = 'display:flex;gap:6px;flex-wrap:wrap;margin-top:7px';
      card.append(heading, desc, status, actions);
      return { card, status, actions };
    };
    const updateCard = makeSettingsCard('تحديث البرنامج', 'الإصدار الحالي: جارٍ التحقق…');
    const updateDesc = updateCard.card.children[1];
    const checkUpdateBtn = btn('تحقق من التحديثات', async () => {
      checkUpdateBtn.disabled = true;
      updateCard.status.textContent = 'جارٍ التحقق…';
      try {
        const result = await api('/api/assistant/app/update/check');
        updateDesc.textContent = 'الإصدار الحالي: ' + (result.current || '—');
        updateCard.status.textContent = result.error || (result.available ? 'يتوفر إصدار ' + (result.latest || '—') : 'البرنامج محدّث.');
        applyBtn.hidden = !result.available || !!result.error;
      } catch (err) {
        updateCard.status.textContent = err.message || 'تعذر التحقق من التحديثات.';
        applyBtn.hidden = true;
      } finally { checkUpdateBtn.disabled = false; }
    }, 'btn');
    const applyBtn = btn('حدّث الآن', async () => {
      if (!window.confirm('هل تريد تحديث البرنامج الآن؟')) return;
      applyBtn.disabled = true;
      checkUpdateBtn.disabled = true;
      updateCard.status.textContent = 'جارٍ التحديث…';
      try {
        const result = await api('/api/assistant/app/update/apply', {});
        if (!result.ok) throw new Error(result.error || 'تعذر تطبيق التحديث.');
        const deadline = Date.now() + 60000;
        while (Date.now() < deadline) {
          await new Promise(resolve => setTimeout(resolve, 1500));
          try {
            await api('/api/health');
            location.reload();
            return;
          } catch (_) { /* ينتظر عودة الخادم بعد إعادة التشغيل */ }
        }
        throw new Error('لم يعد الخادم خلال دقيقة. أعد تحميل الصفحة لاحقًا.');
      } catch (err) {
        updateCard.status.textContent = err.message || 'تعذر تطبيق التحديث.';
        applyBtn.disabled = false;
        checkUpdateBtn.disabled = false;
      }
    }, 'btn pri');
    applyBtn.hidden = true;
    updateCard.actions.append(checkUpdateBtn, applyBtn);
    sideContentEl.appendChild(updateCard.card);

    const syncCard = makeSettingsCard('المزامنة مع الكمبيوتر الآخر', 'تُزامَن الإعدادات والتوجيهات وذاكرة المساعد عبر مخزن خاص. لا يُرسل شيء حتى تضغط زر المزامنة.');
    const syncBtn = btn('زامن الآن', async () => {
      syncBtn.disabled = true;
      syncCard.status.textContent = 'جارٍ تنفيذ المزامنة…';
      try {
        const result = await api('/api/assistant/sync/run', {});
        if (!result.ok) throw new Error(result.msg || result.error || 'تعذرت المزامنة.');
        syncCard.status.textContent = `أُضيف ${Number(result.memory_added || 0).toLocaleString('ar')} وتحدّث ${Number(result.memory_updated || 0).toLocaleString('ar')} وحُذف ${Number(result.memory_removed || 0).toLocaleString('ar')} في الذاكرة`;
        if (typeof loadMemory === 'function') loadMemory(true);
        await loadSyncStatus();
      } catch (err) {
        syncCard.status.textContent = err.message || 'تعذرت المزامنة.';
      } finally { syncBtn.disabled = false; }
    }, 'btn pri');
    syncCard.actions.appendChild(syncBtn);
    sideContentEl.appendChild(syncCard.card);
    async function loadSyncStatus() {
      try {
        const status = await api('/api/assistant/sync/status');
        const when = Number(status.last) > 0 ? agentRelativeTime(Number(status.last) * 1000) : 'لا توجد مزامنة سابقة';
        syncCard.status.textContent = `آخر مزامنة: ${when}${status.last_msg ? ' · ' + status.last_msg : ''}`;
        syncBtn.disabled = !status.gh_ready;      // أول مزامنة هي التي تجهّز المستودع، فلا يُشترط أن تكون قد تمّت قبلًا
        if (!status.gh_ready && !syncCard.actions.querySelector('code')) {
          const code = el('code', 'gh auth login');
          code.style.cssText = 'display:inline-block;padding:4px 7px;border-radius:5px;background:var(--side);color:var(--ink);cursor:pointer;user-select:all';
          code.title = 'اضغط لنسخ الأمر';
          code.onclick = async () => { try { await navigator.clipboard.writeText('gh auth login'); } catch (_) {} };
          syncCard.actions.prepend(el('span', 'سجّل الدخول إلى GitHub في الطرفية أولًا: '));
          syncCard.actions.prepend(code);
        }
      } catch (err) { syncCard.status.textContent = err.message || 'تعذر جلب حالة المزامنة.'; }
    }
    loadSyncStatus();
    checkUpdateBtn.click();

    const telegramCard = makeSettingsCard('الوصل مع Telegram', 'أرسل أوامر المساعد إلى بوت Telegram وتابع إشعاراته.');
    telegramCard.status.textContent = 'جارٍ تحميل حالة Telegram…';
    const telegramBody = el('div', '');
    telegramBody.style.cssText = 'display:flex;flex-direction:column;gap:7px;margin-top:7px';
    telegramCard.card.appendChild(telegramBody);
    sideContentEl.appendChild(telegramCard.card);
    let telegramPoll = null;
    let telegramStatus = null;
    const telegramError = (err) => { telegramCard.status.textContent = err && err.message ? err.message : 'تعذر تنفيذ طلب Telegram.'; };
    const telegramButton = (label, action, className = 'btn') => btn(label, async (event) => {
      const button = event && event.currentTarget;
      if (button) button.disabled = true;
      try { await action(); } catch (err) { telegramError(err); }
      finally { if (button && button.isConnected) button.disabled = false; }
    }, className);
    const telegramToggle = (label, key, value, onChange) => {
      const row = el('label', '');
      row.style.cssText = 'display:flex;align-items:center;gap:7px';
      const input = document.createElement('input');
      input.type = 'checkbox'; input.checked = !!value;
      input.addEventListener('change', async () => {
        input.disabled = true;
        try { const next = await api('/api/assistant/telegram/configure', { [key]: input.checked }); onChange(next); }
        catch (err) { input.checked = !input.checked; telegramError(err); }
        finally { input.disabled = false; }
      });
      row.append(input, document.createTextNode(label));
      return row;
    };
    const renderTelegram = (status) => {
      telegramStatus = status || {};
      telegramBody.replaceChildren();
      if (telegramStatus.has_token && telegramStatus.paired && telegramPoll) { clearInterval(telegramPoll); telegramPoll = null; }
      if (!telegramStatus.has_token) {
        telegramBody.appendChild(el('div', '١. افتح @BotFather في Telegram.'));
        telegramBody.appendChild(el('div', '٢. أرسل /newbot واتبع التعليمات.'));
        telegramBody.appendChild(el('div', '٣. انسخ رمز البوت والصقه هنا.'));
        const input = document.createElement('input');
        input.type = 'password'; input.autocomplete = 'new-password'; input.placeholder = 'رمز البوت';
        input.style.cssText = 'width:100%;box-sizing:border-box;padding:7px;border:1px solid var(--line);border-radius:7px;background:var(--side);color:var(--ink)';
        const save = telegramButton('احفظ المفتاح', async () => {
          const token = input.value.trim();
          if (!token) throw new Error('أدخل رمز البوت أولًا.');
          input.value = '';
          try { renderTelegram(await api('/api/assistant/telegram/token', { token })); }
          catch (err) { input.value = ''; throw err; }
        }, 'btn pri');
        telegramBody.append(input, save);
        telegramCard.status.textContent = 'لم يُحفظ مفتاح البوت.';
        return;
      }
      if (!telegramStatus.paired) {
        telegramCard.status.textContent = 'حُفظ المفتاح. بقيت ضغطة واحدة في Telegram.';
        telegramBody.appendChild(el('div', 'اضغط الزر أدناه، فيفتح Telegram على بوتك. اضغط فيه «Start» (أو «ابدأ») وسيرتبط هذا الجهاز تلقائيًا.'));
        if (telegramStatus.pair_link) {
          const open = el('a', 'افتح Telegram واضغط Start', 'btn pri');
          open.href = telegramStatus.pair_link; open.target = '_blank'; open.rel = 'noopener';
          open.style.cssText = 'display:block;text-align:center;text-decoration:none;margin:8px 0';
          telegramBody.appendChild(open);
          telegramBody.appendChild(el('div', 'أو أرسل للبوت يدويًا: /start ' + String(telegramStatus.pair_code)));
        }
        {
          const why = telegramStatus.gateway ? 'الاستماع يعمل. بانتظار ضغطك Start.' : (telegramStatus.error || (telegramStatus.running ? 'جارٍ الاتصال بـ Telegram…' : 'الاستماع متوقف.'));
          const line = el('div', 'الحالة: ' + why);
          line.style.cssText = 'font-size:.9em;opacity:.85;margin:6px 0';
          telegramBody.appendChild(line);
        }
        telegramBody.appendChild(telegramButton('رمز اقتران جديد', async () => renderTelegram(await api('/api/assistant/telegram/pair', {}))));
        telegramBody.appendChild(telegramButton('حذف المفتاح', async () => {
          if (!window.confirm('هل تريد حذف مفتاح Telegram من سلسلة مفاتيح هذا الجهاز؟')) return;
          renderTelegram(await api('/api/assistant/telegram/forget', {}));
        }));
        if (!telegramPoll) telegramPoll = setInterval(async () => {
          try { renderTelegram(await api('/api/assistant/telegram/status')); }
          catch (err) { telegramError(err); }
        }, 3000);
        return;
      }
      if (telegramPoll) { clearInterval(telegramPoll); telegramPoll = null; }
      telegramCard.status.textContent = (telegramStatus.machine || 'هذا الجهاز') + ' · ' + (telegramStatus.gateway ? 'هذا الجهاز هو البوابة' : (telegramStatus.error || 'جهاز آخر يستقبل الرسائل الآن'));
      telegramBody.appendChild(telegramToggle('تشغيل الوصل', 'enabled', telegramStatus.enabled, renderTelegram));
      telegramBody.appendChild(telegramToggle('إشعار عند فشل وكيل', 'notify_error', telegramStatus.notify_error, renderTelegram));
      telegramBody.appendChild(telegramToggle('إشعار عند اكتمال ردّ طويل', 'notify_long', telegramStatus.notify_long, renderTelegram));
      telegramBody.appendChild(telegramToggle('إشعار عند اكتمال تحليل أو تنظيف أو تفريغ', 'notify_done', telegramStatus.notify_done, renderTelegram));
      telegramBody.appendChild(telegramToggle('إشعار عند توفر تحديث', 'notify_update', telegramStatus.notify_update, renderTelegram));
      telegramBody.appendChild(telegramToggle('السماح باعتماد العمليات الحمراء من Telegram (ضغطتان ورمز؛ الحذف النهائي لا يتم من هناك أبدًا)', 'approve_red', telegramStatus.approve_red, renderTelegram));
      telegramBody.appendChild(el('div', 'أوامر المساعد والأوامر الجاهزة تُكتب للبوت مباشرة، والعمليات الحمراء تنتظر موافقتك داخل زاجل.'));
      telegramBody.appendChild(telegramButton('رسالة تجربة', async () => {
        const result = await api('/api/assistant/telegram/test', {});
        telegramCard.status.textContent = result.sent ? 'أُرسلت رسالة التجربة.' : 'تعذر إرسال رسالة التجربة.';
      }));
      telegramBody.appendChild(telegramButton('فك الربط', async () => renderTelegram(await api('/api/assistant/telegram/unpair', {}))));
      telegramBody.appendChild(telegramButton('حذف المفتاح', async () => {
        if (!window.confirm('هل تريد حذف مفتاح Telegram من سلسلة مفاتيح هذا الجهاز؟')) return;
        renderTelegram(await api('/api/assistant/telegram/forget', {}));
      }));
    };
    api('/api/assistant/telegram/status').then(renderTelegram).catch(telegramError);

    // بطاقة واتساب: التنبيهات والتقرير الصباحي (الوقت والمحتوى والشكل)
    const waCard = makeSettingsCard('واتساب: التنبيهات والتقرير الصباحي', 'يراقب رسائلك الواردة ويرسل إلى Telegram ما يهمّك، وتقريرًا مرتّبًا في الوقت الذي تختاره. لا يرسل شيئًا إلى واتساب.');
    waCard.status.textContent = 'جارٍ تحميل الإعدادات…';
    const waBody = el('div', '');
    waBody.style.cssText = 'display:flex;flex-direction:column;gap:7px;margin-top:7px';
    waCard.card.appendChild(waBody);
    sideContentEl.appendChild(waCard.card);
    const waError = (err) => { waCard.status.textContent = err && err.message ? err.message : 'تعذر تنفيذ الطلب.'; };
    let waState = null;
    const waSave = async (patch) => { try { renderWa(await api('/api/assistant/whatsapp/configure', patch)); } catch (err) { waError(err); renderWa(waState); } };
    const waRow = (label, control) => {
      const row = el('label', '');
      row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:7px';
      row.append(document.createTextNode(label), control);
      return row;
    };
    const waCheck = (label, value, onChange) => {
      const input = document.createElement('input');
      input.type = 'checkbox'; input.checked = !!value;
      input.addEventListener('change', () => onChange(input.checked));
      const row = el('label', '');
      row.style.cssText = 'display:flex;align-items:center;gap:7px';
      row.append(input, document.createTextNode(label));
      return row;
    };
    const waInputStyle = 'padding:5px;border:1px solid var(--line);border-radius:7px;background:var(--side);color:var(--ink)';
    const waText = (value, placeholder, onSave) => {
      const input = document.createElement('input');
      input.type = 'text'; input.value = value || ''; input.placeholder = placeholder || '';
      input.style.cssText = 'width:100%;box-sizing:border-box;' + waInputStyle;
      input.addEventListener('change', () => onSave(input.value));
      return input;
    };
    const waNumber = (value, min, max, onSave) => {
      const input = document.createElement('input');
      input.type = 'number'; input.min = min; input.max = max; input.value = value;
      input.style.cssText = 'width:70px;' + waInputStyle;
      input.addEventListener('change', () => onSave(Number(input.value)));
      return input;
    };
    const waSelect = (value, options, onSave) => {
      const select = document.createElement('select');
      select.style.cssText = waInputStyle;
      options.forEach(([v, label]) => { const o = document.createElement('option'); o.value = v; o.textContent = label; if (String(v) === String(value)) o.selected = true; select.appendChild(o); });
      select.addEventListener('change', () => onSave(select.value));
      return select;
    };
    const renderWa = (st) => {
      waState = st || {};
      waBody.replaceChildren();
      const sec = waState.sections || {};
      waCard.status.textContent = (waState.error ? 'تنبيه: ' + waState.error : (waState.last_poll_secs_ago == null ? 'لم يبدأ الفحص بعد.' : 'آخر فحص قبل ' + waState.last_poll_secs_ago + ' ثانية.')) + ' (يعمل ما دام زاجل مفتوحًا)';
      const h = (t) => { const d = el('div', t); d.style.cssText = 'font-weight:600;margin-top:6px'; return d; };
      if (waState.bridge && waState.bridge !== 'ok') {
        const n = el('div', waState.bridge === 'none'
          ? 'تنبيه: جسر واتساب غير موجود على هذا الجهاز، فلن يعمل المراقب هنا. ما تكتبه هنا يُحفظ ويصل إلى الجهاز الذي فيه الجسر عند المزامنة (زر المزامنة في الإعدادات).'
          : 'تنبيه: الجسر موجود لكنه غير مقترن بحسابك؛ افتح صفحة الإقران أولًا.');
        n.style.cssText = 'padding:6px 8px;border-radius:6px;background:rgba(220,150,0,.15)';
        waBody.appendChild(n);
      }
      waBody.appendChild(h('التنبيهات الفورية'));
      waBody.appendChild(waCheck('أرسل لي في Telegram ما يهمّني فور وصوله', waState.enabled, (v) => waSave({ enabled: v })));
      waBody.appendChild(waCheck('اشمل المجموعات (صامتة افتراضيًا)', waState.alert_groups, (v) => waSave({ alert_groups: v })));
      waBody.appendChild(el('div', 'أشخاص مهمّون (اسم أو رقم، يفصل بينهم فاصلة):'));
      waBody.appendChild(waText((waState.vip || []).join('، '), 'مثل: أحمد، أمي', (v) => waSave({ vip: v })));
      waBody.appendChild(el('div', 'كلمات تُنبّهك:'));
      waBody.appendChild(waText((waState.keywords || []).join('، '), 'مثل: عقد، موعد', (v) => waSave({ keywords: v })));
      const quiet = el('div', '');
      quiet.style.cssText = 'display:flex;align-items:center;gap:6px';
      quiet.append(document.createTextNode('ساعات الهدوء (تُؤجَّل للتقرير) من'), waNumber(waState.quiet_from, 0, 23, (v) => waSave({ quiet_from: v })), document.createTextNode('إلى'), waNumber(waState.quiet_to, 0, 23, (v) => waSave({ quiet_to: v })));
      waBody.appendChild(quiet);

      waBody.appendChild(h('التقرير الصباحي'));
      waBody.appendChild(waCheck('أرسل لي تقريرًا يوميًا في Telegram', waState.digest, (v) => waSave({ digest: v })));
      const time = document.createElement('input');
      time.type = 'time'; time.style.cssText = waInputStyle;
      time.value = String(waState.digest_hour ?? 7).padStart(2, '0') + ':' + String(waState.digest_minute ?? 0).padStart(2, '0');
      time.addEventListener('change', () => { const [hh, mm] = (time.value || '07:00').split(':').map(Number); waSave({ digest_hour: hh, digest_minute: mm }); });
      waBody.appendChild(waRow('وقت وصوله', time));
      waBody.appendChild(waRow('الأيام', waSelect(waState.digest_days || 'all', [['all', 'كل يوم'], ['weekdays', 'أيام العمل (الاثنين–الجمعة)']], (v) => waSave({ digest_days: v }))));
      waBody.appendChild(waRow('الفترة التي يغطيها', waSelect(waState.window_hours || 24, [[12, 'آخر ١٢ ساعة'], [24, 'آخر ٢٤ ساعة'], [48, 'آخر ٤٨ ساعة'], [72, 'آخر ٧٢ ساعة']], (v) => waSave({ window_hours: Number(v) }))));
      waBody.appendChild(waRow('شكله', waSelect(waState.format || 'detailed', [['detailed', 'مفصّل (مع نص الرسائل)'], ['compact', 'مختصر (سطر لكل رسالة)'], ['names', 'أسماء فقط (بلا نص)']], (v) => waSave({ format: v }))));
      waBody.appendChild(waRow('عنوانه', waText(waState.title || '', '☀️ تقرير واتساب', (v) => waSave({ title: v }))));
      waBody.appendChild(waRow('عدد أهم الرسائل', waNumber(waState.max_top ?? 6, 1, 12, (v) => waSave({ max_top: v }))));
      waBody.appendChild(waRow('طول مقتطف الرسالة (حرفًا)', waNumber(waState.body_chars ?? 220, 40, 500, (v) => waSave({ body_chars: v }))));
      waBody.appendChild(el('div', 'ما يتضمنه:'));
      [['counts', 'الإحصاء في العنوان (عدد الرسائل والمحادثات)'], ['top', 'أهم الرسائل'], ['pending', 'من ينتظر ردّك'], ['busiest', 'أنشط المحادثات'], ['media', 'ما وصلك من صوتيات وصور']].forEach(([k, label]) => {
        waBody.appendChild(waCheck(label, sec[k], (v) => waSave({ sections: { [k]: v } })));
      });
      waBody.appendChild(h('التلخيص الذكي (اختياري)'));
      waBody.appendChild(waCheck('لخّص التقرير بالذكاء الاصطناعي: أهم ما وصلك وسبب أهميته واقتراح ردود', waState.ai, (v) => waSave({ ai: v })));
      const aiWarn = el('div', 'تنبيه: مقتطفات أهم الرسائل (بعد استبعاد ما تحدده أدناه وإخفاء الأرقام الطويلة) تُرسل إلى النموذج الذي تختاره. الحالات والقنوات لا تُرسل أبدًا، ولا يملك النموذج أي أداة. وإن فشل التلخيص يصلك التقرير العادي.');
      aiWarn.style.cssText = 'font-size:.88em;opacity:.85';
      waBody.appendChild(aiWarn);
      waBody.appendChild(waRow('المصدر', waSelect(waState.ai_agent || 'agy', [['agy', 'Antigravity (حساب Google)'], ['claude', 'Claude Haiku']], (v) => waSave({ ai_agent: v }))));
      waBody.appendChild(el('div', 'لا يُرسل عنهم أو عنها شيء إلى النموذج (أسماء أو كلمات):'));
      waBody.appendChild(waText((waState.ai_exclude || []).join('، '), 'مثل: العائلة، البنك', (v) => waSave({ ai_exclude: v })));
      waBody.appendChild(waRow('أقصى عدد رسائل تُلخَّص', waNumber(waState.ai_max ?? 20, 5, 40, (v) => waSave({ ai_max: v }))));
      waBody.appendChild(waCheck('اقترح ردودًا (لا تُرسل أبدًا إلا بموافقتك)', waState.ai_reply, (v) => waSave({ ai_reply: v })));
      const aiOut = el('pre', '');
      aiOut.style.cssText = 'white-space:pre-wrap;margin:0;padding:8px;border:1px dashed var(--line);border-radius:7px;display:none;max-height:240px;overflow:auto';
      waBody.appendChild(telegramButton('اختبر التلخيص الذكي (برسائل مصطنعة، لا رسائلك)', async () => {
        waCard.status.textContent = 'جارٍ الاختبار… قد يستغرق دقيقة.';
        const r = await api('/api/assistant/whatsapp/ai_test', {});
        aiOut.textContent = r.ok ? r.text : ('تعذّر: ' + r.error); aiOut.style.display = 'block';
        waCard.status.textContent = r.ok ? ('نجح الاختبار خلال ' + r.secs + ' ثانية.') : 'فشل الاختبار.';
      }));
      waBody.appendChild(aiOut);
      const preview = el('pre', '');
      preview.style.cssText = 'white-space:pre-wrap;margin:0;padding:8px;border:1px dashed var(--line);border-radius:7px;display:none;max-height:240px;overflow:auto';
      waBody.appendChild(telegramButton('معاينة التقرير الآن', async () => {
        waCard.status.textContent = waState.ai ? 'جارٍ التلخيص الذكي… قد يستغرق دقيقة أو أكثر.' : 'جارٍ بناء المعاينة…';
        const r = await api('/api/assistant/whatsapp/preview', {});
        preview.textContent = r.text || ''; preview.style.display = 'block';
        waCard.status.textContent = 'هذه معاينة ولم تُرسل.';
      }));
      waBody.appendChild(preview);
      waBody.appendChild(telegramButton('أرسل التقرير إلى Telegram الآن', async () => {
        const r = await api('/api/assistant/whatsapp/digest', {});
        waCard.status.textContent = r.sent ? 'أُرسل التقرير إلى Telegram.' : 'لم يُرسل: تأكد أن Telegram مفعّل ومقترن.';
      }));
    };
    api('/api/assistant/whatsapp/status').then(renderWa).catch(waError);

    // بطاقة الهاتف اللاسلكي أعلى تبويب الإعدادات
    renderPhoneCard(sideContentEl);

    // 1. أزرار الأدوات الفورية في الأعلى (الحالة / العمليات / أوقف الكل)
    const quickBox = el('div', '', 'as-quick-tools-grid');
    const statusBtn = btn('', () => runQuick('status'), 'btn');
    statusBtn.append(createSvg('activity', 13), document.createTextNode('الحالة'));

    const opsBtn = btn('', () => runQuick('ops'), 'btn');
    opsBtn.append(createSvg('layers', 13), document.createTextNode('العمليات'));

    const stopAllBtn = btn('', () => runQuick('stop_all'), 'btn');
    stopAllBtn.style.color = 'var(--err)';
    stopAllBtn.append(createSvg('ban', 13), document.createTextNode('أوقف الكل'));

    quickBox.append(statusBtn, opsBtn, stopAllBtn);
    sideContentEl.appendChild(quickBox);

    // 2. زر تحديث النماذج
    const refreshBox = el('div', '', 'as-refresh-box');
    refreshBox.style.display = 'flex';
    refreshBox.style.flexDirection = 'column';
    refreshBox.style.gap = '4px';
    refreshBox.style.marginBottom = '8px';

    const refreshBtn = btn('', async () => {
      await refreshModelsList(refreshBtn, refreshStat);
    }, 'btn pri as-refresh-models-btn');
    refreshBtn.append(createSvg('refresh', 13), document.createTextNode('تحديث قائمة النماذج'));

    const refreshStat = el('div', 'اضغط لجلب أحدث النماذج المتوفرة محليًا وعبر الحسابات.', 'as-refresh-status');
    refreshBox.append(refreshBtn, refreshStat);
    sideContentEl.appendChild(refreshBox);

    // 3. بطاقات الوكلاء
    agentsList.forEach(ag => {
      const isCurrentActive = ag.id === activeAgentId;
      const isDefault = ag.id === currentSettings.default_agent || (ag.default && !currentSettings.default_agent);

      const card = el('div', '', 'as-agent-card' + (isCurrentActive ? ' as-active-agent' : ''));

      // ترويسة بطاقة الوكيل
      const head = el('div', '', 'as-agent-head');
      const titleRow = el('div', '', 'as-agent-title-row');
      const name = el('span', ag.name, 'as-agent-name');

      const badges = el('div', '', 'as-agent-badges');
      badges.style.display = 'inline-flex';
      badges.style.gap = '4px';
      if (isCurrentActive) {
        badges.appendChild(el('span', 'النشط', 'as-pill current'));
      }
      badges.appendChild(el('span', ag.installed ? 'مثبّت' : 'غير مثبّت', 'as-pill ' + (ag.installed ? 'installed' : 'missing')));

      titleRow.append(name, badges);

      // زر النجمة (الأساسي)
      const starBtn = el('button', '', 'as-star-btn' + (isDefault ? ' is-default' : ''), {
        title: isDefault ? 'هذا هو الوكيل الأساسي' : 'تعيين كالوكيل الأساسي'
      });
      starBtn.append(createSvg(isDefault ? 'star-filled' : 'star', 12));
      starBtn.appendChild(document.createTextNode(isDefault ? 'الأساسي' : 'افتراضي'));
      starBtn.onclick = async (e) => {
        e.stopPropagation();
        try {
          const res = await api('/api/assistant/settings', { default_agent: ag.id });
          if (res?.settings) currentSettings = res.settings;
          if (res?.agents) agentsList = res.agents;
          activeAgentId = ag.id;
          activeModel = ag.model || '';
          updateSourceBadge();
          safeNote('تم تعيين ' + ag.name + ' كالوكيل الأساسي.');
          renderSettingsTab();
        } catch (err) {
          safeNote('تعذر تعيين الوكيل الأساسي: ' + (err.message || ''));
        }
      };

      head.append(titleRow, starBtn);

      // معلومات الوكيل
      const descBox = el('div', '');
      descBox.style.fontSize = '11px';
      descBox.style.color = 'var(--mut)';
      descBox.style.lineHeight = '1.45';

      if (ag.billing) {
        const r1 = el('div', 'الحساب: ' + ag.billing);
        descBox.appendChild(r1);
      }
      if (ag.note) {
        const r2 = el('div', 'الملاحظة: ' + ag.note);
        descBox.appendChild(r2);
      }
      const r3 = el('div', 'آخر استقدام: ' + formatRelativeTime(ag.fetched));
      descBox.appendChild(r3);

      // عناصر التحكم بالنماذج
      const controls = el('div', '');
      controls.style.display = 'flex';
      controls.style.flexDirection = 'column';
      controls.style.gap = '5px';

      // منتقي النماذج
      const modelRow = el('div', '', 'as-ctrl-row');
      modelRow.appendChild(el('span', 'النموذج:', 'as-ctrl-lbl'));

      const modelSelect = el('select', '', 'as-select');
      const models = Array.isArray(ag.models) ? ag.models : [];

      if (models.length > 0) {
        models.forEach(m => {
          const opt = el('option', m.name + (m.free ? ' (مجاني)' : '') + (m.note ? ' — ' + m.note : ''), '');
          opt.value = m.id;
          if (m.id === (ag.model || activeModel)) {
            opt.selected = true;
          }
          modelSelect.appendChild(opt);
        });
      } else {
        const opt = el('option', ag.model || 'الافتراضي', '');
        opt.value = ag.model || '';
        opt.selected = true;
        modelSelect.appendChild(opt);
      }

      modelSelect.onchange = async () => {
        const newModel = modelSelect.value;
        try {
          const res = await api('/api/assistant/settings', { agent: ag.id, model: newModel });
          if (res?.settings) currentSettings = res.settings;
          if (res?.agents) agentsList = res.agents;
          ag.model = newModel;

          if (ag.id === activeAgentId) {
            activeModel = newModel;
            updateSourceBadge();
            newChat();
          }
          renderSettingsTab();
        } catch (err) {
          safeNote('تعذر حفظ النموذج: ' + (err.message || ''));
        }
      };

      modelRow.appendChild(modelSelect);
      controls.appendChild(modelRow);

      // حقل نموذج مخصص
      const customRow = el('div', '', 'as-ctrl-row');
      customRow.appendChild(el('span', 'مخصص:', 'as-ctrl-lbl'));
      const customInp = el('input', '', 'as-input-text', {
        placeholder: 'معرّف نموذج مخصص…'
      });
      customInp.value = models.some(m => m.id === ag.model) ? '' : (ag.model || '');
      customInp.onkeydown = async (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          const val = customInp.value.trim();
          if (!val) return;
          try {
            const res = await api('/api/assistant/settings', { agent: ag.id, model: val });
            if (res?.settings) currentSettings = res.settings;
            if (res?.agents) agentsList = res.agents;
            ag.model = val;
            if (ag.id === activeAgentId) {
              activeModel = val;
              updateSourceBadge();
              newChat();
            }
            safeNote('تم حفظ النموذج المخصص: ' + val);
            renderSettingsTab();
          } catch (err) {
            safeNote('خطأ في معرّف النموذج: ' + (err.message || ''));
          }
        }
      };
      customRow.appendChild(customInp);
      controls.appendChild(customRow);

      // خيار الجهد has_effort
      if (ag.has_effort) {
        const effortRow = el('div', '', 'as-ctrl-row');
        effortRow.appendChild(el('span', 'الجهد:', 'as-ctrl-lbl'));
        const effortSelect = el('select', '', 'as-select');
        const efforts = ['low', 'medium', 'high', 'xhigh', 'max'];
        const currentEffort = ag.effort || currentSettings?.efforts?.[ag.id] || 'medium';

        efforts.forEach(ef => {
          const opt = el('option', ef, '');
          opt.value = ef;
          if (ef === currentEffort) opt.selected = true;
          effortSelect.appendChild(opt);
        });

        effortSelect.onchange = async () => {
          const val = effortSelect.value;
          try {
            const res = await api('/api/assistant/settings', { agent: ag.id, effort: val });
            if (res?.settings) currentSettings = res.settings;
            if (res?.agents) agentsList = res.agents;
            ag.effort = val;
            safeNote('تم حفظ مستوى الجهد: ' + val);
          } catch (err) {
            safeNote('تعذر حفظ الجهد: ' + (err.message || ''));
          }
        };

        effortRow.appendChild(effortSelect);
        controls.appendChild(effortRow);
      }

      // زر اختيار الوكيل للمحادثة الحالية
      if (!isCurrentActive) {
        const chooseBtn = btn('اختيار كمصدر للمحادثة الحالية', () => {
          activeAgentId = ag.id;
          activeModel = ag.model || '';
          updateSourceBadge();
          renderSettingsTab();
          newChat();
        }, 'btn as-choose-agent-btn');
        controls.appendChild(chooseBtn);
      }

      card.append(head, descBox, controls);
      sideContentEl.appendChild(card);
    });
  }

  const agentChartColors = ['#4f8cff', '#19a974', '#f59e0b', '#e05d8c', '#8b6ce8', '#13a8a8', '#ef6548', '#78909c'];
  function agentColor(i) { return agentChartColors[i % agentChartColors.length]; }
  function agentsActive() { return (isOpen && isSidebarOpen || activeWindow === 'control' && controlPanelEl && !controlPanelEl.hidden) && activeTab === 'agents'; }
  function stopAgentsPolling() { if (agentsPollTimer) clearInterval(agentsPollTimer); agentsPollTimer = null; }
  function startAgentsPolling() {
    stopAgentsPolling();
    if (agentsActive()) agentsPollTimer = setInterval(() => { if (agentsActive()) loadAgentsStats(true); else stopAgentsPolling(); }, 20000);
  }
  async function loadAgentsStats(silent = false) {
    if (!agentsActive() || agentsLoading) return;
    agentsLoading = true;
    try {
      agentsStats = await api('/api/assistant/agents/stats?hours=' + agentsRange);
      renderAgentsTab();
      startAgentsPolling();
    } catch (err) {
      if (!silent) { agentsStats = null; renderAgentsTab(err.message || 'تعذر تحميل الإحصاءات'); }
    } finally { agentsLoading = false; }
  }
  function svgNode(tag, attrs = {}) {
    const node = document.createElementNS(SVG_NS, tag);
    Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, String(v)));
    return node;
  }
  function agentRelativeTime(value) {
    const ms = typeof value === 'number' ? value : Date.parse(value);
    if (!Number.isFinite(ms)) return '—';
    const mins = Math.max(0, Math.floor((Date.now() - ms) / 60000));
    if (mins < 1) return 'الآن';
    if (mins < 60) return 'قبل ' + mins.toLocaleString('ar') + ' دقيقة';
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return 'قبل ' + hrs.toLocaleString('ar') + ' ساعة';
    return 'قبل ' + Math.floor(hrs / 24).toLocaleString('ar') + ' يوم';
  }
  function agentSparkline(series, color) {
    const svg = svgNode('svg', { viewBox: '0 0 120 32', width: '120', height: '32', role: 'img', 'aria-label': 'اتجاه زمن الاستجابة' });
    const nums = (series || []).map((v, i) => v == null || !Number.isFinite(Number(v)) ? null : { i, v: Number(v) });
    const valid = nums.filter(Boolean);
    if (valid.length < 2) return svg;
    const vals = valid.map(p => p.v), min = Math.min(...vals), max = Math.max(...vals), span = max - min || 1;
    let segment = [];
    const flush = () => { if (segment.length > 1) svg.appendChild(svgNode('polyline', { points: segment.map(p => `${(p.i / Math.max(1, nums.length - 1)) * 116 + 2},${29 - ((p.v - min) / span) * 25}`).join(' '), fill: 'none', stroke: color, 'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' })); segment = []; };
    nums.forEach(p => { if (p) segment.push(p); else flush(); }); flush(); return svg;
  }
  function renderAgentsTab(errorMsg = '') {
    if (activeTab !== 'agents' || !sideContentEl) return;
    sideContentEl.replaceChildren();
    const wrap = el('div', '', 'as-memory-head-box');
    wrap.style.cssText = 'padding:10px;margin-bottom:9px';
    const ranges = [[24, 'آخر ٢٤ ساعة'], [168, '٧ أيام'], [720, '٣٠ يومًا']];
    const rangeRow = el('div', '', ''); rangeRow.style.cssText = 'display:flex;gap:6px;flex-wrap:wrap';
    ranges.forEach(([hours, label]) => { const chip = btn(label, () => { agentsRange = hours; agentsStats = null; renderAgentsTab(); loadAgentsStats(); }, 'btn' + (agentsRange === hours ? ' pri' : '')); chip.style.cssText = 'padding:5px 9px;font-size:11px'; rangeRow.appendChild(chip); });
    wrap.appendChild(rangeRow);
    wrap.appendChild(el('div', 'الإحصاءات تقديرية، وقد تختلف عن الاستهلاك الفعلي.', 'as-memory-desc'));
    sideContentEl.appendChild(wrap);
    if (errorMsg) { sideContentEl.appendChild(el('div', errorMsg, 'as-memory-hint')); return; }
    if (!agentsStats) { sideContentEl.appendChild(el('div', 'جارٍ تحميل الإحصاءات…', 'as-memory-hint')); return; }
    const data = agentsStats, list = Array.isArray(data.agents) ? data.agents : [], names = data.names || {};
    const nameOf = id => names[id] || id;
    const cardGrid = el('div', '', ''); cardGrid.style.cssText = 'display:grid;gap:8px';
    const statusLabel = { ok: 'يعمل', slow: 'بطيء', down: 'متوقف', idle: 'لم يُجرَّب' };
    list.forEach((agent, index) => {
      const card = el('div', '', 'as-memory-card'); card.style.cssText = 'padding:10px';
      const top = el('div', '', ''); top.style.cssText = 'display:flex;align-items:center;gap:7px;flex-wrap:wrap';
      const dot = el('span', ''); dot.style.cssText = `width:9px;height:9px;border-radius:50%;background:${agentColor(index)};flex:none`;
      const title = el('strong', nameOf(agent.id)); title.style.cssText = 'flex:1';
      const pill = el('span', statusLabel[agent.status] || statusLabel.idle); pill.style.cssText = 'border:1px solid var(--line);border-radius:999px;padding:2px 7px;font-size:10px;color:var(--muted)';
      top.append(dot, title, pill); card.appendChild(top);
      card.appendChild(el('div', agent.why || (agent.status === 'idle' ? 'لا بيانات بعد' : ''), 'as-memory-hint'));
      const metrics = el('div', '', ''); metrics.style.cssText = 'display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:6px;font-size:11px;color:var(--muted)';
      const median = Number(agent.median), success = Number(agent.success);
      metrics.append(el('span', `الوسيط ${Number.isFinite(median) && median > 0 ? median.toLocaleString('ar', { maximumFractionDigits: 1 }) + ' ث' : '—'}`), el('span', `النجاح ${Number.isFinite(success) ? success.toLocaleString('ar', { maximumFractionDigits: 1 }) : '—'}٪`), agentSparkline(agent.series, agentColor(index)));
      card.appendChild(metrics);
      const checkResult = el('span', '', 'as-memory-hint');
      const checkBtn = btn('فحص', async () => { checkBtn.disabled = true; checkResult.textContent = 'جارٍ الفحص…'; try { const res = await api('/api/assistant/agents/ping', { agent: agent.id }); checkResult.textContent = `${res.alive ? 'يستجيب' : 'لا يستجيب'} · ${res.why || ''}${Number.isFinite(Number(res.ms)) ? ' · ' + Number(res.ms).toLocaleString('ar') + ' ملث' : ''}`; } catch (err) { checkResult.textContent = err.message || 'تعذر الفحص'; } finally { checkBtn.disabled = false; } }, 'btn');
      checkBtn.style.cssText = 'padding:4px 9px;font-size:10px;margin-top:5px'; card.append(checkBtn, checkResult); cardGrid.appendChild(card);
    });
    sideContentEl.appendChild(cardGrid);
    if (!list.length || list.every(a => a.status === 'idle')) sideContentEl.appendChild(el('div', 'لا بيانات بعد', 'as-memory-empty'));
    const chartCard = el('div', '', 'as-memory-head-box'); chartCard.style.cssText = 'padding:10px;margin-top:9px';
    chartCard.appendChild(el('strong', 'زمن الاستجابة', ''));
    const chart = svgNode('svg', { viewBox: '0 0 360 132', width: '100%', height: '132', role: 'img', 'aria-label': 'مخطط زمن الاستجابة' });
    [25, 60, 95, 125].forEach(y => chart.appendChild(svgNode('line', { x1: 25, y1: y, x2: 355, y2: y, stroke: 'var(--line)', 'stroke-width': 1 })));
    const maxResponse = Math.max(1, ...list.flatMap(a => (a.series || []).filter(v => v != null).map(Number).filter(Number.isFinite)));
    list.forEach((agent, i) => { const vals = agent.series || [], points = vals.map((v, n) => v == null || !Number.isFinite(Number(v)) ? null : `${30 + n * (320 / Math.max(1, vals.length - 1))},${124 - Number(v) / maxResponse * 92}`).filter(Boolean); if (points.length > 1) chart.appendChild(svgNode('polyline', { points: points.join(' '), fill: 'none', stroke: agentColor(i), 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' })); });
    chartCard.appendChild(chart);
    const legend = el('div', '', ''); legend.style.cssText = 'display:flex;gap:9px;flex-wrap:wrap;font-size:10px';
    list.forEach((a, i) => { const item = el('span', nameOf(a.id)); item.style.cssText = `color:${agentColor(i)}`; legend.appendChild(item); }); chartCard.appendChild(legend); sideContentEl.appendChild(chartCard);
    const tokenCard = el('div', '', 'as-memory-head-box'); tokenCard.style.cssText = 'padding:10px;margin-top:9px'; tokenCard.appendChild(el('strong', 'توزيع الرموز التقديري', ''));
    const donut = svgNode('svg', { viewBox: '0 0 160 120', width: '160', height: '120', role: 'img', 'aria-label': 'توزيع الرموز' });
    const total = list.reduce((sum, a) => sum + Math.max(0, Number(a.tokens) || 0), 0), cx = 80, cy = 59, radius = 39, circumference = 2 * Math.PI * radius;
    let offset = 0;
    list.forEach((a, i) => { const amount = Math.max(0, Number(a.tokens) || 0), portion = total ? amount / total : 0; if (!portion) return; donut.appendChild(svgNode('circle', { cx, cy, r: radius, fill: 'none', stroke: agentColor(i), 'stroke-width': 13, 'stroke-dasharray': `${portion * circumference} ${circumference}`, 'stroke-dashoffset': -offset, transform: `rotate(-90 ${cx} ${cy})` })); offset += portion * circumference; });
    const compact = total >= 1e6 ? (total / 1e6).toLocaleString('ar', { maximumFractionDigits: 1 }) + ' م' : total >= 1e3 ? (total / 1e3).toLocaleString('ar', { maximumFractionDigits: 1 }) + ' ك' : total.toLocaleString('ar');
    const center = svgNode('text', { x: cx, y: cy + 4, 'text-anchor': 'middle', fill: 'var(--fg)', 'font-size': 12 }); center.textContent = '≈ ' + compact; donut.appendChild(center); tokenCard.appendChild(donut);
    list.forEach((a, i) => tokenCard.appendChild(el('div', `${nameOf(a.id)} · ${(total ? (Number(a.tokens || 0) / total * 100) : 0).toLocaleString('ar', { maximumFractionDigits: 1 })}٪`, 'as-memory-hint'))); sideContentEl.appendChild(tokenCard);
    const successCard = el('div', '', 'as-memory-head-box'); successCard.style.cssText = 'padding:10px;margin-top:9px'; successCard.appendChild(el('strong', 'معدل النجاح', ''));
    list.forEach((a, i) => { const row = el('div', '', ''); row.style.cssText = 'display:grid;grid-template-columns:minmax(60px,1fr) 2fr auto;gap:7px;align-items:center;margin-top:7px;font-size:10px'; row.appendChild(el('span', nameOf(a.id))); const track = el('div', ''); track.style.cssText = 'height:6px;background:var(--line);border-radius:8px;overflow:hidden'; const fill = el('div', ''); const pct = Math.max(0, Math.min(100, Number(a.success) || 0)); fill.style.cssText = `height:100%;width:${pct}%;background:${agentColor(i)}`; track.appendChild(fill); row.append(track, el('span', pct.toLocaleString('ar', { maximumFractionDigits: 1 }) + '٪')); successCard.appendChild(row); }); sideContentEl.appendChild(successCard);
    const errorsCard = el('div', '', 'as-memory-head-box'); errorsCard.style.cssText = 'padding:10px;margin-top:9px'; errorsCard.appendChild(el('strong', 'أحدث الأخطاء', ''));
    const errors = Array.isArray(data.errors) ? data.errors : [];
    if (!errors.length) errorsCard.appendChild(el('div', 'لا أخطاء حديثة', 'as-memory-hint'));
    else { const table = el('table', '', ''); table.style.cssText = 'width:100%;border-collapse:collapse;font-size:10px;margin-top:6px'; errors.slice(0, 20).forEach(err => { const tr = el('tr', ''); tr.style.borderBottom = '1px solid var(--line)'; [agentRelativeTime(err.t), nameOf(err.agent), err.error || ''].forEach(value => { const td = el('td', value); td.style.cssText = 'padding:5px 3px;vertical-align:top'; tr.appendChild(td); }); table.appendChild(tr); }); errorsCard.appendChild(table); }
    sideContentEl.appendChild(errorsCard);
  }

  function renderActiveTab() {
    const nav = activeWindow === 'control' ? controlTabsNav : sideTabsNav;
    if (!nav) return;
    Array.from(nav.children).forEach(b => {
      b.classList.toggle('as-active-tab', b.dataset.tab === activeTab);
    });

    if (activeTab === 'chats') renderChatsTab();
    else if (activeTab === 'memory') renderMemoryTab();
    else if (activeTab === 'prompts') renderPromptsTab();
    else if (activeTab === 'scripts') renderScriptsTab();
    else if (activeTab === 'automations') renderAutomationsTab();
    else if (activeTab === 'agents') renderAgentsTab();
    else if (activeTab === 'settings') renderSettingsTab();
    else if (activeTab === 'terminal') window.ZajelTerminalUI?.activate?.(controlContentEl);
  }

  /* ==========================================================================
     14. إرسال الرسالة ودورة عمل الوكيل والمؤشرات الحية والتعقيب أثناء العمل
     ========================================================================== */
  /* ==========================================================================
     أسئلة التوضيح قبل الإرسال: يقرأ المساعد الطلب ويسأل أسئلة اختيارية سريعة ثم يرسله مُثرى
     ========================================================================== */
  let clarifyBusy = false;
  function clarifyEnabled() {
    try { return localStorage.getItem('zajel_as_clarify') !== 'off'; } catch (_) { return true; }
  }
  function shouldClarify(text) {
    if (!clarifyEnabled() || clarifyBusy || currentJobId) return false;
    if (text.startsWith('/') || text.includes('— توضيحات')) return false;
    const words = text.split(/\s+/).filter(Boolean).length;
    return words <= 14 && text.length < 200;
  }

  // يعيد النص النهائي، أو null إن ألغى المستخدم
  function clarifyFlow(text) {
    return new Promise(resolve => {
      clarifyBusy = true;
      const card = el('div', '', 'as-clarify');
      const finish = val => { clarifyBusy = false; card.remove(); resolve(val); };
      const head = el('div', '', 'as-clarify-head');
      head.appendChild(el('b', '🔎 أقرأ طلبك قبل الإرسال…'));
      const skip = btn('أرسل كما هو', () => { token++; finish(text); }, 'btn');
      const cancel = btn('إلغاء', () => { token++; finish(null); }, 'btn');
      const acts = el('span', '', 'as-imp-acts');
      acts.append(skip, cancel);
      head.appendChild(acts);
      card.appendChild(head);
      card.appendChild(el('div', text, 'as-clarify-q'));
      chatContainer.appendChild(card);
      scrollToChatBottom(true);
      let token = 0;
      const my = token;

      const showQuestions = d => {
        card.replaceChildren();
        const h2 = el('div', '', 'as-clarify-head');
        h2.appendChild(el('b', d.intro || 'أسئلة سريعة تحسّن الجواب:'));
        const a2 = el('span', '', 'as-imp-acts');
        h2.appendChild(a2);
        card.appendChild(h2);
        const answers = d.questions.map(() => new Set());
        const others = [];
        d.questions.forEach((q, qi) => {
          const box = el('div', '', 'as-clarify-box');
          box.appendChild(el('div', q.q, 'as-clarify-q'));
          const row = el('div', '', 'as-clarify-opts');
          q.options.forEach(o => {
            const b = btn(o, () => {
              if (!q.multi) { answers[qi].clear(); row.querySelectorAll('.on').forEach(x => x.classList.remove('on')); }
              if (answers[qi].has(o)) { answers[qi].delete(o); b.classList.remove('on'); }
              else { answers[qi].add(o); b.classList.add('on'); }
            }, 'btn as-clarify-opt');
            row.appendChild(b);
          });
          const other = el('input', '', 'as-word-input', { placeholder: 'أو اكتب إجابتك' });
          others.push(other);
          box.append(row, other);
          card.appendChild(box);
        });
        const foot = el('div', '', 'as-imp-foot');
        foot.append(
          btn('إرسال مع الإجابات', () => {
            const lines = [];
            d.questions.forEach((q, qi) => {
              const parts = [...answers[qi]];
              if (others[qi].value.trim()) parts.push(others[qi].value.trim());
              if (parts.length) lines.push('- ' + q.q + ' ' + parts.join('، '));
            });
            finish(lines.length ? text + '\n\n— توضيحات:\n' + lines.join('\n') : text);
          }, 'btn pri'),
          btn('أرسل كما هو', () => finish(text), 'btn'),
          btn('إلغاء', () => finish(null), 'btn')
        );
        card.appendChild(foot);
        scrollToChatBottom(true);
      };

      (async () => {
        try {
          const r = await api('/api/assistant/clarify', { text });
          for (let i = 0; i < 90; i++) {
            await new Promise(res => setTimeout(res, 1500));
            if (token !== my) return;
            const v = await api('/api/assistant/clarify/get?id=' + encodeURIComponent(r.id));
            if (v.state === 'done') {
              if (v.needs && v.questions && v.questions.length) showQuestions(v);
              else finish(text);
              return;
            }
          }
          finish(text);
        } catch (_) {
          if (token === my) finish(text);
        }
      })();
    });
  }

  async function sendMsg() {
    if (!inputEl) return;
    const raw = inputEl.value.trim();
    const readyAtts = pendingAttachments.filter(a => a.status === 'done');
    const hasUploading = pendingAttachments.some(a => a.status === 'uploading');
    if (hasUploading) return;
    if (!raw && !readyAtts.length) return;
    if (clarifyBusy) return;

    // لا يُشغّل clarify على نص فارغ حتى لو وُجدت مرفقات جاهزة
    if (raw && shouldClarify(raw)) {
      const out = await clarifyFlow(raw);
      if (out === null) return; // ألغى المستخدم: نحتفظ بالمرفقات في الشريط
      rememberSent(raw);
      if (inputEl.value.trim() !== raw && inputEl.value.trim()) return; // غيّر المستخدم النص أثناء الانتظار
      inputEl.value = out;
    } else if (raw) {
      rememberSent(raw);
    }
    return sendMsgNow();
  }

  async function sendMsgNow() {
    if (!inputEl) return;
    let text = inputEl.value.trim();
    const readyAtts = pendingAttachments.filter(a => a.status === 'done');
    const hasUploading = pendingAttachments.some(a => a.status === 'uploading');
    if (hasUploading) return;
    if (!text && !readyAtts.length) return;

    // إن كان النص فارغًا فاستعمل نصًا افتراضيًا: «اقرأ المرفقات وأخبرني بما فيها.» (يُرسل ويُعرض)
    if (!text && readyAtts.length > 0) {
      text = 'اقرأ المرفقات وأخبرني بما فيها.';
    }

    // تجهيز المرفقات للإرسال (حتى 10)
    const attachmentsToSend = [...readyAtts.filter(a => !a.ref).slice(0, 10), ...readyAtts.filter(a => a.ref).slice(0, 100)].map(a => a.ref
      ? { ref: true, sid: a.sid, path: a.path, name: a.name, kind: 'ref', is_dir: !!a.is_dir }
      : { path: a.path, name: a.name, kind: a.kind });

    // تفريغ المدخل وشريط المرفقات
    inputEl.value = '';
    autoResizeInput();
    updateImproveBtn();
    clearAttachments();

    // استخراج السياق إن طُلب
    let context = {};
    if (sendContextEnabled && typeof P !== 'undefined' && P) {
      const srcId = P.src ? P.src.id : '';
      const srcLabel = P.src ? (P.src.label || '') : '';
      const curPath = P.cur || '';
      let selected = [];
      if (typeof P.S === 'function') {
        try {
          const s = P.S();
          if (s && s.size) selected = Array.from(s).slice(0, 30);
        } catch (_) {}
      }
      context = {
        src: srcId,
        label: srcLabel,
        path: curPath,
        selected
      };
    }

    // إرفاق نطاق البحث المختار (مصفوفة معرّفات الأماكن، أو فارغة عند «الكل»)
    if (searchPlacesSelection && searchPlacesSelection.length > 0) {
      context.search_places = [...searchPlacesSelection];
    } else {
      context.search_places = [];
    }

    // إظهار فقاعة رسالة المستخدم مع المرفقات
    const userMsgEl = addMessage('user', text, attachmentsToSend);

    // إن كان المساعد يعمل حالياً في نفس المحادثة: لا تقطع المهمة ولا تنشئ بطاقة بوت جديدة
    if (currentJobId) {
      try {
        const res = await api('/api/assistant/chat', {
          agent: activeAgentId,
          model: activeModel,
          text,
          conversation: currentConversation,
          context,
          attachments: attachmentsToSend
        });

        // الخادم يعيد { job, conversation, queued: true, position: n }
        if (res && res.queued) {
          if (userMsgEl) {
            const qPill = el('span', 'في الطابور · رقم ' + (res.position || 1), 'as-queue-pill');
            userMsgEl.appendChild(qPill);
            scrollToChatBottom(true);
          }
        }
      } catch (err) {
        renderErrorMessage(err.message || 'تعذر إضافة التعقيب للطابور');
      }
      return;
    }

    // إن لم يكن المساعد يعمل: نبدأ مهمة جديدة عادية
    const botCard = createBotRunningCard(activeAgentId, activeModel);
    activeBotCard = botCard;
    chatContainer.appendChild(botCard.element);
    scrollToChatBottom(true);
    messages.push({ type: 'bot', element: botCard.element });
    trimMessages();

    if (stopBtn) stopBtn.disabled = false;
    currentJobId = 'pending_start';
    updateSendButtonState();

    try {
      const res = await api('/api/assistant/chat', {
        agent: activeAgentId,
        model: activeModel,
        text,
        conversation: currentConversation,
        context,
        attachments: attachmentsToSend
      });

      currentJobId = res.job;
      currentConversation = res.conversation || currentConversation;
      try { localStorage.setItem('zajel_as_last_chat', currentConversation); } catch (_) {}
      if (stopBtn) stopBtn.disabled = false;
      updateSendButtonState();

      pollJob(res.job, botCard);
    } catch (err) {
      botCard.element.remove();
      renderErrorMessage(err.message || 'تعذر إرسال الطلب');
      if (stopBtn) stopBtn.disabled = true;
      currentJobId = '';
      activeBotCard = null;
      updateSendButtonState();
      if (inputEl) inputEl.focus();
    }
  }

  function createBotRunningCard(agentId, modelName) {
    const element = el('div', '', 'as-msg as-msg-bot');

    const head = el('div', '', 'as-running-head');
    const metaWrap = el('div', '', 'as-running-meta');

    const typingPulse = el('span', '', 'as-typing-pulse');
    typingPulse.append(
      el('span', '', 'as-typing-dot'),
      el('span', '', 'as-typing-dot'),
      el('span', '', 'as-typing-dot')
    );

    const ag = agentsList.find(a => a.id === agentId);
    const displayName = (ag ? ag.name : agentId) + (modelName ? ' (' + modelName + ')' : '');
    const agentLabel = el('span', displayName);
    metaWrap.append(typingPulse, agentLabel);

    const timerText = el('span', '0 ث');
    head.append(metaWrap, timerText);

    const stepsTimeline = el('div', '', 'as-steps-timeline');
    const bodyText = el('div', '', 'as-msg-body');

    element.append(head, stepsTimeline, bodyText);

    const handledSteps = new Set();
    let currentRenderedText = '';

    return {
      element,
      timerText,
      updateTime(elapsedSec) {
        timerText.textContent = elapsedSec + ' ث';
      },
      updateSteps(steps) {
        if (!Array.isArray(steps)) return;
        steps.forEach(st => {
          const key = st.t + '_' + st.label;
          if (handledSteps.has(key)) return;
          handledSteps.add(key);

          const badge = el('span', '', 'as-step-badge');
          const tSec = typeof st.t === 'number' ? (st.t.toFixed(1) + 'ث') : '';
          badge.append(el('b', tSec), document.createTextNode(' ' + st.label));
          stepsTimeline.appendChild(badge);
        });
      },
      updateLiveText(text) {
        if (text && text !== currentRenderedText) {
          currentRenderedText = text;
          renderWithChoices(bodyText, text, false);
          scrollToChatBottom(true);
        }
      },
      markStopped(reasonText = 'قُطعت بتعقيب') {
        head.remove();
        stepsTimeline.remove();
        if (!currentRenderedText) {
          renderSafeFormattedText(bodyText, 'أُوقفت المهمة.');
        }

        const footer = el('div', '', 'as-bot-footer');
        const metaTag = el('div', '', 'as-bot-meta-tag');
        const stoppedPill = el('span', reasonText, 'as-pill stopped');
        metaTag.appendChild(stoppedPill);

        const agInfo = (ag ? ag.name : agentId) + (modelName ? ' · ' + modelName : '');
        metaTag.appendChild(document.createTextNode(agInfo));

        const copyBtn = btn('', () => {
          try {
            navigator.clipboard.writeText(currentRenderedText);
            safeNote('تم النسخ');
          } catch (_) {}
        }, 'as-copy-btn');
        copyBtn.append(createSvg('copy', 12), document.createTextNode('نسخ'));

        footer.append(metaTag, copyBtn);
        element.appendChild(footer);
      },
      finish(data, durationSec) {
        head.remove();
        stepsTimeline.remove();

        const isStopped = data.state === 'stopped';
        const finalText = data.text || (isStopped ? 'أُوقفت المهمة بناءً على طلبك.' : 'اكتملت المهمة.');
        renderWithChoices(bodyText, finalText, !isStopped);

        const footer = el('div', '', 'as-bot-footer');
        const metaTag = el('div', '', 'as-bot-meta-tag');

        if (isStopped) {
          metaTag.appendChild(el('span', 'قُطعت بتعقيب', 'as-pill stopped'));
        }

        const agInfo = (data.agent ? (agentsList.find(a => a.id === data.agent)?.name || data.agent) : (ag ? ag.name : agentId));
        const modInfo = data.model || modelName;
        const durStr = durationSec != null ? (durationSec + ' ثانية') : '';
        metaTag.appendChild(document.createTextNode(agInfo + (modInfo ? ' · ' + modInfo : '') + (durStr ? ' · ' + durStr : '')));

        const copyBtn = btn('', () => {
          try {
            navigator.clipboard.writeText(finalText);
            copyBtn.classList.add('copied');
            copyBtn.replaceChildren(createSvg('check', 12), document.createTextNode('تم النسخ'));
            setTimeout(() => {
              copyBtn.classList.remove('copied');
              copyBtn.replaceChildren(createSvg('copy', 12), document.createTextNode('نسخ'));
            }, 2000);
          } catch (_) {
            safeNote('تم نسخ النص');
          }
        }, 'as-copy-btn');
        copyBtn.append(createSvg('copy', 12), document.createTextNode('نسخ'));

        footer.append(metaTag, copyBtn);
        element.appendChild(footer);
      }
    };
  }

  function renderErrorMessage(errorText) {
    if (!chatContainer) return;
    const card = el('div', '', 'as-msg as-msg-err');
    const head = el('div', '', 'as-err-head');
    head.append(createSvg('shield-alert', 15), document.createTextNode('تعذر إكمال الطلب'));

    const msg = el('div', errorText, 'as-err-msg');

    const tryOtherBtn = btn('', () => {
      switchTab('settings');
    }, 'btn pri as-try-other-btn');
    tryOtherBtn.append(createSvg('swap', 13), document.createTextNode('جرّب مصدرًا آخر'));

    card.append(head, msg, tryOtherBtn);
    chatContainer.appendChild(card);
    scrollToChatBottom(true);
    messages.push({ type: 'err', element: card });
    trimMessages();
  }

  async function pollJob(jobId, botCard) {
    clearTimeout(jobPollTimer);
    const startTs = Date.now();

    async function step() {
      if (!currentJobId || currentJobId !== jobId) return;
      try {
        const data = await api('/api/assistant/job?id=' + encodeURIComponent(jobId));
        if (!data) return;

        // تحديث شريط التعقيبات المنتظرة في الطابور
        if (Array.isArray(data.queued)) {
          updateQueuedBar(data.queued);
        } else {
          updateQueuedBar([]);
        }

        let elapsed = 0;
        if (data.started) {
          elapsed = Math.max(0, Math.floor(Date.now() / 1000 - data.started));
        } else {
          elapsed = Math.max(0, Math.floor((Date.now() - startTs) / 1000));
        }

        botCard.updateTime(elapsed);

        if (Array.isArray(data.steps)) {
          botCard.updateSteps(data.steps);
        }

        if (data.text) {
          botCard.updateLiveText(data.text);
        }

        if (Array.isArray(data.events)) {
          checkEventsForResultsAndOps(data.events);
        }

        if (data.state === 'running') {
          jobPollTimer = setTimeout(step, 700);
        } else {
          // اكتملت المهمة الحالية
          if (data.state === 'error') {
            botCard.element.remove();
            renderErrorMessage(data.error || 'حدث خطأ غير متوقع أثناء معالجة الطلب.');
          } else {
            botCard.finish(data, elapsed);
          }

          if (Array.isArray(data.events)) {
            checkEventsForResultsAndOps(data.events);
          }

          // التحقق مما إذا كان هناك مهمة تالية ناتجة عن دمج التعقيبات المنتظرة
          if (data.next) {
            currentJobId = data.next;
            const nextBotCard = createBotRunningCard(activeAgentId, activeModel);
            activeBotCard = nextBotCard;
            chatContainer.appendChild(nextBotCard.element);
            messages.push({ type: 'bot', element: nextBotCard.element });
            trimMessages();
            scrollToChatBottom(true);
            if (stopBtn) stopBtn.disabled = false;
            updateSendButtonState();
            pollJob(data.next, nextBotCard);
          } else {
            currentJobId = '';
            activeBotCard = null;
            updateQueuedBar([]);
            if (stopBtn) stopBtn.disabled = true;
            updateSendButtonState();
          }
        }
      } catch (_) {
        jobPollTimer = setTimeout(step, 1400);
      }
    }

    jobPollTimer = setTimeout(step, 700);
  }

  /* ==========================================================================
     15. فحص الأحداث لبطاقات النتائج القابلة للطي والعمليات الطويلة
     ========================================================================== */
  function checkEventsForResultsAndOps(events) {
    if (!Array.isArray(events)) return;
    events.forEach((ev, idx) => {
      const evKey = (ev.t || '') + '_' + (ev.tool || '') + '_' + idx;
      if (inspectedEvents.has(evKey)) return;
      inspectedEvents.add(evKey);

      if (ev.search_id) {                       // نتيجة بحث: لوحة تفاعلية كاملة بدل بطاقة من ثمانية أسطر
        if (!renderedSearches.has(ev.search_id)) { renderedSearches.add(ev.search_id); renderSearchPanel(ev); }
        return;
      }

      let parsed = null;
      if (ev.result) {
        if (typeof ev.result === 'object') {
          parsed = ev.result;
        } else if (typeof ev.result === 'string') {
          try {
            parsed = JSON.parse(ev.result);
          } catch (_) {
            parsed = null;
          }
        }
      }

      if (!parsed) return;

      if (parsed.id && typeof parsed.id === 'string' && (ev.tool?.includes('op') || ev.tool?.includes('items') || ev.tool?.includes('sync') || ev.tool?.includes('migration'))) {
        trackOp(parsed.id);
      }
      if (Array.isArray(parsed.ops)) {
        parsed.ops.forEach(o => {
          if (o && o.id) trackOp(o.id);
        });
      }

      const list = Array.isArray(parsed.entries) ? parsed.entries :
                   Array.isArray(parsed.items) ? parsed.items :
                   Array.isArray(parsed.results) ? parsed.results : null;

      if (list && list.length > 0) {
        renderResultCard(ev.tool, list);
      }
    });
  }


  /* ==========================================================================
     15-ب. لوحة نتائج البحث التفاعلية: كل النتائج كاختصارات، تحديد، نسخ، معاينة بالمسافة، قائمة ⋯
     ========================================================================== */
  const renderedSearches = new Set();
  if (!document.getElementById('as-sp-styles')) {
    const st = document.createElement('style');
    st.id = 'as-sp-styles';
    st.textContent = `
      .as-sp{flex:none;border:1px solid var(--line);border-radius:12px;background:var(--panel);overflow:hidden;margin:8px 0;outline:none;position:relative}
      .as-sp-hd{padding:8px 12px;background:var(--side);display:flex;justify-content:space-between;align-items:center;gap:8px;font-weight:700}
      .as-sp-hd small{font-weight:400;color:var(--mut)}
      .as-sp-st,.as-sp-flt{padding:6px 10px;display:flex;gap:5px;flex-wrap:wrap;font-size:12px;border-bottom:1px solid var(--line)}
      .as-sp-chip{border:1px solid var(--line);background:var(--panel);color:inherit;border-radius:999px;padding:2px 10px;font:inherit;font-size:12px;cursor:pointer}
      .as-sp-chip.on{background:var(--accp);border-color:var(--acc);color:var(--acc)}
      .as-sp-chip.warn{background:var(--warnp);color:var(--warn);border-color:transparent;cursor:default}
      .as-sp-list{max-height:320px;overflow:auto;padding:4px}
      .as-sp-row{display:flex;align-items:center;gap:8px;padding:5px 8px;border-radius:8px;border:1px solid transparent;cursor:default}
      .as-sp-row:hover{background:var(--side)}
      .as-sp-row.sel{background:var(--accp);border-color:var(--acc)}
      .as-sp-row.cur{box-shadow:inset 0 0 0 1.5px var(--acc)}
      .as-sp-meta{flex:1;min-width:0}
      .as-sp-nm{font-weight:600;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;overflow-wrap:anywhere;line-height:1.35}
      .as-sp-th{width:38px;height:38px;border-radius:8px;background:var(--side);display:grid;place-items:center;overflow:hidden;flex:none;font-size:19px}
      .as-sp-th img{width:100%;height:100%;object-fit:cover}
      .as-sp-row{padding:6px 8px}
      .as-ref-group{display:flex;align-items:center;gap:8px}
      .as-ref-thumbs{display:flex;gap:3px}
      .as-ref-thumbs .as-chip-thumb{width:30px;height:30px;border-radius:6px;object-fit:cover}
      .as-msg-ref{padding:6px 10px;border-radius:10px;background:var(--accp);font-size:12.5px}
      .as-sp-pt{color:var(--mut);font-size:11.5px;direction:ltr;text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .as-sp-sz{color:var(--mut);font-size:11.5px;min-width:54px;text-align:left}
      .as-sp-more{border:1px solid var(--line);background:var(--panel);color:inherit;border-radius:7px;padding:0 8px;font-size:16px;line-height:22px;cursor:pointer}
      .as-sp-ft{padding:7px 10px;border-top:1px solid var(--line);display:flex;gap:6px;align-items:center;flex-wrap:wrap;background:var(--side);font-size:12px}
      .as-sp-b{border:1px solid var(--line);background:var(--panel);color:inherit;border-radius:7px;padding:3px 10px;font:inherit;font-size:12px;cursor:pointer}
      .as-sp-b.pri{background:var(--acc);border-color:var(--acc);color:#fff}
      .as-sp-b:disabled{opacity:.5;cursor:default}
      .as-sp-menu{position:absolute;z-index:30;background:var(--panel);border:1px solid var(--line);border-radius:10px;box-shadow:0 10px 30px rgba(0,0,0,.25);padding:4px;min-width:210px}
      .as-sp-menu button{display:block;width:100%;text-align:right;border:0;background:none;color:inherit;font:inherit;padding:6px 10px;border-radius:7px;cursor:pointer}
      .as-sp-menu button:hover{background:var(--accp)}
      .as-sp-menu hr{border:0;border-top:1px solid var(--line);margin:3px 0}
    `;
    document.head.appendChild(st);
  }

  const SP_TYPES = [['صور', /\.(jpe?g|png|gif|webp|heic|bmp|tiff?)$/i], ['فيديو', /\.(mp4|mov|mkv|avi|m4v|webm)$/i], ['صوت', /\.(mp3|m4a|wav|aac|flac|ogg)$/i],
    ['مستندات', /\.(pdf|docx?|txt|md|rtf|pages|epub|odt)$/i], ['جداول', /\.(xlsx?|csv|numbers|ods)$/i], ['أرشيف', /\.(zip|rar|7z|tar|gz|dmg)$/i]];
  const spType = e => e.is_dir ? 'مجلدات' : (SP_TYPES.find(t => t[1].test(e.name)) || ['أخرى'])[0];
  const spSrcLabel = sid => (typeof entrySrc === 'function' && entrySrc(sid)?.label) || sid || '—';

  async function renderSearchPanel(ev) {
    if (!chatContainer) return;
    let job;
    try { job = await api('/api/search/job?id=' + encodeURIComponent(ev.search_id)); } catch (_) { return; }   // انتهت صلاحية الجلسة
    const place = ev.search_place || '';
    const S = { sel: new Set(), cur: -1, anchor: -1, src: '', type: '', rows: [] };
    const card = el('div', '', 'as-sp', { tabindex: '0', 'aria-label': 'نتائج البحث' });
    const title = el('b'), sub = el('small');
    const hd = el('div', '', 'as-sp-hd'); hd.append(title, sub);
    const st = el('div', '', 'as-sp-st'), flt = el('div', '', 'as-sp-flt'), list = el('div', '', 'as-sp-list'), ft = el('div', '', 'as-sp-ft');
    card.append(hd, st, flt, list, ft);
    let menu = null;
    const closeMenu = () => { if (menu) { menu.remove(); menu = null; } };

    const ents = () => (job.entries || []).map(e => ({ ...e, sid: e.sid || place })).filter(e => e.sid);
    const visible = () => ents().filter(e => (!S.src || e.sid === S.src) && (!S.type || spType(e) === S.type));
    const itemsOf = (idxs) => idxs.map(i => S.rows[i]).filter(Boolean);
    const chosen = () => S.sel.size ? [...S.sel].sort((a, b) => a - b) : (S.cur >= 0 ? [S.cur] : []);
    const keyOf = e => e.sid + '|' + e.path;
    const selKeys = new Set();   // التحديد يبقى مع وصول نتائج جديدة
    const panelId = 'sp_' + ev.search_id;
    function syncRefs() { setRefAttachments(panelId, ents().filter(e => selKeys.has(keyOf(e)))); }
    refPanels.set(panelId, () => {   // حين يُزال المرفق أو تُرسل الرسالة: يتبعها التحديد هنا
      const have = new Set(pendingAttachments.filter(a => a.panel === panelId).map(a => a.key));
      [...selKeys].forEach(k => { if (!have.has(k)) selKeys.delete(k); });
      drawRows(); drawFoot(true);
    });

    function lines(items) { return items.map(e => `- [${e.sid}] ${e.path}`).join('\n'); }
    function toAssistant(prefix, items, send) {
      if (!inputEl) return;
      inputEl.value = prefix + '\n' + lines(items);
      if (typeof autoResizeInput === 'function') autoResizeInput();
      if (send) sendMsg(); else inputEl.focus();
    }
    async function copyText(t, msg) { try { await navigator.clipboard.writeText(t); } catch (_) { const ta = document.createElement('textarea'); ta.value = t; document.body.append(ta); ta.select(); try { document.execCommand('copy'); } catch (__) {} ta.remove(); } safeNote(msg); }

    function menuFor(idxs, anchorEl) {
      closeMenu();
      const items = itemsOf(idxs); if (!items.length) return;
      menu = el('div', '', 'as-sp-menu');
      const one = items.length === 1;
      const add = (t, f) => { if (t === '-') { menu.append(document.createElement('hr')); return; } const b = el('button', t); b.type = 'button'; b.onclick = (e) => { e.stopPropagation(); closeMenu(); f(); }; menu.append(b); };
      if (one) { add('فتح في مكانه الأصلي', () => revealEntry(items[0])); add('معاينة (مسافة)', () => previewEntries(S.rows, idxs[0])); add('-'); }
      add(one ? 'انسخ إلى…' : `انسخ المحدد (${items.length}) إلى…`, () => copyEntries(items));
      add('انسخ المسارات', () => copyText(items.map(e => e.path).join('\n'), 'نُسخت المسارات.'));
      add('-');
      add('اطلب من المساعد: حلّلها', () => toAssistant('حلّل هذه الملفات وأخبرني بمحتواها وأهم ما فيها:', items, true));
      add('اطلب من المساعد: انسخها…', () => toAssistant('انسخ هذه الملفات إلى المكان الذي سأذكره بعد قليل:', items, false));
      add('اطلب من المساعد: أنشئ مجلدًا وضعها فيه…', () => toAssistant('أنشئ مجلدًا جديدًا باسم «…» (اكتب الاسم) وانسخ إليه هذه الملفات:', items, false));
      card.append(menu);
      const r = anchorEl.getBoundingClientRect(), c = card.getBoundingClientRect();
      menu.style.top = Math.min(r.bottom - c.top + 2, Math.max(0, c.height - menu.offsetHeight - 4)) + 'px';
      menu.style.left = Math.max(4, r.left - c.left) + 'px';
    }

    function drawRows() {
      const rows = visible(); S.rows = rows;
      S.sel = new Set(); rows.forEach((e, i) => { if (selKeys.has(keyOf(e))) S.sel.add(i); });
      list.replaceChildren();
      if (!rows.length) list.append(el('div', job.state === 'running' ? 'جارٍ البحث…' : 'لا نتائج.', 'as-sp-pt', { style: 'padding:12px;text-align:center' }));
      rows.slice(0, 600).forEach((e, i) => {
        const row = el('div', '', 'as-sp-row' + (S.sel.has(i) ? ' sel' : '') + (S.cur === i ? ' cur' : ''));
        const cb = document.createElement('input'); cb.type = 'checkbox'; cb.checked = S.sel.has(i);
        cb.onclick = ev2 => ev2.stopPropagation();
        cb.onchange = () => { cb.checked ? selKeys.add(keyOf(e)) : selKeys.delete(keyOf(e)); S.cur = i; S.anchor = i; drawRows(); drawFoot(); };
        const th = el('div', '', 'as-sp-th');
        const emoji = e.is_dir ? '📁' : ({ 'صور': '🖼️', 'فيديو': '🎬', 'صوت': '🎵', 'مستندات': '📄', 'جداول': '📊', 'أرشيف': '🗜️' }[spType(e)] || '📎');
        const tu = (!e.is_dir && typeof entryThumb === 'function') ? entryThumb(e.sid, e) : null;
        if (tu) { const im = el('img', '', '', { src: tu, alt: '', loading: 'lazy' }); im.onerror = () => { im.replaceWith(el('span', emoji)); }; th.appendChild(im); } else th.appendChild(el('span', emoji));
        const meta = el('div', '', 'as-sp-meta');
        meta.append(el('div', (e.is_dir ? '📁 ' : '') + e.name, 'as-sp-nm', { title: e.name }), el('div', (e.is_dir ? '' : safeFsize(e.size) + ' · ') + spSrcLabel(e.sid), 'as-sp-pt', { style: 'direction:rtl;text-align:right' }), el('div', e.folder || e.path, 'as-sp-pt'));
        const more = el('button', '⋯', 'as-sp-more', { title: 'خيارات', 'aria-label': 'خيارات هذه النتيجة' }); more.type = 'button';
        more.onclick = ev2 => { ev2.stopPropagation(); menuFor(S.sel.has(i) ? [...S.sel].sort((a, b) => a - b) : [i], more); };
        row.append(cb, th, meta, more);
        row.onclick = ev2 => {
          closeMenu(); card.focus();
          if (ev2.shiftKey && S.anchor >= 0) { const [a, b] = [Math.min(S.anchor, i), Math.max(S.anchor, i)]; for (let k = a; k <= b; k++) selKeys.add(keyOf(S.rows[k])); }
          else if (ev2.metaKey || ev2.ctrlKey) { selKeys.has(keyOf(e)) ? selKeys.delete(keyOf(e)) : selKeys.add(keyOf(e)); S.anchor = i; }
          else { selKeys.clear(); selKeys.add(keyOf(e)); S.anchor = i; }
          S.cur = i; drawRows(); drawFoot();
        };
        row.ondblclick = () => revealEntry(e);
        row.oncontextmenu = ev2 => { ev2.preventDefault(); if (!S.sel.has(i)) { selKeys.clear(); selKeys.add(keyOf(e)); S.cur = i; drawRows(); } menuFor(S.sel.has(i) ? [...S.sel].sort((a, b) => a - b) : [i], row); };
        list.append(row);
      });
      if (rows.length > 600) list.append(el('div', `يُعرض أول 600 من ${rows.length}؛ ضيّق بالتصفية.`, 'as-sp-pt', { style: 'padding:8px;text-align:center' }));
      list.querySelector('.cur')?.scrollIntoView({ block: 'nearest' });
    }
    function drawFoot(skipSync) {
      if (skipSync !== true) syncRefs();
      const n = S.sel.size;
      ft.replaceChildren();
      const cp = btn('انسخ المحدد إلى… (' + n + ')', () => copyEntries(itemsOf([...S.sel].sort((a, b) => a - b))), 'as-sp-b pri'); cp.disabled = !n;
      const all = btn('حدّد الكل (⌘A)', selectAll, 'as-sp-b');
      const clr = btn('ألغِ التحديد', () => { selKeys.clear(); drawRows(); drawFoot(); }, 'as-sp-b'); clr.disabled = !n;
      const mo = btn('⋯ المزيد', () => menuFor(chosen(), mo), 'as-sp-b'); mo.disabled = !chosen().length;
      const hint = el('span', n ? safeFsize(itemsOf([...S.sel]).reduce((a, e) => a + (e.size || 0), 0)) : 'اختصارات فقط — لا يُنسخ شيء إلا بطلبك · المسافة = معاينة', 'as-sp-pt', { style: 'flex:1;text-align:right' });
      ft.append(cp, all, clr, mo, hint);
    }
    function selectAll() { S.rows.forEach(e => selKeys.add(keyOf(e))); drawRows(); drawFoot(); card.focus(); }
    function drawHead() {
      const all = ents(), running = job.state === 'running';
      title.textContent = (running ? '⏳ ' : '') + 'نتائج البحث (' + all.length + (job.truncated ? '+' : '') + ')';
      sub.textContent = running ? 'تصل النتائج فور إيجادها…' : (job.seconds != null ? job.seconds + ' ث' : '');
      st.replaceChildren();
      Object.entries(job.sources || {}).forEach(([sid, s]) => {
        const tx = s.state === 'error' ? 'تعذّر — ' + (s.error || '') : s.state === 'timeout' ? 'تأخر (نتائج جزئية)' : s.state === 'slow' ? 'بطيء ' + s.seconds + ' ث' : s.state === 'running' && job.seconds > 10 ? 'ما زال يبحث…' : '';
        if (tx) st.append(el('span', '⚠ ' + spSrcLabel(sid) + ': ' + tx, 'as-sp-chip warn'));
      });
      st.hidden = !st.childElementCount;
      flt.replaceChildren();
      const chip = (label, n, on, f) => { const c = el('button', label + ' (' + n + ')', 'as-sp-chip' + (on ? ' on' : '')); c.type = 'button'; c.onclick = () => { f(); drawHead(); drawRows(); drawFoot(); }; flt.append(c); };
      chip('الكل', all.length, !S.src && !S.type, () => { S.src = S.type = ''; });
      [...new Set(all.map(e => e.sid))].forEach(sid => { if ([...new Set(all.map(e => e.sid))].length > 1) chip(spSrcLabel(sid), all.filter(e => e.sid === sid).length, S.src === sid, () => { S.src = S.src === sid ? '' : sid; }); });
      [...new Set(all.map(spType))].forEach(t => chip(t, all.filter(e => spType(e) === t).length, S.type === t, () => { S.type = S.type === t ? '' : t; }));
    }

    card.onkeydown = ev2 => {
      const k = ev2.key, mod = ev2.metaKey || ev2.ctrlKey;
      if (mod && k.toLowerCase() === 'a') { ev2.preventDefault(); selectAll(); }
      else if (mod && k.toLowerCase() === 'c') { const it = itemsOf(chosen()); if (it.length) { ev2.preventDefault(); copyText(it.map(e => e.path).join('\n'), 'نُسخت مسارات ' + it.length + ' عنصر.'); } }
      else if (k === ' ' && S.rows.length) { ev2.preventDefault(); previewEntries(S.rows, S.cur >= 0 ? S.cur : 0); }
      else if (k === 'ArrowDown' || k === 'ArrowUp') {
        ev2.preventDefault(); const n = Math.max(0, Math.min(S.rows.length - 1, (S.cur < 0 ? (k === 'ArrowDown' ? -1 : S.rows.length) : S.cur) + (k === 'ArrowDown' ? 1 : -1)));
        if (ev2.shiftKey && S.anchor >= 0) { const [a, b] = [Math.min(S.anchor, n), Math.max(S.anchor, n)]; selKeys.clear(); for (let q = a; q <= b; q++) selKeys.add(keyOf(S.rows[q])); }
        else { selKeys.clear(); if (S.rows[n]) selKeys.add(keyOf(S.rows[n])); S.anchor = n; }
        S.cur = n; drawRows(); drawFoot();
      }
      else if (k === 'Enter' && S.cur >= 0) { ev2.preventDefault(); revealEntry(S.rows[S.cur]); }
      else if (k.length === 1 && !mod && k !== ' ' && S.sel.size && inputEl) { inputEl.focus(); }   // الكتابة بعد التحديد تذهب لصندوق الرسالة
      else if (k === 'Escape') { if (menu) closeMenu(); else { selKeys.clear(); drawRows(); drawFoot(); } }
    };
    card.addEventListener('click', ev2 => { if (menu && !menu.contains(ev2.target)) closeMenu(); });

    drawHead(); drawRows(); drawFoot();
    chatContainer.appendChild(card);
    scrollToChatBottom(true);
    messages.push({ type: 'bot', element: card });
    trimMessages();

    // متابعة وصول النتائج إن لم ينته البحث
    for (let k = 0; k < 200 && job.state === 'running' && card.isConnected; k++) {
      await new Promise(r => setTimeout(r, 1500));
      try { job = await api('/api/search/job?id=' + encodeURIComponent(ev.search_id)); } catch (_) { break; }
      drawHead(); drawRows(); drawFoot();
    }
  }

  window.zajelSearchPanel = renderSearchPanel;   // للاختبار اليدوي من وحدة التحكم

  function renderResultCard(toolName, list) {
    if (!chatContainer) return;
    const card = el('div', '', 'as-result-card');
    const firstCount = Math.min(list.length, 8);
    const tTitle = (TOOL_NAMES[toolName] || toolName || 'نتائج') + ' (' + list.length + ')';
    const head = el('div', '', 'as-result-head');
    head.append(el('span', tTitle), createSvg('chevron-down', 14));

    const body = el('div', '', 'as-result-list');

    head.onclick = () => {
      body.hidden = !body.hidden;
      const svg = head.querySelector('svg');
      if (svg) {
        svg.style.transform = body.hidden ? 'rotate(90deg)' : 'none';
      }
    };

    list.slice(0, firstCount).forEach(item => {
      const row = el('div', '', 'as-result-item');
      const nameTxt = typeof item === 'string' ? item.split('/').pop() : (item.name || item.path || 'ملف');
      const nameEl = el('span', nameTxt, 'as-result-name');

      let sizeTxt = '';
      if (typeof item === 'object' && item.size != null) {
        sizeTxt = safeFsize(item.size);
      }
      const sizeEl = el('span', sizeTxt, 'as-result-size');
      row.append(nameEl, sizeEl);

      row.onclick = () => {
        const path = typeof item === 'string' ? item : item.path;
        const srcId = typeof item === 'object' ? (item.sid || item.src) : null;
        if (typeof P !== 'undefined' && P && typeof P.reveal === 'function' && srcId) {
          try {
            P.reveal(item, srcId);
            return;
          } catch (_) {}
        }
        if (path) {
          try {
            navigator.clipboard.writeText(path);
            safeNote('تم نسخ المسار: ' + path);
          } catch (_) {
            safeNote(path);
          }
        }
      };

      body.appendChild(row);
    });

    card.append(head, body);
    chatContainer.appendChild(card);
    scrollToChatBottom(true);
    messages.push({ type: 'bot', element: card });
    trimMessages();
  }

  /* ==========================================================================
     16. الأزرار الفورية (الحالة / العمليات / أوقف الكل)
     ========================================================================== */
  async function runQuick(action) {
    try {
      const res = await api('/api/assistant/quick', { action });
      if (action === 'status') {
        renderQuickStatusCard(res);
      } else if (action === 'ops') {
        renderQuickOpsCard(res);
      } else if (action === 'stop_all') {
        const ag = res?.agents_stopped ?? 0;
        const op = res?.ops_cancelled ?? 0;
        const pd = res?.pending_denied ?? 0;
        addMessage('sys', 'أُوقف الكل بنجاح: ' + ag + ' وكيل، ' + op + ' عملية، ' + pd + ' طلب موافقة.');
        if (currentJobId) {
          currentJobId = '';
          activeBotCard = null;
          if (stopBtn) stopBtn.disabled = true;
          updateSendButtonState();
        }
      }
    } catch (err) {
      addMessage('err', 'تعذر تنفيذ الإجراء: ' + (err.message || 'خطأ'));
    }
  }

  function renderQuickStatusCard(data) {
    if (!chatContainer) return;
    const card = el('div', '', 'as-msg as-msg-bot as-info-card');
    const title = el('div', '', 'as-running-head');
    title.append(createSvg('activity', 14), document.createTextNode('حالة نظام زاجل'));
    card.appendChild(title);

    const phoneRow = el('div', '', 'as-info-row');
    const phoneLbl = el('b', 'الهاتف:');
    const p = data?.phone;
    const pTxt = p?.connected ? (p.model || 'متصل') + (p.wifi ? ' (Wi-Fi)' : ' (USB)') : 'غير متصل';
    const phoneVal = el('span', pTxt);
    phoneRow.append(phoneLbl, phoneVal);
    card.appendChild(phoneRow);

    const volsRow = el('div', '', 'as-info-row');
    const volsLbl = el('b', 'الأقراص:');
    const vList = Array.isArray(data?.volumes) ? data.volumes : [];
    const volsVal = el('span', vList.length + ' قرص متصل');
    volsRow.append(volsLbl, volsVal);
    card.appendChild(volsRow);

    const opsRow = el('div', '', 'as-info-row');
    const opsLbl = el('b', 'العمليات:');
    const rOps = Array.isArray(data?.running_ops) ? data.running_ops : [];
    const opsVal = el('span', rOps.length + ' جارية');
    opsRow.append(opsLbl, opsVal);
    card.appendChild(opsRow);

    const syncRow = el('div', '', 'as-info-row');
    const syncLbl = el('b', 'المزامنات:');
    const sList = Array.isArray(data?.syncs) ? data.syncs : [];
    const syncVal = el('span', sList.length + ' محفوظة');
    syncRow.append(syncLbl, syncVal);
    card.appendChild(syncRow);

    chatContainer.appendChild(card);
    scrollToChatBottom(true);
    messages.push({ type: 'bot', element: card });
    trimMessages();

    rOps.forEach(o => {
      if (o && o.id) trackOp(o.id);
    });
  }

  function renderQuickOpsCard(data) {
    if (!chatContainer) return;
    const card = el('div', '', 'as-msg as-msg-bot as-info-card');
    const title = el('div', '', 'as-running-head');
    title.append(createSvg('layers', 14), document.createTextNode('العمليات الأخيرة'));
    card.appendChild(title);

    const ops = Array.isArray(data?.ops) ? data.ops : [];
    const running = ops.filter(o => o.state === 'running');

    const summaryRow = el('div', '', 'as-info-row');
    summaryRow.append(el('b', 'الملخص:'), el('span', ops.length + ' إجمالي (' + running.length + ' جارية)'));
    card.appendChild(summaryRow);

    const recent = ops.slice(-4).reverse();
    recent.forEach(o => {
      const row = el('div', '', 'as-info-row');
      const oName = el('span', (o.title || o.id || 'عملية'));
      oName.style.overflow = 'hidden';
      oName.style.textOverflow = 'ellipsis';
      oName.style.whiteSpace = 'nowrap';
      const oState = el('span', (o.state === 'running' ? 'جارية' : o.state === 'done' ? 'مكتملة' : o.state));
      oState.style.color = o.state === 'running' ? 'var(--acc)' : o.state === 'done' ? 'var(--ok)' : 'var(--mut)';
      row.append(oName, oState);
      card.appendChild(row);
      if (o.state === 'running' && o.id) {
        trackOp(o.id);
      }
    });

    chatContainer.appendChild(card);
    scrollToChatBottom(true);
    messages.push({ type: 'bot', element: card });
    trimMessages();
  }

  /* ==========================================================================
     17. بطاقات الموافقة المعلقة (أعلى المحادثة مع الطي بعدّادها)
     ========================================================================== */
  function schedulePendingPoll() {
    clearTimeout(pendingPollTimer);
    const delay = isOpen ? 2000 : 8000;
    pendingPollTimer = setTimeout(pollPending, delay);
  }

  async function pollPending() {
    clearTimeout(pendingPollTimer);
    try {
      const data = await api('/api/assistant/pending');
      const list = Array.isArray(data?.pending) ? data.pending : [];

      let hasNew = false;
      list.forEach(p => {
        if (!lastKnownPendingIds.has(p.id)) {
          hasNew = true;
        }
      });

      if (hasNew && !isOpen) {
        togglePanel(true);
        if (chipEl) chipEl.classList.add('as-alert');
      }

      lastKnownPendingIds = new Set(list.map(p => p.id));
      renderPendingArea(list);
      updateFloatingBadgeState();
    } catch (_) {
      // تجاهل أخطاء الشبكة المؤقتة
    } finally {
      schedulePendingPoll();
    }
  }

  function renderPendingArea(list) {
    if (!pendingArea || !pendingListWrap) return;
    if (list.length === 0) {
      pendingArea.hidden = true;
      renderedPendingCards.forEach(c => {
        clearInterval(c.timerInterval);
        c.element.remove();
      });
      renderedPendingCards.clear();
      return;
    }

    pendingArea.hidden = false;

    // شريط الرأس القابل للطي إن كثرت البطاقات
    if (list.length > 1) {
      pendingToggleRow.hidden = false;
      pendingToggleRow.replaceChildren(
        el('span', 'طلبات موافقة معلقة (' + list.length + ')'),
        createSvg('chevron-down', 13)
      );
      pendingToggleRow.onclick = () => {
        pendingListWrap.hidden = !pendingListWrap.hidden;
      };
    } else {
      pendingToggleRow.hidden = true;
      pendingListWrap.hidden = false;
    }

    const currentIds = new Set(list.map(x => x.id));

    renderedPendingCards.forEach((c, id) => {
      if (!currentIds.has(id)) {
        clearInterval(c.timerInterval);
        c.element.remove();
        renderedPendingCards.delete(id);
      }
    });

    list.forEach(item => {
      if (renderedPendingCards.has(item.id)) {
        const c = renderedPendingCards.get(item.id);
        c.updateExpiry(item.expires_in);
      } else {
        const cardObj = createPendingCard(item);
        renderedPendingCards.set(item.id, cardObj);
        pendingListWrap.appendChild(cardObj.element);
      }
    });
  }

  function createPendingCard(item) {
    const card = el('div', '', 'as-card-pending');
    const head = el('div', '', 'as-pending-head');

    const pTitle = el('span', '', 'as-pending-title');
    pTitle.append(
      createSvg('shield-alert', 14),
      document.createTextNode(item.preview?.title || TOOL_NAMES[item.tool] || item.tool || 'طلب موافقة')
    );

    const timerEl = el('span', '00:00', 'as-pending-timer');
    head.append(pTitle, timerEl);

    const body = el('div', '', 'as-pending-body');
    const pv = item.preview || {};

    if (pv.count != null) {
      const r = el('div', '', 'as-pending-row');
      r.append(el('b', 'عدد العناصر: '), el('span', String(pv.count)));
      body.appendChild(r);
    }
    if (pv.bytes != null) {
      const r = el('div', '', 'as-pending-row');
      r.append(el('b', 'الحجم: '), el('span', safeFsize(pv.bytes)));
      body.appendChild(r);
    }
    if (pv.from) {
      const r = el('div', '', 'as-pending-row');
      r.append(el('b', 'من: '), el('span', String(pv.from)));
      body.appendChild(r);
    }
    if (pv.to) {
      const r = el('div', '', 'as-pending-row');
      r.append(el('b', 'إلى: '), el('span', String(pv.to)));
      body.appendChild(r);
    }
    if (Array.isArray(pv.items) && pv.items.length > 0) {
      const r = el('div', '', 'as-pending-row');
      r.append(el('b', 'العناصر: '), el('span', pv.items.slice(0, 4).join('، ') + (pv.items.length > 4 ? '…' : '')));
      body.appendChild(r);
    }
    if (Array.isArray(pv.renames) && pv.renames.length > 0) {
      const r = el('div', '', 'as-pending-row');
      const txt = pv.renames.slice(0, 3).map(x => (x.from ? x.from.split('/').pop() : '') + ' ← ' + (x.to || '')).join(' | ');
      r.append(el('b', 'إعادة التسمية: '), el('span', txt));
      body.appendChild(r);
    }
    if (pv.target) {
      const r = el('div', '', 'as-pending-row');
      r.append(el('b', 'الهدف: '), el('span', String(pv.target)));
      body.appendChild(r);
    }
    if (Array.isArray(pv.places) && pv.places.length > 0) {
      const r = el('div', '', 'as-pending-row');
      r.append(el('b', 'الأماكن: '), el('span', pv.places.join(' ، ')));
      body.appendChild(r);
    }
    if (pv.script) {
      const sc = pv.script;
      if (sc.description) {
        const r = el('div', '', 'as-pending-row');
        r.append(el('b', 'ماذا يفعل: '), el('span', String(sc.description)));
        body.appendChild(r);
      }
      if (Array.isArray(sc.flags) && sc.flags.length) {
        const r = el('div', '', 'as-pending-row');
        r.style.color = '#c4382b';
        r.append(el('b', '⚠ تنبيه: '), el('span', sc.flags.join('، ')));
        body.appendChild(r);
      }
      (sc.params || []).forEach(q => {
        const r = el('div', '', 'as-pending-row');
        r.append(el('b', q.label + ': '), el('span', String(q.value)));
        body.appendChild(r);
      });
      const det = document.createElement('details');
      det.open = true;
      const sum = document.createElement('summary');
      sum.textContent = 'نصّ الكود (اقرأه قبل الموافقة)';
      const pre = document.createElement('pre');
      pre.textContent = String(sc.code || '');
      pre.style.cssText = 'max-height:220px;overflow:auto;direction:ltr;text-align:left;font-size:11.5px;background:rgba(127,127,127,.12);padding:8px;border-radius:8px;white-space:pre-wrap;margin:6px 0 0';
      det.append(sum, pre);
      body.appendChild(det);
    }
    if (pv.note) {
      const r = el('div', '', 'as-pending-row');
      r.append(el('b', 'ملاحظة: '), el('span', String(pv.note)));
      body.appendChild(r);
    }

    let wordInp = null;
    if (item.needs_word) {
      const wordBox = el('div', '', 'as-word-box');
      wordInp = el('input', '', 'as-word-input', {
        placeholder: 'اكتب كلمة التأكيد: «' + item.needs_word + '»'
      });
      wordBox.appendChild(wordInp);
      body.appendChild(wordBox);
    }

    const cardErr = el('div', '', 'as-card-err');
    cardErr.hidden = true;

    const actions = el('div', '', 'as-pending-actions');
    const approveBtn = btn('✔ موافقة', async () => {
      approveBtn.disabled = true;
      cardErr.hidden = true;
      try {
        const word = wordInp ? wordInp.value.trim() : '';
        const res = await api('/api/assistant/approve', { id: item.id, word });

        clearInterval(timerInterval);
        card.remove();
        renderedPendingCards.delete(item.id);

        addMessage('sys', 'تمت الموافقة بنجاح على العملية.');

        const opId = res?.result?.id || res?.id;
        if (opId) trackOp(opId);
        if (Array.isArray(res?.result?.ops)) {
          res.result.ops.forEach(o => {
            if (o && o.id) trackOp(o.id);
          });
        }
      } catch (err) {
        cardErr.textContent = err.message || 'فشلت الموافقة';
        cardErr.hidden = false;
        approveBtn.disabled = wordInp ? (wordInp.value.trim() !== item.needs_word) : false;
      }
    }, 'btn pri as-approve-btn');

    const denyBtn = btn('✖ رفض', async () => {
      denyBtn.disabled = true;
      cardErr.hidden = true;
      try {
        await api('/api/assistant/deny', { id: item.id });
        clearInterval(timerInterval);
        card.remove();
        renderedPendingCards.delete(item.id);
        addMessage('sys', 'رُفض طلب العملية.');
      } catch (err) {
        cardErr.textContent = err.message || 'فشل الرفض';
        cardErr.hidden = false;
        denyBtn.disabled = false;
      }
    }, 'btn as-deny-btn');

    if (item.needs_word) {
      approveBtn.disabled = true;
      wordInp.oninput = () => {
        approveBtn.disabled = (wordInp.value.trim() !== item.needs_word);
      };
    }

    actions.append(approveBtn, denyBtn);
    card.append(head, body, cardErr, actions);

    let expiresAt = Date.now() + Math.max(0, (item.expires_in || 600)) * 1000;

    function updateTimerDisplay() {
      const leftSec = Math.max(0, Math.round((expiresAt - Date.now()) / 1000));
      const mm = String(Math.floor(leftSec / 60)).padStart(2, '0');
      const ss = String(leftSec % 60).padStart(2, '0');
      timerEl.textContent = mm + ':' + ss;
      if (leftSec <= 0) {
        clearInterval(timerInterval);
        card.remove();
        renderedPendingCards.delete(item.id);
      }
    }

    const timerInterval = setInterval(updateTimerDisplay, 1000);
    updateTimerDisplay();

    return {
      element: card,
      timerInterval,
      updateExpiry(newSec) {
        if (typeof newSec === 'number') {
          expiresAt = Date.now() + Math.max(0, newSec) * 1000;
          updateTimerDisplay();
        }
      }
    };
  }

  /* ==========================================================================
     18. شريط التقدم للعمليات الطويلة
     ========================================================================== */
  function trackOp(opId) {
    if (!opId || trackedOps.has(opId) || !chatContainer) return;
    trackedOps.add(opId);

    const card = el('div', '', 'as-op-card');
    const head = el('div', '', 'as-op-head');
    const title = el('span', 'عملية: ' + opId, 'as-op-title');
    const cancelBtn = btn('⏹ أوقف', async () => {
      cancelBtn.disabled = true;
      try {
        await api('/api/ops/cancel', { id: opId });
        safeNote('تم طلب إيقاف العملية ' + opId);
      } catch (err) {
        safeNote(err.message || 'تعذر الإيقاف');
      }
    }, 'btn');
    cancelBtn.style.fontSize = '11px';
    cancelBtn.style.padding = '2px 7px';

    head.append(title, cancelBtn);

    const pbar = el('div', '', 'as-op-pbar');
    const fill = el('div', '', 'as-op-pbar-fill');
    pbar.appendChild(fill);

    const details = el('div', '', 'as-op-details');
    const statText = el('span', 'جارٍ البدء…');
    details.appendChild(statText);

    const currText = el('div', '', 'as-op-curr');

    card.append(head, pbar, details, currText);
    chatContainer.appendChild(card);
    scrollToChatBottom(true);
    messages.push({ type: 'bot', element: card });
    trimMessages();

    const pollTimer = setInterval(async () => {
      try {
        const d = await api('/api/ops/get?id=' + encodeURIComponent(opId));
        if (!d) return;

        if (d.title) title.textContent = d.title;

        let pct = 0;
        if (d.bytes_total > 0) {
          pct = Math.min(100, Math.round(((d.bytes_done || 0) / d.bytes_total) * 100));
        } else if (d.total > 0) {
          pct = Math.min(100, Math.round(((d.done || 0) / d.total) * 100));
        }
        fill.style.width = pct + '%';

        let countStr = '';
        if (d.total > 0) {
          countStr = (d.done || 0) + ' من ' + d.total;
        }
        if (d.bytes_total > 0) {
          countStr += (countStr ? ' (' : '') + safeFsize(d.bytes_done || 0) + ' من ' + safeFsize(d.bytes_total) + (countStr ? ')' : '');
        }

        let extraStr = pct + '%';
        if (d.speed > 0) {
          extraStr += ' • ' + safeFsize(d.speed) + '/ث';
        }
        if (d.eta != null && d.eta > 0) {
          const m = Math.floor(d.eta / 60);
          const s = d.eta % 60;
          extraStr += ' • متبقي: ' + (m > 0 ? (m + ' د ') : '') + s + ' ث';
        }

        statText.textContent = countStr ? (countStr + ' — ' + extraStr) : extraStr;

        if (d.current) {
          currText.textContent = d.current;
        }

        if (d.state !== 'running') {
          clearInterval(pollTimer);
          cancelBtn.remove();
          if (d.state === 'done') {
            fill.style.width = '100%';
            fill.style.background = 'var(--ok)';
            statText.textContent = 'اكتملت بنجاح' + (countStr ? ': ' + countStr : '');
          } else if (d.state === 'error') {
            fill.style.background = 'var(--err)';
            statText.textContent = 'خطأ: ' + (d.errors?.[0] || 'توقفت العملية');
          } else {
            fill.style.background = 'var(--warn)';
            statText.textContent = 'أُوقفت العملية';
          }
        }
      } catch (_) {
        // تجاهل أخطاء الشبكة المؤقتة
      }
    }, 1000);
  }

  /* ==========================================================================
     19. بناء هيكل الواجهة وتركيبه
     ========================================================================== */
  function buildAssistantUI() {
    // 1. زر الشريحة في الشريط العلوي .top
    const topBar = document.querySelector('.top');
    if (topBar && !document.getElementById('as-chip')) {
      chipEl = el('span', '', 'chip', {
        id: 'as-chip',
        title: 'فتح نافذة المساعد الذكي',
        role: 'button',
        tabindex: '0',
        'aria-label': 'فتح نافذة المساعد الذكي'
      });
      chipEl.append(createSvg('bot', 15), document.createTextNode(' المساعد'));
      chipEl.onclick = () => togglePanel();
      chipEl.onkeydown = (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          togglePanel();
        }
      };

      const vclean = document.getElementById('vclean');
      if (vclean && vclean.parentNode === topBar) {
        topBar.insertBefore(chipEl, vclean);
      } else {
        topBar.appendChild(chipEl);
      }
      controlChipEl = el('span', '', 'chip', { id: 'zajel-control-chip', title: 'مركز التحكم', role: 'button', tabindex: '0', 'aria-label': 'مركز التحكم' });
      controlChipEl.append(createSvg('settings', 15), document.createTextNode(' مركز التحكم'));
      controlChipEl.onclick = () => { if (controlPanelEl) { controlPanelEl.hidden = !controlPanelEl.hidden; controlPanelEl.style.display = controlPanelEl.hidden ? 'none' : 'flex'; if (controlPanelEl.hidden) { stopAutomationsPolling(); stopAgentsPolling(); window.ZajelTerminalUI?.deactivate?.(); } } if (controlPanelEl && !controlPanelEl.hidden) switchControlTab(controlActiveTab); };
      controlChipEl.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); controlChipEl.click(); } };
      topBar.insertBefore(controlChipEl, vclean && vclean.parentNode === topBar ? vclean : null);
    }

    // 2. النافذة الجانبية الكاملة
    panelEl = el('aside', '', 'as-panel' + (isExpanded ? ' as-expanded' : ''), {
      id: 'as-panel',
      role: 'region',
      'aria-label': 'المساعد الذكي لزاجل'
    });
    panelEl.hidden = true;

    // النسخ عند التحديد: أي نص تحدده داخل المساعد يُنسخ فورًا إلى الحافظة مع علامة «نُسخ» خفيفة (لا رسالة منبثقة)
    let lastCopied = '', lastCopiedAt = 0, copyTipTimer = null, copyTip = null;
    const showCopyTip = () => {
      if (!copyTip) {
        copyTip = el('div', '✓ نُسخ');
        copyTip.style.cssText = 'position:absolute;bottom:74px;left:50%;transform:translateX(-50%);background:rgba(30,30,30,.88);color:#fff;font-size:12px;padding:4px 12px;border-radius:14px;pointer-events:none;transition:opacity .25s;z-index:5';
        panelEl.appendChild(copyTip);
      }
      copyTip.style.opacity = '1';
      clearTimeout(copyTipTimer);
      copyTipTimer = setTimeout(() => { if (copyTip) copyTip.style.opacity = '0'; }, 1100);
    };
    const copySelection = () => {
      let on = true;
      try { on = localStorage.getItem('zajel_as_copy_on_select') !== '0'; } catch (_) {}
      if (!on) return;
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed) return;
      const node = sel.anchorNode && (sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentElement);
      if (!node || !panelEl.contains(node) || node.closest('input,textarea,button')) return;
      const text = sel.toString().trim();
      if (text.length < 2 || (text === lastCopied && Date.now() - lastCopiedAt < 1500)) return;
      lastCopied = text;
      lastCopiedAt = Date.now();
      const fallback = () => {
        try {
          const ta = document.createElement('textarea');
          ta.value = text;
          ta.style.cssText = 'position:fixed;opacity:0;top:0;left:0';
          document.body.appendChild(ta);
          ta.select();
          document.execCommand('copy');
          ta.remove();
          sel.removeAllRanges();
        } catch (_) {}
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(showCopyTip).catch(() => { fallback(); showCopyTip(); });
      } else {
        fallback();
        showCopyTip();
      }
    };
    panelEl.addEventListener('mouseup', () => setTimeout(copySelection, 15));
    panelEl.addEventListener('touchend', () => setTimeout(copySelection, 250));

    // تظليل السحب والإفلات للملفات فوق اللوحة (المهمة B)
    dragOverlayEl = el('div', '', 'as-drag-overlay', { 'aria-hidden': 'true' });
    dragOverlayEl.hidden = true;
    const dragIco = el('div', '', 'as-drag-overlay-ico');
    dragIco.appendChild(createSvg('clip', 36));
    const dragText = el('div', 'أفلت الملفات هنا لإرفاقها', 'as-drag-overlay-text');
    dragOverlayEl.append(dragIco, dragText);
    panelEl.appendChild(dragOverlayEl);

    // السحب والإفلات: أفلت مجلدًا أو ملفًا أو جهازًا أو سحابة أو قرصًا من زاجل على اللوحة فيدخل مكانه ومساره في الرسالة
    const zajelDrag = ev => Array.from(ev.dataTransfer?.types || []).includes('application/x-zajel');
    panelEl.addEventListener('dragover', ev => {
      if (zajelDrag(ev)) {
        ev.preventDefault();
        ev.dataTransfer.dropEffect = 'copy';
        panelEl.style.outline = '2px dashed #0a84ff';
        panelEl.style.outlineOffset = '-6px';
        if (dragOverlayEl) dragOverlayEl.hidden = true;
        return;
      }
      const types = Array.from(ev.dataTransfer?.types || []);
      if (types.includes('Files')) {
        ev.preventDefault();
        ev.dataTransfer.dropEffect = 'copy';
        if (dragOverlayEl) dragOverlayEl.hidden = false;
      }
    });
    panelEl.addEventListener('dragleave', ev => {
      if (!panelEl.contains(ev.relatedTarget)) {
        panelEl.style.outline = '';
        if (dragOverlayEl) dragOverlayEl.hidden = true;
      }
    });
    panelEl.addEventListener('drop', ev => {
      if (dragOverlayEl) dragOverlayEl.hidden = true;
      if (zajelDrag(ev)) {
        ev.preventDefault();
        ev.stopPropagation();
        panelEl.style.outline = '';
        let items = [];
        try { items = JSON.parse(ev.dataTransfer.getData('application/x-zajel')).items || []; } catch (_) { return; }
        if (!items.length) return;
        const kind = it => it.source ? 'المكان' : it.is_dir === true ? 'المجلد' : it.is_dir === false ? 'الملف' : 'العنصر';
        const line = it => `${kind(it)} «${it.name}» (place: ${it.place}${it.path ? ', path: ' + it.path : ''})`;
        const shown = items.slice(0, 12).map(line);
        const more = items.length > 12 ? ` و${items.length - 12} عنصرًا آخر` : '';
        const piece = shown.join('\n') + more;
        const cur = inputEl ? inputEl.value.trim() : '';
        fillInput((cur ? cur + '\n' : '') + piece + '\n');
        return;
      }
      const types = Array.from(ev.dataTransfer?.types || []);
      if (types.includes('Files') || (ev.dataTransfer?.files && ev.dataTransfer.files.length > 0)) {
        ev.preventDefault();
        ev.stopPropagation();
        panelEl.style.outline = '';
        const files = Array.from(ev.dataTransfer.files || []);
        if (files.length > 0) {
          handleFilesAdded(files);
        }
      }
    });

    // مقبض سحب الحافة لتغيير عرض النافذة
    gripEl = el('div', '', 'as-resize-grip', {
      title: 'اسحب لتغيير العرض · نقر مزدوج لإعادة العرض الافتراضي',
      'aria-label': 'مقبض سحب تغيير الحجم'
    });
    gripEl.ondblclick = () => {
      setPanelWidth(DEFAULT_PANEL_WIDTH);
    };

    let isPointerDragging = false;
    gripEl.onpointerdown = (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      gripEl.setPointerCapture(ev.pointerId);
      isPointerDragging = true;
      gripEl.classList.add('is-dragging');
      panelEl.classList.add('as-resizing');
      document.body.classList.add('as-resizing-active');

      const onpointermove = (e2) => {
        if (!isPointerDragging) return;
        const r = panelEl.getBoundingClientRect();
        const isRightAligned = Math.abs(r.right - window.innerWidth) < Math.abs(r.left);
        const rawW = isRightAligned ? (window.innerWidth - e2.clientX) : e2.clientX;


        const maxW = Math.min(1200, Math.floor(window.innerWidth * 0.96));
        const finalW = Math.max(MIN_PANEL_WIDTH, Math.min(maxW, Math.round(rawW)));
        panelEl.style.width = finalW + 'px';
        panelWidth = finalW;
      };

      const endDrag = (pointerId) => {
        if (!isPointerDragging) return;
        isPointerDragging = false;
        try { gripEl.releasePointerCapture(pointerId); } catch (_) {}
        gripEl.classList.remove('is-dragging');
        panelEl.classList.remove('as-resizing');
        document.body.classList.remove('as-resizing-active');
        gripEl.onpointermove = null;
        gripEl.onpointerup = null;
        gripEl.onpointercancel = null;
        try { localStorage.setItem('zajel_as_width', String(panelWidth)); } catch (_) {}
      };

      gripEl.onpointermove = onpointermove;
      gripEl.onpointerup = (e) => endDrag(e.pointerId);
      gripEl.onpointercancel = (e) => endDrag(e.pointerId);
    };

    panelEl.appendChild(gripEl);

    // زر دائري صغير عائم يظهر عند التصغير
    floatingBtn = el('button', '', 'as-floating-btn', {
      id: 'as-floating-btn',
      title: 'فتح المساعد الذكي',
      'aria-label': 'فتح نافذة المساعد الذكي',
      type: 'button'
    });
    floatingBtn.hidden = true;
    floatingBtn.appendChild(createSvg('bot', 20));
    floatingBtn.onclick = () => {
      floatingBtn.hidden = true;
      togglePanel(true);
    };
    document.body.appendChild(floatingBtn);

    // (أ) الترويسة سطر واحد رفيع ونظيف
    const head = el('header', '', 'as-head');

    // زر الشريط الجانبي ☰ في أقصى اليمين RTL
    const headStart = el('div', '', 'as-head-start');
    const menuBtn = el('button', '', 'as-icon-btn', {
      title: 'الشريط الجانبي (☰)',
      'aria-label': 'فتح/طي الشريط الجانبي'
    });
    menuBtn.appendChild(createSvg('menu', 16));
    menuBtn.onclick = () => toggleSidebar();
    headStart.appendChild(menuBtn);

    // شارة المصدر والنموذج قابلة للنقر لفتح الإعدادات
    const sourceBadge = el('div', '', 'as-source-badge', {
      role: 'button',
      tabindex: '0',
      'aria-label': 'إعدادات وتبديل المصدر والنموذج'
    });
    sourceBadgeText = el('span', 'Antigravity · flash', 'as-source-text');
    const badgeArrow = el('span', '', 'as-badge-arrow');
    badgeArrow.appendChild(createSvg('chevron-down', 13));
    sourceBadge.append(sourceBadgeText, badgeArrow);
    sourceBadge.onclick = () => switchTab('settings');
    sourceBadge.onkeydown = (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        switchTab('settings');
      }
    };

    // إجراءات الترويسة في اليسار
    const headActions = el('div', '', 'as-head-actions');

    const newChatBtn = el('button', '', 'as-icon-btn', {
      title: 'بدء محادثة جديدة',
      'aria-label': 'بدء محادثة جديدة'
    });
    newChatBtn.appendChild(createSvg('plus', 16));
    newChatBtn.onclick = () => newChat();

    minimizeBtn = el('button', '', 'as-icon-btn', {
      title: 'إخفاء المساعد إلى زر عائم (لتغيير العرض استعمل السهمين بجانبه أو اسحب الحافة)',
      'aria-label': 'إخفاء المساعد إلى زر عائم'
    });
    minimizeBtn.appendChild(el('span', '—', 'as-min-dash'));
    minimizeBtn.onclick = () => minimizeToFloatingBadge();

    expandBtn = el('button', '', 'as-icon-btn', {
      title: isExpanded ? 'استعادة العرض الافتراضي' : 'توسيع العرض',
      'aria-label': 'توسيع/تصغير النافذة'
    });
    expandBtn.appendChild(createSvg(isExpanded ? 'minimize' : 'maximize', 15));
    expandBtn.onclick = () => toggleExpand();

    const closeBtn = el('button', '', 'as-icon-btn', {
      title: 'إغلاق نافذة المساعد (Esc)',
      'aria-label': 'إغلاق النافذة'
    });
    closeBtn.appendChild(createSvg('close', 15));
    closeBtn.onclick = () => togglePanel(false);

    floatBtn = el('button', '', 'as-icon-btn', {
      title: 'تحويل المساعد إلى نافذة عائمة',
      'aria-label': 'نافذة عائمة'
    });
    floatBtn.appendChild(el('span', '⧉', 'as-min-dash'));
    floatBtn.onclick = () => setFloating(!isFloating);

    headActions.append(newChatBtn, floatBtn, minimizeBtn, expandBtn, closeBtn);
    head.append(headStart, sourceBadge, headActions);

    // (ب) جسم النافذة: الشريط الجانبي + المنطقة الرئيسية
    const bodyLayout = el('div', '', 'as-body-layout');

    // الشريط الجانبي
    sidebarEl = el('aside', '', 'as-sidebar' + (isSidebarOpen ? '' : ' as-sidebar-closed'), {
      id: 'as-sidebar',
      'aria-label': 'أقسام المساعد الجانبية'
    });
    sidebarEl.style.width = sidebarWidth + 'px';
    const sideGrip = el('div', '', 'as-sidebar-grip', { title: 'اسحب لتغيير عرض الشريط الجانبي · نقر مزدوج للافتراضي' });
    sideGrip.ondblclick = () => {
      sidebarWidth = 300;
      sidebarEl.style.width = '300px';
      try { localStorage.setItem('zajel_as_sidebar_w', '300'); } catch (_) {}
      if (panelEl && panelEl.__markNarrow) panelEl.__markNarrow();
    };
    sideGrip.onpointerdown = ev => {
      ev.preventDefault();
      ev.stopPropagation();
      sideGrip.setPointerCapture(ev.pointerId);
      sideGrip.classList.add('is-dragging');
      panelEl.classList.add('as-resizing');
      const right = sidebarEl.getBoundingClientRect().right;
      sideGrip.onpointermove = e2 => {
        sidebarWidth = Math.max(MIN_SIDEBAR_WIDTH, Math.min(MAX_SIDEBAR_WIDTH, Math.round(right - e2.clientX)));
        sidebarEl.style.width = sidebarWidth + 'px';
        if (panelEl.__markNarrow) panelEl.__markNarrow();
      };
      const stop = e3 => {
        try { sideGrip.releasePointerCapture(e3.pointerId); } catch (_) {}
        sideGrip.classList.remove('is-dragging');
        panelEl.classList.remove('as-resizing');
        sideGrip.onpointermove = sideGrip.onpointerup = sideGrip.onpointercancel = null;
        try { localStorage.setItem('zajel_as_sidebar_w', String(sidebarWidth)); } catch (_) {}
      };
      sideGrip.onpointerup = stop;
      sideGrip.onpointercancel = stop;
    };

    sideTabsNav = el('nav', '', 'as-side-tabs');
    const tabsConfig = [
      { key: 'chats', title: 'المحادثات', icon: 'chat' },
      { key: 'memory', title: 'الذاكرة', icon: 'brain' },
      { key: 'prompts', title: 'الأوامر', icon: 'spark' }
    ];

    tabsConfig.forEach(t => {
      const tabBtn = el('button', '', 'as-tab-btn' + (t.key === activeTab ? ' as-active-tab' : ''), {
        type: 'button',
        title: t.title,
        'data-tab': t.key
      });
      tabBtn.append(createSvg(t.icon, 15), document.createTextNode(t.title));
      if (t.key === 'automations') {
        automationsTabBadge = el('span', '', 'as-tab-unread-badge');
        automationsTabBadge.hidden = true;
        tabBtn.appendChild(automationsTabBadge);
      }
      tabBtn.onclick = () => switchTab(t.key);
      sideTabsNav.appendChild(tabBtn);
    });

    sideContentEl = el('div', '', 'as-side-content');
    assistantContentEl = sideContentEl;
    sidebarEl.append(sideTabsNav, sideContentEl, sideGrip);

    controlPanelEl = el('aside', '', 'as-panel as-control-panel', { id: 'zajel-control-panel', role: 'region', 'aria-label': 'مركز التحكم' });
    controlPanelEl.hidden = true;
    controlPanelEl.style.display = 'none';
    controlPanelEl.style.cssText = 'position:fixed;inset:12px 12px 12px auto;z-index:10001;display:flex;flex-direction:column;width:min(760px,96vw);max-height:calc(100vh - 24px);background:var(--bg);box-shadow:0 8px 40px #0005;border-radius:12px;overflow:hidden';
    const controlHead = el('header', '', 'as-head');
    controlHead.append(el('strong', 'مركز التحكم', 'as-head-title'));
    const closeControl = el('button', '', 'as-icon-btn', { type: 'button', title: 'إغلاق مركز التحكم', 'aria-label': 'إغلاق مركز التحكم' });
    closeControl.appendChild(createSvg('close', 15)); closeControl.onclick = () => { controlPanelEl.hidden = true; controlPanelEl.style.display = 'none'; stopAutomationsPolling(); stopAgentsPolling(); window.ZajelTerminalUI?.deactivate?.(); };
    controlHead.appendChild(closeControl);
    const controlBody = el('div', '', 'as-body-layout');
    const controlSide = el('aside', '', 'as-sidebar');
    controlTabsNav = el('nav', '', 'as-side-tabs');
    [ ['settings','الإعدادات','settings'], ['agents','الوكلاء','activity'], ['automations','الأتمتة','activity'], ['scripts','المكتبة','layers'], ['terminal','الطرفية','activity'] ].forEach(([key,title,icon]) => {
      const tab = el('button', '', 'as-tab-btn', { type:'button', title, 'data-tab':key });
      tab.append(createSvg(icon,15), document.createTextNode(title));
      if (key === 'automations') { controlAutomationBadge = el('span','','as-tab-unread-badge'); controlAutomationBadge.hidden = true; tab.appendChild(controlAutomationBadge); }
      tab.onclick = () => switchControlTab(key); controlTabsNav.appendChild(tab);
    });
    controlContentEl = el('div','','as-side-content');
    controlSide.append(controlTabsNav, controlContentEl);
    controlSide.style.cssText = 'flex:1 1 auto;width:100%;max-width:none;min-width:0;border:0';
    controlBody.style.cssText = 'display:flex;flex:1;min-height:0';
    controlBody.append(controlSide);
    controlPanelEl.append(controlHead, controlBody);
    document.body.appendChild(controlPanelEl);

    // المنطقة الرئيسية
    const mainArea = el('main', '', 'as-main');

    // بطاقات الموافقة المعلقة أعلى المحادثة
    pendingArea = el('div', '', 'as-pending-area');
    pendingArea.hidden = true;
    pendingToggleRow = el('div', '', 'as-pending-toggle-row');
    pendingToggleRow.hidden = true;
    pendingListWrap = el('div', '');
    pendingListWrap.style.display = 'flex';
    pendingListWrap.style.flexDirection = 'column';
    pendingListWrap.style.gap = '6px';
    pendingArea.append(pendingToggleRow, pendingListWrap);

    // منطقة المحادثة الواسعة
    chatContainer = el('div', '', 'as-chat', {
      role: 'log',
      'aria-live': 'polite'
    });
    chatContainer.onscroll = () => checkScrollPosition();

    // الحالة الترحيبية الفارغة مع الاقتراحات
    emptyStateEl = el('div', '', 'as-empty-state');
    const emptyIcon = el('div', '', 'as-empty-icon');
    emptyIcon.appendChild(createSvg('bot', 26));

    const emptyTitle = el('div', 'مساعد زاجل الذكي', 'as-empty-title');
    const emptyDesc = el('div', 'مرحباً بك! تصفح ملفاتك ومزامنتها والبحث المتقدم بأمان، مع شريط جانبي وسجل ذاكرة وأوامر سريعة.', 'as-empty-desc');

    const suggestionsGrid = el('div', '', 'as-suggestions-grid');
    const suggestions = [
      'ابحث عن …',
      'ما حالة العمليات؟',
      'كم المساحة المتبقية؟',
      'زامن هذا المجلد مع …'
    ];
    suggestions.forEach(sug => {
      const chip = el('button', '', 'as-suggestion-chip', { type: 'button' });
      chip.append(el('span', sug), createSvg('plus', 13));
      chip.onclick = () => fillInput(sug);
      suggestionsGrid.appendChild(chip);
    });

    emptyStateEl.append(emptyIcon, emptyTitle, emptyDesc, suggestionsGrid);
    chatContainer.appendChild(emptyStateEl);

    // الزر العائم للتمرير إلى الأسفل
    scrollBottomBtn = el('button', '', 'as-scroll-bottom', {
      type: 'button',
      title: 'التمرير إلى نهاية المحادثة'
    });
    scrollBottomBtn.appendChild(createSvg('arrow-down', 16));
    scrollBottomBtn.hidden = true;
    scrollBottomBtn.onclick = () => scrollToChatBottom(true);

    // شارة سياق المجلد الصغير ونطاق البحث فوق المدخل
    ctxPillBar = el('div', '', 'as-ctx-pill-row');
    ctxFolderContainer = el('div', '', 'as-ctx-folder-wrap');
    searchScopeWrap = buildSearchScopeUI();
    ctxPillBar.append(ctxFolderContainer, searchScopeWrap);

    // صف الإدخال المتوسع ذاتيًا مع زر الإرفاق وزر النجمة لحفظ الأمر الجاهز
    const inputBar = el('div', '', 'as-input-bar');

    // زر الإرفاق ومدخل الملفات المخفي (المهمة B)
    fileInputEl = el('input', '', '', {
      type: 'file',
      multiple: 'multiple',
      style: 'display:none',
      'aria-hidden': 'true'
    });
    fileInputEl.onchange = () => {
      if (fileInputEl.files && fileInputEl.files.length > 0) {
        handleFilesAdded(fileInputEl.files);
        fileInputEl.value = '';
      }
    };

    attachBtn = el('button', '', 'as-attach-btn', {
      type: 'button',
      title: 'إرفاق صور أو صوتيات أو ملفات',
      'aria-label': 'إرفاق صور أو صوتيات أو ملفات'
    });
    attachBtn.appendChild(createSvg('clip', 16));
    attachBtn.onclick = () => {
      if (fileInputEl) fileInputEl.click();
    };

    const inputWrap = el('div', '', 'as-input-wrap');
    inputEl = el('textarea', '', 'as-input', {
      placeholder: 'اكتب طلبك هنا…',
      title: 'Enter للإرسال، Shift+Enter لسطر جديد',
      rows: '1',
      'aria-label': 'رسالة إلى المساعد'
    });

    inputEl.oninput = () => { autoResizeInput(); updateImproveBtn(); updateSendButtonState(); };
    inputEl.onkeydown = (e) => {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        sendMsg();
        return;
      }
      // الأسهم تتنقل بين الطلبات السابقة (كالطرفية) حين يكون المؤشر في السطر الأول/الأخير فلا يتعطل التحرير متعدد الأسطر
      if ((e.key === 'ArrowUp' || e.key === 'ArrowDown') && !e.shiftKey && !e.altKey && !e.ctrlKey && !e.metaKey && !e.isComposing) {
        const v = inputEl.value, pos = inputEl.selectionStart;
        const onFirst = !v.slice(0, pos).includes('\n'), onLast = !v.slice(inputEl.selectionEnd).includes('\n');
        if (e.key === 'ArrowUp' && onFirst && stepHistory(-1)) e.preventDefault();
        else if (e.key === 'ArrowDown' && onLast && stepHistory(1)) e.preventDefault();
      }
    };
    inputEl.onfocus = () => updateContextPill();

    // لصق صورة من الحافظة داخل مربع الإدخال (المهمة B)
    inputEl.addEventListener('paste', (ev) => {
      const cd = ev.clipboardData;
      if (!cd) return;
      const items = Array.from(cd.items || []);
      const fileItems = items.filter(it => it.kind === 'file');
      if (!fileItems.length) return;

      const files = [];
      for (const it of fileItems) {
        const f = it.getAsFile();
        if (!f) continue;
        if (f.type && f.type.startsWith('image/')) {
          const now = new Date();
          const pad = n => String(n).padStart(2, '0');
          const timeStr = `${pad(now.getHours())}-${pad(now.getMinutes())}-${pad(now.getSeconds())}`;
          const renamed = new File([f], `صورة-${timeStr}.png`, { type: f.type || 'image/png' });
          files.push(renamed);
        } else {
          files.push(f);
        }
      }
      if (files.length > 0) {
        ev.preventDefault();
        handleFilesAdded(files);
      }
    });

    // زر النجمة لحفظ النص كأمر جاهز
    const starPromptBtn = el('button', '', 'as-save-prompt-star', {
      title: 'احفظ هذا النص كأمر جاهز',
      type: 'button'
    });
    starPromptBtn.appendChild(createSvg('star', 14));
    starPromptBtn.onclick = () => {
      const txt = inputEl ? inputEl.value.trim() : '';
      if (!txt) {
        safeNote('اكتب نصًا في مربع الإدخال أولاً لحفظه كأمر جاهز.');
        return;
      }
      showPromptModal({ title: '', text: txt });
    };

    inputWrap.append(inputEl);

    const inputActions = el('div', '', 'as-input-actions');
    sendBtn = btn('', sendMsg, 'btn pri as-send-btn', {
      'aria-label': 'إرسال الرسالة'
    });
    updateSendButtonState();

    stopBtn = btn('', async () => {
      if (!currentJobId) return;
      const targetJobId = currentJobId;
      stopBtn.disabled = true;
      clearTimeout(jobPollTimer);
      try {
        await api('/api/assistant/stop', { id: targetJobId });
        addMessage('sys', 'تم إيقاف المهمة وتفريغ الطابور.');
      } catch (err) {
        addMessage('err', 'تعذر إيقاف المهمة: ' + (err.message || 'خطأ'));
      } finally {
        currentJobId = '';
        if (activeBotCard) {
          activeBotCard.finish({ state: 'stopped', text: 'أُوقفت المهمة بناءً على طلبك وأُفرغ الطابور.' }, 0);
          activeBotCard = null;
        }
        updateQueuedBar([]);
        stopBtn.disabled = true;
        updateSendButtonState();
      }
    }, 'btn as-stop-btn', {
      title: 'إيقاف المهمة وتفريغ الطابور',
      'aria-label': 'إيقاف المهمة وتفريغ الطابور'
    });
    stopBtn.append(createSvg('stop', 12), el('span', 'أوقف', 'as-btn-label'));
    stopBtn.disabled = true;

    // مربع إدخال واحد متجاوب: النص بعرض كامل، وتحته صف أزرار (إرفاق، حفظ كأمر، ثم إيقاف وإرسال)
    const composer = el('div', '', 'as-composer');
    const composerRow = el('div', '', 'as-composer-row');
    composerRow.append(attachBtn, starPromptBtn, el('span', '', 'as-composer-spacer'), stopBtn, sendBtn);
    composer.append(inputWrap, composerRow);
    inputBar.append(composer, fileInputEl);

    // شريط شرائح المرفقات فوق مربع الإدخال (المهمة B)
    attachmentsBarEl = el('div', '', 'as-attachments-bar', {
      role: 'region',
      'aria-label': 'المرفقات الجاهزة للإرسال'
    });
    attachmentsBarEl.hidden = true;

    queuedBarEl = el('div', '', 'as-queued-bar');
    queuedBarEl.hidden = true;
    improveRowEl = el('div', '', 'as-improve-row');
    improveBtnEl = btn('✨ تحسين هذا الطلب', () => showImproveModal(), 'btn as-improve-btn', { title: 'يحوّل طلبك إلى موجّه احترافي بالعربية والإنجليزية قبل أن ترسله' });
    improveBtnEl.hidden = true;
    const askLbl = el('label', '', 'as-clarify-toggle', { title: 'عند الإرسال يقرأ المساعد طلبك القصير ويسألك أسئلة سريعة قبل أن يرسله' });
    const askCb = el('input', '', '', { type: 'checkbox' });
    askCb.checked = clarifyEnabled();
    askCb.onchange = () => { try { localStorage.setItem('zajel_as_clarify', askCb.checked ? 'on' : 'off'); } catch (_) {} };
    askLbl.append(askCb, document.createTextNode(' اسألني قبل الإرسال'));
    improveRowEl.append(improveBtnEl, askLbl);
    mainArea.append(pendingArea, chatContainer, scrollBottomBtn, ctxPillBar, queuedBarEl, improveRowEl, attachmentsBarEl, inputBar);
    bodyLayout.append(sidebarEl, mainArea);
    panelEl.append(head, bodyLayout);
    wireFloatInteractions(head);
    applyPanelMode();
    document.body.appendChild(panelEl);
    // التلاصق: ما دامت النافذة تسمح، يُزاح محتوى البرنامج ليبقى ظاهرًا بجانب المساعد بدل أن يُغطّى
    const markNarrow = () => {
      const w = panelEl.hidden ? 0 : panelEl.clientWidth;
      panelEl.classList.toggle('as-narrow', w > 0 && w < sidebarWidth + 280);
      const dock = !isFloating && w > 0 && window.innerWidth - w >= 460 ? w : 0;
      document.body.style.paddingInlineEnd = dock ? dock + 'px' : '';
      document.body.style.setProperty('--as-dock', dock + 'px');
      document.body.classList.toggle('as-docked', dock > 0);
    };
    panelEl.__markNarrow = markNarrow;
    try { new ResizeObserver(markNarrow).observe(panelEl); } catch (_) {}
    window.addEventListener('resize', () => { if (isFloating) applyPanelMode(); markNarrow(); if (!isExpanded) setPanelWidth(panelWidth, false); });
    markNarrow();

    // إغلاق قائمة نطاق البحث عند النقر خارجها
    document.addEventListener('pointerdown', (e) => {
      if (isSearchScopeOpen && searchScopeWrap) {
        if (!searchScopeWrap.contains(e.target)) {
          closeSearchScopePopup();
        }
      }
    });

    // معالجة مفتاح Escape (يغلق معاينة الصورة أولاً، ثم نطاق البحث، ثم الشريط، ثم النافذة)
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        if (activeImageModalEl) {
          e.stopPropagation();
          activeImageModalEl.remove();
          activeImageModalEl = null;
        } else if (isSearchScopeOpen) {
          e.stopPropagation();
          closeSearchScopePopup();
          if (searchScopeBtn) searchScopeBtn.focus();
        } else if (isSidebarOpen) {
          e.stopPropagation();
          toggleSidebar(false);
        } else if (isOpen) {
          e.stopPropagation();
          togglePanel(false);
        }
      }
    });

    // تحديث دوري للسياق
    setInterval(() => {
      if (isOpen) updateContextPill();
    }, 2500);

    // تحميل الإعدادات الأولية
    loadAgents();
    schedulePendingPoll();
    checkAutomationsNoticeBadge();
    setInterval(checkAutomationsNoticeBadge, 60000);
    renderActiveTab();
    fetchSearchPlaces().then(() => {
      updateSearchScopeBadge();
    });
  }

  /* ==========================================================================
     20. التشغيل عند جاهزية الصفحة
     ========================================================================== */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', buildAssistantUI);
  } else {
    buildAssistantUI();
  }
})();
