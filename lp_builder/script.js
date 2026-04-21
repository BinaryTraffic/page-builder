// Navbar scroll
const navbar = document.getElementById('navbar');
if (navbar) {
  window.addEventListener('scroll', () => {
    navbar.classList.toggle('scrolled', window.scrollY > 60);
  });
}

// Mobile nav
const navToggle = document.getElementById('navToggle');
const navMenu = document.getElementById('navMenu');
if (navToggle && navMenu) {
  navToggle.addEventListener('click', () => {
    const open = navMenu.classList.toggle('open');
    const spans = navToggle.querySelectorAll('span');
    spans[0].style.transform = open ? 'rotate(45deg) translate(5px, 5px)' : '';
    spans[1].style.opacity = open ? '0' : '';
    spans[2].style.transform = open ? 'rotate(-45deg) translate(5px, -5px)' : '';
  });
  navMenu.querySelectorAll('a').forEach(a => a.addEventListener('click', () => {
    navMenu.classList.remove('open');
    navToggle.querySelectorAll('span').forEach(s => { s.style.transform = ''; s.style.opacity = ''; });
  }));
}

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

// Smooth scroll
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    const href = a.getAttribute('href');
    if (href === '#') return;
    const target = document.querySelector(href);
    if (target) {
      e.preventDefault();
      window.scrollTo({ top: target.getBoundingClientRect().top + window.scrollY - 80, behavior: 'smooth' });
    }
  });
});
