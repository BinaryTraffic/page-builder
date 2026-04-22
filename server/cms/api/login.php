<?php
declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    json_response(['ok' => false, 'error' => 'method_not_allowed'], 405);
}

setup_session();
$input = get_request_json();
$id = trim((string)($input['id'] ?? ''));
$password = (string)($input['password'] ?? '');

if ($id === '' || $password === '') {
    json_response(['ok' => false, 'error' => 'invalid_request'], 400);
}

$users = read_json(USERS_FILE, ['users' => []]);
$attempts = read_json(LOGIN_ATTEMPTS_FILE, []);
$record = $attempts[$id] ?? ['count' => 0, 'lock_until' => 0];

$now = time();
if (($record['lock_until'] ?? 0) > $now) {
    json_response(['ok' => false, 'error' => 'locked'], 423);
}

$targetUser = null;
foreach (($users['users'] ?? []) as $user) {
    if (($user['id'] ?? '') === $id && ($user['active'] ?? true) === true) {
        $targetUser = $user;
        break;
    }
}

if (!$targetUser || !password_verify($password, (string)($targetUser['password_hash'] ?? ''))) {
    $record['count'] = (int)($record['count'] ?? 0) + 1;
    if ($record['count'] >= MAX_FAILED_ATTEMPTS) {
        $record['count'] = 0;
        $record['lock_until'] = $now + LOCK_SECONDS;
    }
    $attempts[$id] = $record;
    write_json(LOGIN_ATTEMPTS_FILE, $attempts);
    json_response(['ok' => false, 'error' => 'invalid_credentials'], 401);
}

$attempts[$id] = ['count' => 0, 'lock_until' => 0];
write_json(LOGIN_ATTEMPTS_FILE, $attempts);

$_SESSION['user_id'] = $id;
$_SESSION['csrf'] = bin2hex(random_bytes(24));
unset($_SESSION['active_site_key'], $_SESSION['active_lp_token']);

append_audit($id, 'login');
json_response([
    'ok' => true,
    'user' => ['id' => $id],
    'must_change_password' => (bool)($targetUser['must_change_password'] ?? false),
    'csrf' => $_SESSION['csrf'],
]);
