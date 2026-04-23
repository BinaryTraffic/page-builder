let csrf = "";

const ERR_JA = {
  csrf_mismatch: "画面の有効期限が切れました。一度ログアウトするか、ページを再読み込みしてからやり直してください。",
  invalid_credentials: "IDまたはパスワードが違います。",
  unauthorized: "ログインの有効期限が切れています。再度ログインしてください。",
  locked: "失敗が続いたため一時的にロックされています。しばらく待ってから試してください。",
  password_change_required: "先にパスワードを変更してください。",
  site_not_selected: "先に「編集するLP」で site を選んでください。",
  site_forbidden: "このLPへのアクセスは許可されていません。",
  site_unknown: "登録のない site_key です。",
  invalid_site_session: "セッションのLP情報が不正です。LPを選び直してください。",
  credentials_not_found: "この site_key に cms_credentials.json がありません。LP をアップロード済みか確認してください。",
  lp_token_mismatch: "資格情報と lp_meta.json の lp_token が一致しません。",
  site_auth_no_select: "サイトパスワードログインでは LP の切替はできません。ログアウトして管理者でログインしてください。",
  invalid_credentials_file: "サーバー側の資格情報ファイルが不正です。LP を再生成してください。",
  original_exists: "既に _lp_original があります。「オリジナルを上書き」で取り直すか、_lp を整理してください。",
  lp_dir_not_found: "LP ディレクトリが見つかりません。アップロード先を確認してください。",
  copy_failed: "ファイルのコピーに失敗しました。サーバーの空きと権限を確認してください。",
  mkdir_failed: "ディレクトリの作成に失敗しました。",
  invalid_request: "要求が不正です。"
};

function errMessage(err) {
  if (!err) return "エラー";
  if (err.code && ERR_JA[err.code]) return ERR_JA[err.code];
  if (err.message && ERR_JA[err.message]) return ERR_JA[err.message];
  return err.message || String(err);
}

const loginCard = document.getElementById("loginCard");
const passwordCard = document.getElementById("passwordCard");
const siteCard = document.getElementById("siteCard");
const editorCard = document.getElementById("editorCard");
const statusEl = document.getElementById("status");
const siteKeySelect = document.getElementById("siteKeySelect");

/** 編集対象 LP（プレビュー用の公開パス生成） */
let activeSiteKey = "";

/** クライアント等から `/cms/admin/?site_key=...` で開いたとき用（サーバは GET では切替えない。認可後に POST のみ） */
function readPendingSiteKeyFromUrl() {
  const p = new URLSearchParams(window.location.search);
  return (p.get("site_key") || p.get("for_site") || "").trim();
}

let pendingSiteKeyFromUrl = readPendingSiteKeyFromUrl();

const siteKeyLoginInput = document.getElementById("siteKeyLogin");
if (siteKeyLoginInput && pendingSiteKeyFromUrl) {
  siteKeyLoginInput.value = pendingSiteKeyFromUrl;
}

function stripSiteKeyQueryFromAddressBar() {
  if (!pendingSiteKeyFromUrl) return;
  const u = new URL(window.location.href);
  u.searchParams.delete("site_key");
  u.searchParams.delete("for_site");
  const q = u.searchParams.toString();
  window.history.replaceState({}, "", u.pathname + (q ? `?${q}` : "") + u.hash);
  pendingSiteKeyFromUrl = "";
}

function setStatus(text) {
  statusEl.textContent = text;
}

function showOnly(el) {
  loginCard.classList.toggle("hidden", el !== loginCard);
  passwordCard.classList.toggle("hidden", el !== passwordCard);
  siteCard.classList.toggle("hidden", el !== siteCard);
  editorCard.classList.toggle("hidden", el !== editorCard);
}

async function rawApi(path, options = {}) {
  const response = await fetch(path, {
    credentials: "include",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(csrf ? { "X-CSRF-Token": csrf } : {}),
      ...(options.headers || {})
    }
  });
  const data = await response.json().catch(() => ({}));
  return { response, data };
}

async function api(path, options = {}) {
  const { response, data } = await rawApi(path, options);
  if (!response.ok) {
    const code = data.error || data.detail || `HTTP ${response.status}`;
    const err = new Error(code);
    err.code = data.error;
    err.status = response.status;
    throw err;
  }
  return data;
}

function fillSiteSelect(sites) {
  siteKeySelect.innerHTML = "";
  (sites || []).forEach((s) => {
    const sk = s.site_key || s.sitekey;
    if (!sk) return;
    const opt = document.createElement("option");
    opt.value = sk;
    opt.textContent = sk;
    siteKeySelect.appendChild(opt);
  });
}

async function postSelectSite(siteKey) {
  return api("/cms/api/select-site.php", {
    method: "POST",
    body: JSON.stringify({ site_key: siteKey })
  });
}

function heroFilenameFromData(images) {
  const h = images?.hero;
  if (typeof h === "string") return h;
  if (h && typeof h === "object" && typeof h.url === "string") {
    const u = h.url;
    const m = u.match(/custom\/([^?'#]+)/);
    if (m) return decodeURIComponent(m[1]);
    if (!/^https?:\/\//i.test(u)) return u.replace(/^\.\//, "");
  }
  return "";
}

function heroPreviewUrl() {
  const raw = (document.getElementById("heroImage")?.value || "").trim();
  if (!raw) return "";
  if (/^https?:\/\//i.test(raw)) return raw;
  if (!activeSiteKey) return "";
  const segs = raw.split("/").filter(Boolean);
  return (
    `${window.location.origin}/${encodeURIComponent(activeSiteKey)}/custom/` +
    segs.map((s) => encodeURIComponent(s)).join("/")
  );
}

function syncPreview() {
  const subEl = document.getElementById("heroSub");
  const titleEl = document.getElementById("heroTitle");
  const descEl = document.getElementById("heroDesc");
  const sub = subEl ? subEl.value || "" : "";
  const title = titleEl ? titleEl.value || "" : "";
  const desc = descEl ? descEl.value || "" : "";
  const pSub = document.getElementById("previewHeroSub");
  const pTitle = document.getElementById("previewHeroTitle");
  const pDesc = document.getElementById("previewHeroDesc");
  const bg = document.getElementById("previewHeroBg");
  if (pSub) pSub.textContent = sub;
  if (pTitle) pTitle.textContent = title || "（タイトル）";
  if (pDesc) pDesc.textContent = desc || "（リード）";
  const url = heroPreviewUrl();
  if (bg) {
    if (url) {
      bg.style.backgroundImage = "url(" + JSON.stringify(url) + ")";
      bg.style.backgroundColor = "";
    } else {
      bg.style.backgroundImage = "none";
      bg.style.backgroundColor = "#1a1a22";
    }
  }
}

async function loadContent() {
  const data = await api("/cms/api/content.php", { method: "GET" });
  document.getElementById("heroImage").value = heroFilenameFromData(data.images || {});
  document.getElementById("heroSub").value = data.texts?.hero_sub || "";
  document.getElementById("heroTitle").value = data.texts?.hero_title || "";
  document.getElementById("heroDesc").value = data.texts?.hero_desc || "";
  setStatus(JSON.stringify(data, null, 2));
  syncPreview();
}

/**
 * /cms/api/me.php の内容で画面遷移
 */
async function applyMeData(data) {
  csrf = data.csrf || "";
  activeSiteKey = data.active_site_key || "";
  const switchBtn = document.getElementById("switchSiteBtn");
  if (switchBtn) {
    switchBtn.style.display = data.auth === "site" ? "none" : "";
  }
  if (data.user?.must_change_password) {
    stripSiteKeyQueryFromAddressBar();
    showOnly(passwordCard);
    return;
  }
  if (pendingSiteKeyFromUrl) {
    const want = pendingSiteKeyFromUrl;
    if (data.active_site_key === want) {
      stripSiteKeyQueryFromAddressBar();
      showOnly(editorCard);
      try {
        await loadContent();
      } catch (e) {
        if (e.code === "site_not_selected" || e.code === "invalid_site_session") {
          const me2 = await api("/cms/api/me.php", { method: "GET" });
          await applyMeData(me2);
        } else {
          alert(errMessage(e));
        }
      }
      return;
    }
    const allowed = (data.sites || []).some(
      (s) => (s.site_key || s.sitekey) === want
    );
    if (!allowed) {
      setStatus(
        `URL で指定した site_key はこのアカウントで利用できません: ${want}`
      );
      stripSiteKeyQueryFromAddressBar();
      fillSiteSelect(data.sites);
      showOnly(siteCard);
      return;
    }
    try {
      const d = await postSelectSite(want);
      csrf = d.csrf || csrf;
      stripSiteKeyQueryFromAddressBar();
      showOnly(editorCard);
      await loadContent();
    } catch (e) {
      stripSiteKeyQueryFromAddressBar();
      alert(errMessage(e));
      fillSiteSelect(data.sites);
      if (data.sites && data.sites.length) {
        showOnly(siteCard);
      } else {
        setStatus(
          "利用可能なLPがありません。サーバーの台帳と allowed_site_keys を確認してください。"
        );
        showOnly(siteCard);
      }
    }
    return;
  }
  if (!data.active_site_key) {
    fillSiteSelect(data.sites);
    if (data.sites && data.sites.length) {
      showOnly(siteCard);
    } else {
      setStatus("利用可能なLPがありません。サーバーの台帳と allowed_site_keys を確認してください。");
      showOnly(siteCard);
    }
    return;
  }
  showOnly(editorCard);
  try {
    await loadContent();
  } catch (e) {
    if (e.code === "site_not_selected" || e.code === "invalid_site_session") {
      const me2 = await api("/cms/api/me.php", { method: "GET" });
      await applyMeData(me2);
    } else {
      alert(errMessage(e));
    }
  }
}

async function fetchMeAndApply() {
  const d = await api("/cms/api/me.php", { method: "GET" });
  await applyMeData(d);
}

document.getElementById("loginBtn").addEventListener("click", async () => {
  try {
    const siteKey = (document.getElementById("siteKeyLogin").value || "").trim();
    const password = document.getElementById("loginPw").value;
    if (siteKey) {
      const { response, data } = await rawApi("/cms/api/site-login.php", {
        method: "POST",
        body: JSON.stringify({ site_key: siteKey, password })
      });
      if (!response.ok) {
        const err = new Error(data.error || `HTTP ${response.status}`);
        err.code = data.error;
        throw err;
      }
      csrf = data.csrf || "";
      if (data.must_change_password) {
        stripSiteKeyQueryFromAddressBar();
        showOnly(passwordCard);
      } else {
        await fetchMeAndApply();
      }
      return;
    }
    const id = document.getElementById("loginId").value;
    const { response, data } = await rawApi("/cms/api/login.php", {
      method: "POST",
      body: JSON.stringify({ id, password })
    });
    if (!response.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }
    csrf = data.csrf || "";
    if (data.must_change_password) {
      stripSiteKeyQueryFromAddressBar();
      showOnly(passwordCard);
    } else {
      await fetchMeAndApply();
    }
  } catch (err) {
    alert(`ログイン失敗: ${errMessage(err)}`);
  }
});

document.getElementById("changePwBtn").addEventListener("click", async () => {
  const cur = document.getElementById("curPw").value;
  const a = document.getElementById("newPw").value;
  const b = document.getElementById("newPw2").value;
  if (a !== b) {
    alert("新しいパスワードが一致しません");
    return;
  }
  if (a.length < 12) {
    alert("新しいパスワードは12文字以上にしてください");
    return;
  }
  try {
    const data = await api("/cms/api/change-password.php", {
      method: "POST",
      body: JSON.stringify({ current_password: cur, new_password: a })
    });
    csrf = data.csrf || "";
    document.getElementById("curPw").value = "";
    document.getElementById("newPw").value = "";
    document.getElementById("newPw2").value = "";
    await fetchMeAndApply();
  } catch (e) {
    const msg =
      {
        invalid_current: "現在のパスワードが違います",
        weak_password: "新しいパスワードの条件を満たしません",
        same_as_current: "現在と同じパスワードは使えません"
      }[e.code] || errMessage(e);
    alert(msg);
  }
});

document.getElementById("selectSiteBtn").addEventListener("click", async () => {
  const siteKey = siteKeySelect.value;
  if (!siteKey) {
    alert("LPを選んでください");
    return;
  }
  try {
    const d = await postSelectSite(siteKey);
    csrf = d.csrf || csrf;
    showOnly(editorCard);
    await loadContent();
  } catch (e) {
    alert(errMessage(e));
  }
});

document.getElementById("switchSiteBtn").addEventListener("click", async () => {
  try {
    const { response, data: me } = await rawApi("/cms/api/me.php", { method: "GET" });
    if (!response.ok) {
      throw new Error(me.error || `HTTP ${response.status}`);
    }
    if (me.auth === "site") {
      alert(ERR_JA.site_auth_no_select);
      return;
    }
    csrf = me.csrf || "";
    fillSiteSelect(me.sites);
    if (me.active_site_key) {
      siteKeySelect.value = me.active_site_key;
    }
    showOnly(siteCard);
  } catch (e) {
    alert(errMessage(e));
  }
});

document.getElementById("loadBtn").addEventListener("click", async () => {
  try {
    await loadContent();
  } catch (err) {
    if (err.code === "password_change_required") {
      showOnly(passwordCard);
    } else if (err.code === "site_not_selected" || err.code === "invalid_site_session") {
      await fetchMeAndApply();
    } else {
      alert(`読込失敗: ${errMessage(err)}`);
    }
  }
});

document.getElementById("saveBtn").addEventListener("click", async () => {
  try {
    const payload = {
      images: { hero: (document.getElementById("heroImage").value || "").trim() },
      texts: {
        hero_sub: (document.getElementById("heroSub").value || "").trim(),
        hero_title: (document.getElementById("heroTitle").value || "").trim(),
        hero_desc: (document.getElementById("heroDesc").value || "").trim()
      }
    };
    const data = await api("/cms/api/content.php", {
      method: "PUT",
      body: JSON.stringify(payload)
    });
    setStatus(JSON.stringify(data, null, 2));
  } catch (e) {
    if (e.code === "password_change_required") {
      showOnly(passwordCard);
    } else if (e.code === "site_not_selected" || e.code === "invalid_site_session") {
      await fetchMeAndApply();
    } else {
      alert(`保存失敗: ${errMessage(e)}`);
    }
  }
});

document.getElementById("logoutBtn").addEventListener("click", async () => {
  try {
    await api("/cms/api/logout.php", { method: "POST" });
    csrf = "";
    showOnly(loginCard);
    setStatus("");
  } catch (err) {
    alert(`ログアウト失敗: ${errMessage(err)}`);
  }
});

async function runPublishAction(action, force = false) {
  try {
    const d = await api("/cms/api/publish-lp.php", {
      method: "POST",
      body: JSON.stringify({ action, force })
    });
    alert(d.message || "完了しました。");
  } catch (e) {
    if (e.code === "original_exists" && !force) {
      if (confirm("既に _lp_original があります。上書きして取り直しますか？")) {
        return runPublishAction("snapshot", true);
      }
      return;
    }
    alert(errMessage(e));
  }
}

document.getElementById("saveOriginalBtn")?.addEventListener("click", () => {
  runPublishAction("snapshot", false);
});
document.getElementById("saveOriginalForceBtn")?.addEventListener("click", () => {
  if (confirm("本当に _lp_original を現在の「アップロード済み」で上書きしますか？")) {
    runPublishAction("snapshot", true);
  }
});
document.getElementById("publishBtn")?.addEventListener("click", () => {
  runPublishAction("publish", false);
});

["heroSub", "heroTitle", "heroDesc", "heroImage"].forEach((id) => {
  const el = document.getElementById(id);
  if (el) el.addEventListener("input", () => syncPreview());
  if (el) el.addEventListener("change", () => syncPreview());
});
document.getElementById("heroUploadBtn")?.addEventListener("click", () => {
  document.getElementById("heroFile")?.click();
});
document.getElementById("heroFile")?.addEventListener("change", async (e) => {
  const f = e.target?.files && e.target.files[0];
  if (!f) return;
  try {
    const fd = new FormData();
    fd.append("image", f);
    const res = await fetch("/cms/api/upload-image.php", {
      method: "POST",
      credentials: "include",
      headers: {
        ...(csrf ? { "X-CSRF-Token": csrf } : {})
      },
      body: fd
    });
    const d = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = new Error(d.error || `HTTP ${res.status}`);
      err.code = d.error;
      throw err;
    }
    document.getElementById("heroImage").value = d.file || "";
    syncPreview();
    e.target.value = "";
  } catch (err) {
    alert(errMessage(err));
  }
});

(async () => {
  const { response, data } = await rawApi("/cms/api/me.php", { method: "GET" });
  if (!response.ok) return;
  await applyMeData(data);
})();
