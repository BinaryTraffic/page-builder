/**
 * 公開 LP ページ用: custom/cms_page_state.json（CMS 保存で生成）を読み
 * ヒーロー背景・代表テキストを上書きする。index.html の </body> 直前に
 * <script src="/cms/overlay-apply.js" defer></script> を1行追加（同一オリジン前提）。
 */
(function () {
  "use strict";
  function apply(data) {
    if (!data || typeof data !== "object") return;
    var texts = data.texts;
    if (texts && typeof texts === "object") {
      var sub = document.querySelector(".hero-sub");
      if (sub && texts.hero_sub) sub.textContent = texts.hero_sub;
      var title = document.querySelector(".hero-title");
      if (title && texts.hero_title) title.textContent = texts.hero_title;
      var desc = document.querySelector(".hero-desc");
      if (desc && texts.hero_desc) desc.textContent = texts.hero_desc;
    }
    var img = data.images;
    if (img && img.hero) {
      var h = img.hero;
      var url = typeof h === "string" ? h : h && h.url;
      if (url && typeof url === "string") {
        var bg = document.querySelector(".hero-bg");
        if (bg) bg.style.backgroundImage = "url('" + url + "')";
      }
    }
  }

  fetch("custom/cms_page_state.json?_=" + Date.now())
    .then(function (r) {
      if (!r.ok) return null;
      return r.json();
    })
    .then(apply)
    .catch(function () {
      /* 未保存 LP では無い */
    });
})();
