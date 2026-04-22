<?php
declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    json_response(['ok' => false, 'error' => 'method_not_allowed'], 405);
}

$userId = require_auth();
require_editing_allowed($userId);
require_csrf();

$user = get_user_record($userId);
if ($user === null) {
    json_response(['ok' => false, 'error' => 'unauthorized'], 401);
}
if (!((bool)($user['can_register_sites'] ?? true))) {
    json_response(['ok' => false, 'error' => 'register_forbidden'], 403);
}

$input = get_request_json();
$lpToken = trim((string)($input['lp_token'] ?? ''));
$siteKey = trim((string)($input['site_key'] ?? ''));
if ($lpToken === '' || $siteKey === '') {
    json_response(['ok' => false, 'error' => 'invalid_request'], 400);
}
if (!preg_match('/^[a-zA-Z0-9._-]+$/', $lpToken) || !preg_match('/^[a-zA-Z0-9._-]+$/', $siteKey)) {
    json_response(['ok' => false, 'error' => 'invalid_identifiers'], 400);
}

$dr = get_document_root();
$lpDir = $dr . '/' . $siteKey;
if (!is_dir($lpDir)) {
    json_response(['ok' => false, 'error' => 'lp_dir_not_found'], 400);
}

$sites = load_sites_registry();
$byKey = get_site_by_site_key($siteKey);
$byTok = get_site_by_lp_token($lpToken);
if ($byKey !== null && ($byKey['lp_token'] ?? '') !== $lpToken) {
    json_response(['ok' => false, 'error' => 'site_key_conflict'], 409);
}
if ($byTok !== null && ($byTok['site_key'] ?? '') !== $siteKey) {
    json_response(['ok' => false, 'error' => 'lp_token_conflict'], 409);
}
if ($byKey === null) {
    $sites[] = ['lp_token' => $lpToken, 'site_key' => $siteKey];
    save_sites_registry($sites);
}

$allowed = get_user_allowed_site_keys($userId);
if (!in_array($siteKey, $allowed, true)) {
    $allowed[] = $siteKey;
    $payload = read_json(USERS_FILE, ['users' => []]);
    foreach ($payload['users'] as $i => $u) {
        if (is_array($u) && ($u['id'] ?? '') === $userId) {
            $u['allowed_site_keys'] = $allowed;
            $payload['users'][$i] = $u;
            break;
        }
    }
    write_json(USERS_FILE, $payload);
}

$cp = content_path_for_lp_token($lpToken);
if (!is_file($cp)) {
    write_json(
        $cp,
        [
            'images' => (object) [],
            'texts' => (object) [],
            'updated_at' => now_iso8601(),
            'updated_by' => $userId,
        ]
    );
}
append_audit($userId, 'register_site', ['site_key' => $siteKey, 'lp_token' => $lpToken]);
json_response(['ok' => true, 'site_key' => $siteKey, 'lp_token' => $lpToken]);
