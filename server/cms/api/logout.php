<?php
declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    json_response(['ok' => false, 'error' => 'method_not_allowed'], 405);
}

setup_session();
$userId = (string) ($_SESSION['user_id'] ?? '');
if ($userId !== '') {
    append_audit($userId, 'logout', []);
} else {
    $siteSk = (string) ($_SESSION['site_auth_site_key'] ?? '');
    if ($siteSk !== '') {
        append_audit('site:' . $siteSk, 'logout', []);
    }
}

$_SESSION = [];
if (ini_get('session.use_cookies')) {
    $params = session_get_cookie_params();
    setcookie(
        session_name(),
        '',
        time() - 3600,
        $params['path'],
        $params['domain'] ?? '',
        (bool) $params['secure'],
        (bool) $params['httponly']
    );
}
session_destroy();

json_response(['ok' => true]);
