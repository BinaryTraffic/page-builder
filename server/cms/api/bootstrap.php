<?php
declare(strict_types=1);

const CMS_DATA_DIR = __DIR__ . '/../data';
const SITES_FILE = CMS_DATA_DIR . '/sites.json';
const USERS_FILE = CMS_DATA_DIR . '/users.json';
const AUDIT_FILE = CMS_DATA_DIR . '/audit.log';
const LOGIN_ATTEMPTS_FILE = CMS_DATA_DIR . '/login_attempts.json';

/** 旧単一ファイル（移行用）。参照はしない */
const LEGACY_CONTENT_FILE = CMS_DATA_DIR . '/content.json';

const MAX_FAILED_ATTEMPTS = 5;
const LOCK_SECONDS = 600;

function setup_session(): void
{
    session_set_cookie_params([
        'lifetime' => 60 * 60 * 12,
        'path' => '/',
        'secure' => true,
        'httponly' => true,
        'samesite' => 'Lax',
    ]);
    if (session_status() !== PHP_SESSION_ACTIVE) {
        session_start();
    }
}

function json_response(array $payload, int $statusCode = 200): void
{
    http_response_code($statusCode);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function read_json(string $path, array $default): array
{
    if (!is_file($path)) {
        return $default;
    }
    $raw = file_get_contents($path);
    if ($raw === false || $raw === '') {
        return $default;
    }
    $decoded = json_decode($raw, true);
    return is_array($decoded) ? $decoded : $default;
}

function write_json(string $path, array $data): void
{
    if (!is_dir(dirname($path))) {
        mkdir(dirname($path), 0750, true);
    }
    file_put_contents($path, json_encode($data, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
}

function get_request_json(): array
{
    $raw = file_get_contents('php://input');
    if ($raw === false || $raw === '') {
        return [];
    }
    $decoded = json_decode($raw, true);
    return is_array($decoded) ? $decoded : [];
}

function require_auth(): string
{
    setup_session();
    $userId = $_SESSION['user_id'] ?? null;
    if (!is_string($userId) || $userId === '') {
        json_response(['ok' => false, 'error' => 'unauthorized'], 401);
    }
    return $userId;
}

function get_user_record(string $userId): ?array
{
    $payload = read_json(USERS_FILE, ['users' => []]);
    foreach (($payload['users'] ?? []) as $user) {
        if (($user['id'] ?? '') === $userId) {
            return is_array($user) ? $user : null;
        }
    }
    return null;
}

function user_must_change_password(string $userId): bool
{
    $user = get_user_record($userId);
    if ($user === null) {
        return false;
    }
    return (bool)($user['must_change_password'] ?? false);
}

function require_editing_allowed(string $userId): void
{
    if (user_must_change_password($userId)) {
        json_response(['ok' => false, 'error' => 'password_change_required'], 403);
    }
}

function get_document_root(): string
{
    $dr = $_SERVER['DOCUMENT_ROOT'] ?? '';
    return is_string($dr) && $dr !== '' ? rtrim($dr, '/\\') : '/home/lp-tool';
}

function load_sites_registry(): array
{
    $payload = read_json(SITES_FILE, ['sites' => []]);
    return is_array($payload['sites'] ?? null) ? $payload['sites'] : [];
}

function save_sites_registry(array $sites): void
{
    write_json(SITES_FILE, ['sites' => $sites]);
}

function get_site_by_site_key(string $siteKey): ?array
{
    foreach (load_sites_registry() as $row) {
        if (!is_array($row)) {
            continue;
        }
        if (($row['site_key'] ?? '') === $siteKey) {
            return $row;
        }
    }
    return null;
}

function get_site_by_lp_token(string $lpToken): ?array
{
    foreach (load_sites_registry() as $row) {
        if (!is_array($row)) {
            continue;
        }
        if (($row['lp_token'] ?? '') === $lpToken) {
            return $row;
        }
    }
    return null;
}

function get_user_allowed_site_keys(string $userId): array
{
    $u = get_user_record($userId);
    if ($u === null) {
        return [];
    }
    $keys = $u['allowed_site_keys'] ?? [];
    return is_array($keys) ? array_values(array_filter($keys, 'is_string')) : [];
}

function user_may_access_site_key(string $userId, string $siteKey): bool
{
    return in_array($siteKey, get_user_allowed_site_keys($userId), true);
}

function content_path_for_lp_token(string $lpToken): string
{
    $dir = CMS_DATA_DIR . '/sites/' . $lpToken;
    if (!is_dir($dir)) {
        mkdir($dir, 0750, true);
    }
    return $dir . '/content.json';
}

function get_active_site_key_from_session(): ?string
{
    setup_session();
    $k = $_SESSION['active_site_key'] ?? null;
    return is_string($k) && $k !== '' ? $k : null;
}

function get_active_lp_token_from_session(): ?string
{
    setup_session();
    $k = $_SESSION['active_lp_token'] ?? null;
    return is_string($k) && $k !== '' ? $k : null;
}

function clear_active_site_in_session(): void
{
    setup_session();
    unset($_SESSION['active_site_key'], $_SESSION['active_lp_token']);
}

/**
 * 編集用API向け: LP ディレクトリの cms_credentials.json でログインしたセッション、または users.json ユーザー。
 *
 * @return array{site_key: string, lp_token: string, content_path: string, audit_user: string}
 */
function require_active_site_for_editing(): array
{
    setup_session();
    $sk = get_active_site_key_from_session();
    $lt = get_active_lp_token_from_session();

    $siteLt = (string) ($_SESSION['site_auth_lp_token'] ?? '');
    if ($siteLt !== '') {
        if ($sk === null || $lt === null || $sk !== (string) ($_SESSION['site_auth_site_key'] ?? '') || $lt !== $siteLt) {
            clear_active_site_in_session();
            json_response(['ok' => false, 'error' => 'invalid_site_session'], 400);
        }
        if ((bool) ($_SESSION['site_auth_must_change_password'] ?? false)) {
            json_response(['ok' => false, 'error' => 'password_change_required'], 403);
        }
        $path = content_path_for_lp_token($lt);
        return [
            'site_key' => $sk,
            'lp_token' => $lt,
            'content_path' => $path,
            'audit_user' => 'site:' . $sk,
        ];
    }

    $userId = require_auth();
    require_editing_allowed($userId);
    if ($sk === null || $lt === null) {
        json_response(['ok' => false, 'error' => 'site_not_selected'], 400);
    }
    $row = get_site_by_site_key($sk);
    if ($row === null || (string) ($row['lp_token'] ?? '') !== $lt) {
        clear_active_site_in_session();
        json_response(['ok' => false, 'error' => 'invalid_site_session'], 400);
    }
    if (!user_may_access_site_key($userId, $sk)) {
        json_response(['ok' => false, 'error' => 'site_forbidden'], 403);
    }
    $path = content_path_for_lp_token($lt);
    return [
        'site_key' => $sk,
        'lp_token' => $lt,
        'content_path' => $path,
        'audit_user' => $userId,
    ];
}

function get_csrf_token(): string
{
    setup_session();
    if (!isset($_SESSION['csrf']) || !is_string($_SESSION['csrf'])) {
        $_SESSION['csrf'] = bin2hex(random_bytes(24));
    }
    return $_SESSION['csrf'];
}

function require_csrf(): void
{
    $sessionToken = get_csrf_token();
    $headerToken = $_SERVER['HTTP_X_CSRF_TOKEN'] ?? '';
    if (!is_string($headerToken) || $headerToken === '' || !hash_equals($sessionToken, $headerToken)) {
        json_response(['ok' => false, 'error' => 'csrf_mismatch'], 403);
    }
}

function now_iso8601(): string
{
    return (new DateTimeImmutable('now', new DateTimeZone('Asia/Tokyo')))->format(DateTimeInterface::ATOM);
}

const LP_DIR_ORIGINAL = '_lp_original';
const LP_DIR_PUBLISH = '_lp_publish';

/** content.json / meta.status の既定値 */
const CMS_STATUS_EDITING = 'editing';
const CMS_STATUS_PREVIEW = 'preview';
const CMS_STATUS_DEPLOYED = 'deployed';

/**
 * 旧ファイル互換: meta・日時の既定を揃える（GET/PUT 前に使用）
 */
function normalize_content_json(array $data): array
{
    $now = now_iso8601();
    $out = $data;
    $meta = is_array($out['meta'] ?? null) ? $out['meta'] : [];
    $defaults = [
        'dirty' => false,
        'status' => CMS_STATUS_EDITING,
        'section_dirty' => [],
    ];
    $meta = array_merge($defaults, $meta);
    if (!in_array($meta['status'], [CMS_STATUS_EDITING, CMS_STATUS_PREVIEW, CMS_STATUS_DEPLOYED], true)) {
        $meta['status'] = CMS_STATUS_EDITING;
    }
    $sec = $meta['section_dirty'] ?? [];
    if (is_object($sec)) {
        $sec = (array) $sec;
    }
    if (!is_array($sec)) {
        $sec = [];
    }
    $meta['section_dirty'] = $sec;
    $meta['dirty'] = (bool) ($meta['dirty'] ?? false);
    $out['meta'] = $meta;
    if (empty($out['created_at'] ?? null) || !is_string($out['created_at'])) {
        $out['created_at'] = is_string($out['updated_at'] ?? null) ? (string) $out['updated_at'] : $now;
    }
    if (empty($out['updated_at'] ?? null) || !is_string($out['updated_at'])) {
        $out['updated_at'] = (string) $out['created_at'];
    }
    return $out;
}

/**
 * _lp_publish 完了後: デプロイ済み扱いに content.json meta を揃える
 */
function content_apply_meta_after_deploy(string $lpToken): void
{
    if ($lpToken === '') {
        return;
    }
    $path = content_path_for_lp_token($lpToken);
    if (!is_file($path)) {
        return;
    }
    $c = read_json($path, []);
    if ($c === []) {
        return;
    }
    $c = normalize_content_json($c);
    $c['meta']['status'] = CMS_STATUS_DEPLOYED;
    $c['meta']['dirty'] = false;
    $c['meta']['section_dirty'] = [];
    $c['updated_at'] = now_iso8601();
    write_json($path, $c);
}

/**
 * 任意 custom ディレクトリに cms_page_state.json（overlay-apply.js 用）
 */
function mirror_cms_page_state_to_custom_dir(string $customDir, array $content): void
{
    if ($customDir === '' || str_contains($customDir, '..')) {
        return;
    }
    if (!is_dir($customDir)) {
        if (!@mkdir($customDir, 0755, true) && !is_dir($customDir)) {
            return;
        }
    }
    $images = $content['images'] ?? [];
    $texts = is_array($content['texts'] ?? null) ? $content['texts'] : [];
    $hero = $images['hero'] ?? null;
    $heroUrl = null;
    if (is_string($hero) && $hero !== '') {
        $base = $hero;
        if (!preg_match('#^https?://#i', $base) && $base[0] !== '.') {
            $heroUrl = './custom/' . ltrim($base, '/');
        } else {
            $heroUrl = $base;
        }
    } elseif (is_array($hero) && isset($hero['url']) && is_string($hero['url']) && $hero['url'] !== '') {
        $heroUrl = $hero['url'];
    }
    $meta = is_array($content['meta'] ?? null) ? $content['meta'] : [];
    $out = [
        'texts' => $texts,
        'images' => [],
        'updated_at' => $content['updated_at'] ?? now_iso8601(),
        'meta' => [
            'dirty' => (bool) ($meta['dirty'] ?? false),
            'status' => (string) ($meta['status'] ?? CMS_STATUS_EDITING),
        ],
    ];
    if ($heroUrl !== null) {
        $out['images']['hero'] = ['url' => $heroUrl];
    }
    $path = rtrim($customDir, '/\\') . '/cms_page_state.json';
    write_json($path, $out);
}

/**
 * ドキュメントルート配下 site_key（編集用）の custom/ に反映
 */
function mirror_cms_page_state_to_site_custom(string $siteKey, array $content): void
{
    if ($siteKey === '' || preg_match('/[\x00-\x1f]/', $siteKey) || str_contains($siteKey, '..') || str_contains($siteKey, '/')) {
        return;
    }
    $dir = get_document_root() . '/' . $siteKey . '/custom';
    mirror_cms_page_state_to_custom_dir($dir, $content);
}

function append_audit(string $userId, string $action, array $meta = []): void
{
    setup_session();
    if (!isset($meta['site_key'])) {
        $k = get_active_site_key_from_session();
        if (is_string($k) && $k !== '') {
            $meta['site_key'] = $k;
        }
    }
    if (!isset($meta['lp_token'])) {
        $t = get_active_lp_token_from_session();
        if (is_string($t) && $t !== '') {
            $meta['lp_token'] = $t;
        }
    }
    $entry = [
        'time' => now_iso8601(),
        'user' => $userId,
        'action' => $action,
        'ip' => $_SERVER['REMOTE_ADDR'] ?? 'unknown',
        'meta' => $meta,
    ];
    file_put_contents(AUDIT_FILE, json_encode($entry, JSON_UNESCAPED_UNICODE) . PHP_EOL, FILE_APPEND);
}
