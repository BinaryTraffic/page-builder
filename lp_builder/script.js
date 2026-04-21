function initLpScripts() {
  // Navbar scroll
  const navbar = document.getElementById('navbar');
  if (navbar) {
    window.addEventListener('scroll', () => {
      navbar.classList.toggle('scrolled', window.scrollY > 60);
    });
  }

  // 左ドロワー + ナビ分割（バーは最大 N 件、あとはサブメニュー／モバイルは一覧をドロワーへ）
  (function initNavbarSplitDrawer() {
    const navMenu = document.getElementById('navMenu');
    const navToggle = document.getElementById('navToggle');
    if (!navMenu || navMenu.dataset.navSplitInit === '1') return;

    const raw = [...navMenu.querySelectorAll(':scope > a:not(.nav-cta)')];
    if (raw.length === 0) return;

    navMenu.dataset.navSplitInit = '1';
    const cta = navMenu.querySelector('.nav-cta');
    const allLinks = raw;
    allLinks.forEach(a => {
      if (!a.classList.contains('nav-link')) a.classList.add('nav-link');
      a.remove();
    });

    const navBarEl = document.getElementById('navbar');
    const MAX_PRIMARY = Math.max(
      1,
      parseInt(navBarEl?.dataset?.navMaxVisible || '4', 10) || 4
    );
    const mq = window.matchMedia('(max-width: 768px)');

    let backdrop = document.getElementById('navDrawerBackdrop');
    let drawer = document.getElementById('navDrawer');
    let drawerList = document.getElementById('navDrawerList');

    if (!drawer || !drawerList) {
      backdrop = document.createElement('div');
      backdrop.id = 'navDrawerBackdrop';
      backdrop.className = 'nav-drawer-backdrop';
      backdrop.hidden = true;

      drawer = document.createElement('aside');
      drawer.id = 'navDrawer';
      drawer.className = 'nav-drawer';
      drawer.setAttribute('aria-hidden', 'true');
      drawer.innerHTML =
        '<div class="nav-drawer-panel">' +
        '<button type="button" class="nav-drawer-close" aria-label="メニューを閉じる"><span aria-hidden="true">×</span></button>' +
        '<nav class="nav-drawer-list" id="navDrawerList"></nav></div>';

      drawerList = drawer.querySelector('#navDrawerList');
      document.body.append(backdrop, drawer);
    }

    const moreBtn = document.createElement('button');
    moreBtn.type = 'button';
    moreBtn.id = 'navMoreToggle';
    moreBtn.className = 'nav-more-toggle';
    moreBtn.textContent = 'メニュー';
    moreBtn.setAttribute('aria-expanded', 'false');
    moreBtn.setAttribute('aria-controls', 'navDrawer');
    moreBtn.hidden = true;

    if (cta) navMenu.insertBefore(moreBtn, cta);
    else navMenu.appendChild(moreBtn);

    function closeDrawer() {
      drawer.classList.remove('open');
      backdrop.hidden = true;
      drawer.setAttribute('aria-hidden', 'true');
      moreBtn.setAttribute('aria-expanded', 'false');
      if (navToggle) {
        navToggle.querySelectorAll('span').forEach(s => {
          s.style.transform = '';
          s.style.opacity = '';
        });
      }
      document.body.style.overflow = '';
    }

    function openDrawer() {
      drawer.classList.add('open');
      backdrop.hidden = false;
      drawer.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';
    }

    function applyLayout() {
      [...navMenu.querySelectorAll(':scope > a:not(.nav-cta)')].forEach(a => a.remove());
      while (drawerList.firstChild) drawerList.removeChild(drawerList.firstChild);

      const mobile = mq.matches;
      moreBtn.hidden = true;

      if (mobile) {
        allLinks.forEach(a => drawerList.appendChild(a));
      } else {
        const primary = allLinks.slice(0, MAX_PRIMARY);
        const overflow = allLinks.slice(MAX_PRIMARY);
        primary.forEach(a => navMenu.insertBefore(a, moreBtn));
        overflow.forEach(a => drawerList.appendChild(a));
        if (overflow.length > 0) moreBtn.hidden = false;
      }
      closeDrawer();
    }

    moreBtn.addEventListener('click', () => {
      if (drawer.classList.contains('open')) closeDrawer();
      else {
        openDrawer();
        moreBtn.setAttribute('aria-expanded', 'true');
      }
    });

    if (navToggle) {
      navToggle.addEventListener('click', () => {
        if (drawer.classList.contains('open')) {
          closeDrawer();
        } else {
          openDrawer();
          const spans = navToggle.querySelectorAll('span');
          if (spans.length >= 3) {
            spans[0].style.transform = 'rotate(45deg) translate(5px, 5px)';
            spans[1].style.opacity = '0';
            spans[2].style.transform = 'rotate(-45deg) translate(5px, -5px)';
          }
        }
      });
    }

    backdrop.addEventListener('click', closeDrawer);
    drawer.querySelector('.nav-drawer-close')?.addEventListener('click', closeDrawer);
    drawerList.addEventListener('click', e => {
      if (e.target.closest('a')) closeDrawer();
    });

    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && drawer.classList.contains('open')) closeDrawer();
    });

    let resizeT;
    window.addEventListener('resize', () => {
      clearTimeout(resizeT);
      resizeT = setTimeout(applyLayout, 120);
    });
    mq.addEventListener('change', applyLayout);
    applyLayout();
  })();

  // Price table tabs
  document.querySelectorAll('.price-tabs .tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      document.querySelectorAll('.price-tabs .tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('#priceBody tr').forEach(tr => {
        tr.classList.toggle('hidden', tr.dataset.tab !== tab);
      });
    });
  });

  // Access tabs
  const accessData = {
    azabu: { addr: '港区麻布十番2-1-1 麻布十番ビル1F', station: '東京メトロ南北線・都営大江戸線「麻布十番駅」4番出口より徒歩2分', tel: '03-1234-5678', hours: '10:00〜19:00（火曜定休）' },
    roppongi: { addr: '港区六本木6-2-1 六本木ヒルズ近隣', station: '東京メトロ日比谷線・都営大江戸線「六本木駅」1番出口より徒歩3分', tel: '03-1234-5679', hours: '10:00〜19:00（水曜定休）' },
    shirokanedai: { addr: '港区白金台4-1-1 白金台テラス1F', station: '東京メトロ南北線・都営三田線「白金台駅」1番出口より徒歩2分', tel: '03-1234-5680', hours: '10:00〜18:00（木曜定休）' }
  };
  document.querySelectorAll('.access-tabs .tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.access-tabs .tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const d = accessData[btn.dataset.branch];
      if (d) {
        document.getElementById('accessAddr').textContent = d.addr;
        document.getElementById('accessStation').textContent = d.station;
        const telEl = document.getElementById('accessTel');
        telEl.textContent = d.tel;
        telEl.href = 'tel:' + d.tel;
        document.getElementById('accessHours').textContent = d.hours;
      }
    });
  });

  // Fade-in observer
  const fadeEls = document.querySelectorAll('.fade-in');
  if (fadeEls.length) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry, i) => {
        if (entry.isIntersecting) {
          setTimeout(() => entry.target.classList.add('visible'), i * 90);
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
    fadeEls.forEach(el => observer.observe(el));
  }

  // FAQ accordion
  document.querySelectorAll('.faq-q').forEach(btn => {
    btn.addEventListener('click', () => {
      const expanded = btn.getAttribute('aria-expanded') === 'true';
      document.querySelectorAll('.faq-q').forEach(b => {
        b.setAttribute('aria-expanded', 'false');
        b.nextElementSibling.classList.remove('open');
      });
      if (!expanded) {
        btn.setAttribute('aria-expanded', 'true');
        btn.nextElementSibling.classList.add('open');
      }
    });
  });

  // Back to top button
  (function initBackToTopButton() {
    if (document.querySelector('.back-to-top')) return;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'back-to-top';
    btn.setAttribute('aria-label', 'ページ上部へ戻る');
    btn.textContent = '↑';
    btn.hidden = true;
    document.body.appendChild(btn);

    function onScroll() {
      const visible = window.scrollY > 320;
      btn.hidden = !visible;
      btn.classList.toggle('visible', visible);
    }

    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    btn.addEventListener('click', () => {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  })();

  // ページ内リンク（#...）のスクロールは CSS 側の
  // html { scroll-behavior: smooth; } に委譲する
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initLpScripts);
} else {
  initLpScripts();
}
