/**
 * 画像の差し替え（LP Builder 同梱）
 *
 * 優先順（後から読んだものが前を上書き）:
 *  1) 業種フォールバック（<html data-industry> に即した Unsplash・即時表示）
 *  2) 任意: http://localhost:8200/api/images/{industry}
 *  3) 顧客差し替え: custom/config.json（index.html と同じ階層の custom フォルダ）
 *     → 写真は custom/ 内に置き、JSON にファイル名だけ記載（hero / about / reason1〜3 / cta / branch1〜3）
 *
 * 手順の例: custom_config.example.json を custom/config.json にコピーし、画像を追加してから再読込。
 */
(function () {
  'use strict';
  var TRANSPARENT_GIF =
    'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
  function backupPhotoUrl(img) {
    var label = (img.getAttribute('alt') || 'image').slice(0, 40);
    var seed = encodeURIComponent(INDUSTRY + '-' + label);
    return 'https://picsum.photos/seed/' + seed + '/1200/800';
  }

  const INDUSTRY = document.documentElement.dataset.industry || 'default';

  /** @param {string} id Unsplash の photo-{id} の id 部分（ハイフン含む） */
  function u(id, w) {
    return (
      'https://images.unsplash.com/photo-' +
      id +
      '?auto=format&fit=crop&w=' +
      w +
      '&q=80'
    );
  }

  /**
   * 業種別フォールバック（API 未起動時も必ず業種に近い画像になる）
   * hero / cta: { url }  About / reasons / branches: { medium }
   */
  const FALLBACK = {
    pet_salon: {
      hero: { url: u('1548199973-03cce0bbc87b', 1920) },
      about: { medium: u('1587300003388-59208cc962cb', 900) },
      reason1: { medium: u('1534361960055-19849758bfb5', 900) },
      reason2: { medium: u('1601758124510-52d02ddb7cbd', 900) },
      reason3: { medium: u('1516734212186-a972f63deb8b', 900) },
      cta: { url: u('1450778869180-f41ee186ff49', 1600) },
      branch1: { medium: u('1587300003388-59208cc962cb', 800) },
      branch2: { medium: u('1548199973-03cce0bbc87b', 800) },
      branch3: { medium: u('1516734212186-a972f63deb8b', 800) },
    },
    beauty_salon: {
      hero: { url: u('1560066984-138dadb4c035', 1920) },
      about: { medium: u('1522337360868-704123f5808c', 900) },
      reason1: { medium: u('1595476102670-6b77f905bf2d', 900) },
      reason2: { medium: u('1633688799655-f47d6696d96e', 900) },
      reason3: { medium: u('1521590834227-fbc227004546', 900) },
      cta: { url: u('1562322140-8baeececf439', 1600) },
      branch1: { medium: u('1522337360868-704123f5808c', 800) },
      branch2: { medium: u('1560066984-138dadb4c035', 800) },
      branch3: { medium: u('1595476102670-6b77f905bf2d', 800) },
    },
    restaurant: {
      hero: { url: u('1517248135467-4c7edcad34c4', 1920) },
      about: { medium: u('1414235077428-338989a2e8c0', 900) },
      reason1: { medium: u('1555396273-367ea4eb4db5', 900) },
      reason2: { medium: u('1559339352-11d035aa68ba', 900) },
      reason3: { medium: u('1504674900247-0877df9bb868', 900) },
      cta: { url: u('1550966875-029c447f680b', 1600) },
      branch1: { medium: u('1517248135467-4c7edcad34c4', 800) },
      branch2: { medium: u('1555396273-367ea4eb4db5', 800) },
      branch3: { medium: u('1559339352-11d035aa68ba', 800) },
    },
    clinic: {
      hero: { url: u('1579684385127-1ef15d508377', 1920) },
      about: { medium: u('1576091160550-2173dba999ef', 900) },
      reason1: { medium: u('1582719478250-c89cae4dc85b', 900) },
      reason2: { medium: u('1579684385127-1ef15d508377', 900) },
      reason3: { medium: u('1519494026892-80bbd2d6fd0d', 900) },
      cta: { url: u('1576091160399-112ba8d25d1d', 1600) },
      branch1: { medium: u('1579684385127-1ef15d508377', 800) },
      branch2: { medium: u('1582719478250-c89cae4dc85b', 800) },
      branch3: { medium: u('1519494026892-80bbd2d6fd0d', 800) },
    },
    aesthetic_clinic: {
      hero: { url: u('1570172619644-dfd03ed5d881', 1920) },
      about: { medium: u('1560066984-138dadb4c035', 900) },
      reason1: { medium: u('1522337360868-704123f5808c', 900) },
      reason2: { medium: u('1570172619644-dfd03ed5d881', 900) },
      reason3: { medium: u('1595476102670-6b77f905bf2d', 900) },
      cta: { url: u('1562322140-8baeececf439', 1600) },
      branch1: { medium: u('1570172619644-dfd03ed5d881', 800) },
      branch2: { medium: u('1522337360868-704123f5808c', 800) },
      branch3: { medium: u('1560066984-138dadb4c035', 800) },
    },
    fitness: {
      hero: { url: u('1534438327276-14e4680c3d6c', 1920) },
      about: { medium: u('1571902943202-507ec2618e8f', 900) },
      reason1: { medium: u('1517836357463-d25dfeac3438', 900) },
      reason2: { medium: u('1571902943202-507ec2618e8f', 900) },
      reason3: { medium: u('1534438327276-14e4680c3d6c', 900) },
      cta: { url: u('1517836357463-d25dfeac3438', 1600) },
      branch1: { medium: u('1534438327276-14e4680c3d6c', 800) },
      branch2: { medium: u('1517836357463-d25dfeac3438', 800) },
      branch3: { medium: u('1571902943202-507ec2618e8f', 800) },
    },
    villa: {
      hero: { url: u('1613490493576-7fde63acd811', 1920) },
      about: { medium: u('1600596542815-ffad4c1539a9', 900) },
      reason1: { medium: u('1600585154340-be6161a56a0c', 900) },
      reason2: { medium: u('1600607687939-ce8a6c25118c', 900) },
      reason3: { medium: u('1600596542815-ffad4c1539a9', 900) },
      cta: { url: u('1613490493576-7fde63acd811', 1600) },
      branch1: { medium: u('1613490493576-7fde63acd811', 800) },
      branch2: { medium: u('1600585154340-be6161a56a0c', 800) },
      branch3: { medium: u('1600607687939-ce8a6c25118c', 800) },
    },
    motorcycle_mag: {
      hero: { url: u('1558981806-95801160237e', 1920) },
      about: { medium: u('1558618666-fcd25c85cd64', 900) },
      reason1: { medium: u('1449426468159-96d4d1213360', 900) },
      reason2: { medium: u('1558981806-95801160237e', 900) },
      reason3: { medium: u('1558618666-fcd25c85cd64', 900) },
      cta: { url: u('1449426468159-96d4d1213360', 1600) },
      branch1: { medium: u('1558981806-95801160237e', 800) },
      branch2: { medium: u('1449426468159-96d4d1213360', 800) },
      branch3: { medium: u('1558618666-fcd25c85cd64', 800) },
    },
    default: {
      hero: { url: u('1497366216548-37526070297c', 1920) },
      about: { medium: u('1497366754035-f200968a6e72', 900) },
      reason1: { medium: u('1497215846054-49e9d973d7f6', 900) },
      reason2: { medium: u('1486406146926-c627a92ad1ab', 900) },
      reason3: { medium: u('1497366754035-f200968a6e72', 900) },
      cta: { url: u('1497215846054-49e9d973d7f6', 1600) },
      branch1: { medium: u('1497366216548-37526070297c', 800) },
      branch2: { medium: u('1486406146926-c627a92ad1ab', 800) },
      branch3: { medium: u('1497215846054-49e9d973d7f6', 800) },
    },
  };

  function applyImages(images) {
    if (!images) return;

    if (images.hero) {
      const heroBg = document.querySelector('.hero-bg');
      if (heroBg) heroBg.style.backgroundImage = "url('" + images.hero.url + "')";
    }

    if (images.about) {
      const aboutImg = document.querySelector('.about-img-wrap img');
      if (aboutImg) {
        aboutImg.src = images.about.medium;
        aboutImg.alt = aboutImg.alt || 'About';
      }
    }

    const reasons = [images.reason1, images.reason2, images.reason3];
    document.querySelectorAll('.reason-img img').forEach(function (img, i) {
      if (reasons[i]) img.src = reasons[i].medium;
    });

    if (images.cta) {
      const ctaBg = document.querySelector('.cta-bg');
      if (ctaBg) ctaBg.style.backgroundImage = "url('" + images.cta.url + "')";
    }

    const branches = [images.branch1, images.branch2, images.branch3];
    document.querySelectorAll('.branch-img img').forEach(function (img, i) {
      if (branches[i]) img.src = branches[i].medium;
    });

    // Pexels 直リンクは環境によって 403 になりやすいので、該当 img だけ差し替え
    document.querySelectorAll('.service-image img, .lp-card img').forEach(function (img, i) {
      var src = img.getAttribute('src') || '';
      if (src.indexOf('pexels.com') < 0) return;
      if (!images.reason1 || !images.reason2 || !images.reason3) return;
      if (i % 3 === 0) img.src = images.reason1.medium;
      else if (i % 3 === 1) img.src = images.reason2.medium;
      else img.src = images.reason3.medium;
    });
  }

  function rescueUrlFor(img, images) {
    if (!images || !img) return null;
    if (img.closest('.about, .about-grid, .about-image, .about-img-wrap')) {
      return images.about && images.about.medium;
    }
    if (img.closest('.reason-block, .reason-img, .reason-image, .reasons-section')) {
      var reasonImgs = Array.prototype.slice.call(
        document.querySelectorAll(
          '.reason-img img, .reason-image img, .reasons-section .reason-block img'
        )
      );
      var idx = reasonImgs.indexOf(img);
      if (idx < 0) idx = 0;
      if (idx % 3 === 0 && images.reason1) return images.reason1.medium;
      if (idx % 3 === 1 && images.reason2) return images.reason2.medium;
      if (idx % 3 === 2 && images.reason3) return images.reason3.medium;
    }
    if (img.closest('.branch-card, .branches, .branch-img')) {
      var branchImgs = Array.prototype.slice.call(
        document.querySelectorAll('.branch-img img, .branch-card img')
      );
      var b = branchImgs.indexOf(img);
      if (b < 0) b = 0;
      if (b % 3 === 0 && images.branch1) return images.branch1.medium;
      if (b % 3 === 1 && images.branch2) return images.branch2.medium;
      if (b % 3 === 2 && images.branch3) return images.branch3.medium;
    }
    if (img.closest('.service-image, .lp-card, .services-section')) {
      var serviceImgs = Array.prototype.slice.call(
        document.querySelectorAll('.service-image img, .services-section .lp-card img')
      );
      var s = serviceImgs.indexOf(img);
      if (s < 0) s = 0;
      if (s % 3 === 0 && images.reason1) return images.reason1.medium;
      if (s % 3 === 1 && images.reason2) return images.reason2.medium;
      if (s % 3 === 2 && images.reason3) return images.reason3.medium;
    }
    return (images.reason1 && images.reason1.medium) || (images.about && images.about.medium) || null;
  }

  function attachBrokenImageRescue(getImages) {
    document.querySelectorAll('img').forEach(function (img) {
      if (img.dataset.pexelsRescueBound === '1') return;
      img.dataset.pexelsRescueBound = '1';

      // 空 src は error が上がらない場合があるため、初期段階で補正する
      var rawSrc = (img.getAttribute('src') || '').trim();
      if (!rawSrc || rawSrc === '#' || /^about:blank$/i.test(rawSrc)) {
        var images0 = getImages();
        var next0 = rescueUrlFor(img, images0);
        img.src = next0 || backupPhotoUrl(img);
        img.dataset.pexelsRescueAttempt = '1';
      }

      img.addEventListener('error', function () {
        var attempt = parseInt(img.dataset.pexelsRescueAttempt || '0', 10) || 0;
        var images = getImages();
        var next = rescueUrlFor(img, images);
        var current = img.currentSrc || img.src || '';
        if (attempt === 0) {
          // 1回目: 業種フォールバック（同一URLなら backup を使う）
          if (!next || next === current || next === (img.getAttribute('src') || '')) {
            next = backupPhotoUrl(img);
          }
        } else if (attempt === 1) {
          // 2回目: 外部バックアップ画像
          next = backupPhotoUrl(img);
          if (next === current) next = TRANSPARENT_GIF;
        } else {
          // 3回目以降: 最終的に透明GIFへ
          next = TRANSPARENT_GIF;
        }
        img.dataset.pexelsRescueAttempt = String(attempt + 1);
        img.src = next;
      });
    });
  }

  function deepMergePack(base, overlay) {
    var m = JSON.parse(JSON.stringify(base));
    for (var k in overlay) {
      if (overlay[k]) m[k] = overlay[k];
    }
    return m;
  }

  /** custom/config.json → applyImages 用オブジェクト（値は ./custom/ からの相対ファイル名） */
  function packFromCustomConfig(cfg) {
    if (!cfg || typeof cfg !== 'object') return null;
    var P = './custom/';
    function fp(name) {
      if (!name || typeof name !== 'string') return null;
      return P + name.replace(/^[\.\/]+/, '');
    }
    var out = {};
    if (cfg.hero) out.hero = { url: fp(cfg.hero) };
    if (cfg.about) out.about = { medium: fp(cfg.about) };
    if (cfg.reason1) out.reason1 = { medium: fp(cfg.reason1) };
    if (cfg.reason2) out.reason2 = { medium: fp(cfg.reason2) };
    if (cfg.reason3) out.reason3 = { medium: fp(cfg.reason3) };
    if (cfg.cta) out.cta = { url: fp(cfg.cta) };
    if (cfg.branch1) out.branch1 = { medium: fp(cfg.branch1) };
    if (cfg.branch2) out.branch2 = { medium: fp(cfg.branch2) };
    if (cfg.branch3) out.branch3 = { medium: fp(cfg.branch3) };
    return Object.keys(out).length ? out : null;
  }

  function footerCredit() {
    var footer = document.querySelector('.footer-bottom p');
    if (!footer || footer.dataset.pexelsCredit) return;
    footer.dataset.pexelsCredit = '1';
    var credit = document.createElement('p');
    credit.style.cssText =
      'font-size:0.65rem;color:rgba(255,255,255,0.25);margin-top:6px;';
    credit.innerHTML =
      'Photos: <a href="https://unsplash.com" target="_blank" rel="noopener" style="color:rgba(255,255,255,0.35)">Unsplash</a>';
    footer.parentNode.appendChild(credit);
  }

  // ── ① 業種フォールバック（目的: 業種に即した初期イメージ）
  var pack = JSON.parse(JSON.stringify(FALLBACK[INDUSTRY] || FALLBACK.default));
  applyImages(pack);
  attachBrokenImageRescue(function () {
    return pack;
  });
  footerCredit();

  // 任意機能はデフォルト無効:
  // - ローカル API: <html data-image-api="1" data-image-api-base="http://localhost:8200">
  // - custom/config.json: <html data-custom-images="1">
  var root = document.documentElement;
  var useLocalApi = /^(1|true|on)$/i.test(root.getAttribute('data-image-api') || '');
  var useCustomConfig = /^(1|true|on)$/i.test(root.getAttribute('data-custom-images') || '');
  var apiBase = root.getAttribute('data-image-api-base') || 'http://localhost:8200';

  function applyLocalApi() {
    if (!useLocalApi) return Promise.resolve();
    return fetch(apiBase + '/api/images/' + encodeURIComponent(INDUSTRY))
      .then(function (res) {
        if (!res.ok) return null;
        return res.json();
      })
      .then(function (data) {
        if (data && data.images) {
          pack = deepMergePack(pack, data.images);
          applyImages(pack);
        }
      })
      .catch(function () {
        console.info('[pexels.js] data-image-api が有効ですが API に接続できません（スキップ）。');
      });
  }

  function applyCustomConfig() {
    if (!useCustomConfig) return Promise.resolve();
    return fetch('./custom/config.json?_=' + Date.now())
      .then(function (res) {
        if (!res || !res.ok) return null;
        return res.json();
      })
      .then(function (cfg) {
        if (!cfg || typeof cfg !== 'object') return;
        var custom = packFromCustomConfig(cfg);
        if (!custom) return;
        pack = deepMergePack(pack, custom);
        applyImages(pack);
        console.info('[pexels.js] custom/config.json を適用しました（顧客画像で上書き）。');
      })
      .catch(function () {
        /* 任意ファイル。無い場合はそのまま */
      });
  }

  applyLocalApi().then(applyCustomConfig);
})();
