<?php
declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    json_response(['ok' => false, 'error' => 'method_not_allowed'], 405);
}

$userId = require_auth();
require_csrf();

$input = get_request_json();
$siteKey = trim((string)($input['site_key'] ?? ''));
if ($siteKey === '') {
    json_response(['ok' => false, 'error' => 'invalid_request'], 400);
}

$row = get_site_by_site_key($siteKey);
if ($row === null) {
    json_response(['ok' => false, 'error' => 'site_unknown'], 404);
}
if (!user_may_access_site_key($userId, $siteKey)) {
    json_response(['ok' => false, 'error' => 'site_forbidden'], 403);
}
$lpToken = (string)($row['lp_token'] ?? '');
if ($lpToken === '') {
    json_response(['ok' => false, 'error' => 'registry_broken'], 500);
}

setup_session();
$_SESSION['active_site_key'] = $siteKey;
$_SESSION['active_lp_token'] = $lpToken;

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
append_audit($userId, 'select_site', ['site_key' => $siteKey, 'lp_token' => $lpToken]);
json_response([
    'ok' => true,
    'active_site_key' => $siteKey,
    'active_lp_token' => $lpToken,
    'csrf' => get_csrf_token(),
]);
