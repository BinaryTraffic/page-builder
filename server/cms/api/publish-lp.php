<?php
declare(strict_types=1);

require_once __DIR__ . '/bootstrap.php';
require_once __DIR__ . '/../lib/lp_publish.php';

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    json_response(['ok' => false, 'error' => 'method_not_allowed'], 405);
}

$ctx = require_active_site_for_editing();
require_csrf();

$input = get_request_json();
$action = trim((string) ($input['action'] ?? 'publish'));
$force = (bool) ($input['force'] ?? false);
$siteKey = $ctx['site_key'];
$lpToken = $ctx['lp_token'];

$result = null;
if ($action === 'snapshot' || $action === 'save_original') {
    $result = lp_snapshot_original($siteKey, $force);
} elseif ($action === 'publish' || $action === 'redo' || $action === 'build') {
    $result = lp_build_publish_from_original($siteKey, $lpToken);
} else {
    json_response(['ok' => false, 'error' => 'invalid_request'], 400);
}

if (!$result['ok']) {
    $code = $result['error'] ?? 'unknown';
    $status = $code === 'original_exists' ? 409 : 400;
    json_response(
        [
            'ok' => false,
            'error' => $code,
            'message' => $result['message'] ?? null,
        ],
        $status
    );
}

$msg = (string) ($result['message'] ?? 'OK');
$auditUser = (string) ($ctx['audit_user'] ?? 'unknown');
append_audit(
    $auditUser,
    'lp_' . $action,
    [
        'site_key' => $siteKey,
        'lp_token' => $lpToken,
    ]
);

json_response(['ok' => true, 'message' => $msg]);
