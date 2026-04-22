<?php
declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';

$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';

if ($method === 'GET') {
    $ctx = require_active_site_for_editing();
    $content = read_json($ctx['content_path'], [
        'images' => (object) [],
        'texts' => (object) [],
        'updated_at' => now_iso8601(),
    ]);
    json_response($content);
}

if ($method === 'PUT') {
    $ctx = require_active_site_for_editing();
    require_csrf();
    $input = get_request_json();
    $images = is_array($input['images'] ?? null) ? $input['images'] : [];
    $texts = is_array($input['texts'] ?? null) ? $input['texts'] : [];
    $content = [
        'images' => $images,
        'texts' => $texts,
        'updated_at' => now_iso8601(),
        'updated_by' => $ctx['audit_user'],
    ];
    write_json($ctx['content_path'], $content);
    append_audit(
        $ctx['audit_user'],
        'content_update',
        [
            'fields' => ['images', 'texts'],
            'site_key' => $ctx['site_key'],
            'lp_token' => $ctx['lp_token'],
        ]
    );
    json_response(['ok' => true, 'updated_at' => $content['updated_at']]);
}

json_response(['ok' => false, 'error' => 'method_not_allowed'], 405);
