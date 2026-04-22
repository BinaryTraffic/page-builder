<?php
declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    json_response(['ok' => false, 'error' => 'method_not_allowed'], 405);
}

$userId = require_auth();
require_csrf();

$input = get_request_json();
$current = (string)($input['current_password'] ?? '');
$new = (string)($input['new_password'] ?? '');

if ($current === '' || $new === '') {
    json_response(['ok' => false, 'error' => 'invalid_request'], 400);
}

if (strlen($new) < 12) {
    json_response(['ok' => false, 'error' => 'weak_password'], 400);
}

$user = get_user_record($userId);
if ($user === null || ($user['active'] ?? true) !== true) {
    json_response(['ok' => false, 'error' => 'unauthorized'], 401);
}

$hash = (string)($user['password_hash'] ?? '');
if ($hash === '' || !password_verify($current, $hash)) {
    json_response(['ok' => false, 'error' => 'invalid_current'], 401);
}

if (password_verify($new, $hash)) {
    json_response(['ok' => false, 'error' => 'same_as_current'], 400);
}

$user['password_hash'] = password_hash($new, PASSWORD_DEFAULT);
$user['must_change_password'] = false;

$payload = read_json(USERS_FILE, ['users' => []]);
$users = $payload['users'] ?? [];
$found = false;
foreach ($users as $i => $u) {
    if (is_array($u) && ($u['id'] ?? '') === $userId) {
        $users[$i] = $user;
        $found = true;
        break;
    }
}
if (!$found) {
    json_response(['ok' => false, 'error' => 'user_not_found'], 500);
}
$payload['users'] = $users;
write_json(USERS_FILE, $payload);

append_audit($userId, 'password_change', []);

$_SESSION['csrf'] = bin2hex(random_bytes(24));
json_response([
    'ok' => true,
    'must_change_password' => false,
    'csrf' => $_SESSION['csrf'],
]);
