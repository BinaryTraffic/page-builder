<?php
declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'GET') {
    json_response(['ok' => false, 'error' => 'method_not_allowed'], 405);
}

$userId = require_auth();
$user = get_user_record($userId);
$must = (bool) ($user['must_change_password'] ?? false);
$allowedKeys = get_user_allowed_site_keys($userId);
$actSk = get_active_site_key_from_session();
$actLt = get_active_lp_token_from_session();

$sites = [];
foreach (load_sites_registry() as $row) {
    if (!is_array($row)) {
        continue;
    }
    $sk = (string) ($row['site_key'] ?? '');
    if ($sk === '' || !in_array($sk, $allowedKeys, true)) {
        continue;
    }
    $sites[] = [
        'site_key' => $sk,
        'lp_token' => (string) ($row['lp_token'] ?? ''),
    ];
}

json_response([
    'ok' => true,
    'user' => [
        'id' => $userId,
        'must_change_password' => $must,
    ],
    'allowed_site_keys' => $allowedKeys,
    'active_site_key' => $actSk,
    'active_lp_token' => $actLt,
    'sites' => $sites,
    'csrf' => get_csrf_token(),
]);
