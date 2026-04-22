<?php
declare(strict_types=1);
/**
 * LP ディレクトリ内 custom/cms_credentials.json（+ lp_token 整合）で認証。users.json にアカウントを増やさない。
 */
require_once __DIR__ . '/bootstrap.php';

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    json_response(['ok' => false, 'error' => 'method_not_allowed'], 405);
}

setup_session();
$input = get_request_json();
$siteKey = trim((string) ($input['site_key'] ?? ''));
$password = (string) ($input['password'] ?? '');

if ($siteKey === '' || $password === '') {
    json_response(['ok' => false, 'error' => 'invalid_request'], 400);
}
if (strlen($siteKey) > 500 || preg_match('/[\x00-\x1f]/', $siteKey) || str_contains($siteKey, '..') || str_contains($siteKey, '/')) {
    json_response(['ok' => false, 'error' => 'invalid_site_key'], 400);
}

$dr = get_document_root();
$credPath = $dr . '/' . $siteKey . '/custom/cms_credentials.json';
if (!is_file($credPath)) {
    json_response(['ok' => false, 'error' => 'credentials_not_found'], 404);
}

$cred = read_json($credPath, []);
$hash = (string) ($cred['password_hash'] ?? '');
if ($hash === '' || !password_verify($password, $hash)) {
    json_response(['ok' => false, 'error' => 'invalid_credentials'], 401);
}

$lpTok = strtolower(trim((string) ($cred['lp_token'] ?? '')));
if ($lpTok === '' || !preg_match('/^[a-f0-9]{24}$/', $lpTok)) {
    json_response(['ok' => false, 'error' => 'invalid_credentials_file'], 500);
}

$metaPath = $dr . '/' . $siteKey . '/custom/lp_meta.json';
if (is_file($metaPath)) {
    $meta = read_json($metaPath, []);
    $mt = strtolower((string) ($meta['lp_token'] ?? ''));
    if ($mt !== '' && $mt !== $lpTok) {
        json_response(['ok' => false, 'error' => 'lp_token_mismatch'], 409);
    }
}

unset(
    $_SESSION['user_id'],
    $_SESSION['site_auth_site_key'],
    $_SESSION['site_auth_lp_token'],
    $_SESSION['site_auth_must_change_password'],
);

$_SESSION['site_auth_site_key'] = $siteKey;
$_SESSION['site_auth_lp_token'] = $lpTok;
$_SESSION['site_auth_must_change_password'] = (bool) ($cred['must_change_password'] ?? false);
$_SESSION['active_site_key'] = $siteKey;
$_SESSION['active_lp_token'] = $lpTok;
$_SESSION['csrf'] = bin2hex(random_bytes(24));

append_audit('site:' . $siteKey, 'site_login', ['lp_token' => $lpTok]);

json_response([
    'ok' => true,
    'must_change_password' => (bool) $_SESSION['site_auth_must_change_password'],
    'csrf' => $_SESSION['csrf'],
]);
