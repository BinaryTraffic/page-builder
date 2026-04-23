<?php
declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';

$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';

if ($method === 'GET') {
    $ctx = require_active_site_for_editing();
    $content = read_json($ctx['content_path'], [
        'images' => [],
        'texts' => [],
        'created_at' => now_iso8601(),
        'updated_at' => now_iso8601(),
    ]);
    $content = normalize_content_json($content);
    json_response($content);
}

if ($method === 'PUT') {
    $ctx = require_active_site_for_editing();
    require_csrf();
    $input = get_request_json();
    $existing = read_json($ctx['content_path'], []);
    $existing = $existing === [] ? [
        'images' => [],
        'texts' => [],
    ] : $existing;
    $existing = normalize_content_json($existing);
    $images = is_array($input['images'] ?? null) ? $input['images'] : $existing['images'];
    $texts = is_array($input['texts'] ?? null) ? $input['texts'] : $existing['texts'];
    $inMeta = is_array($input['meta'] ?? null) ? $input['meta'] : [];
    $meta = array_merge($existing['meta'] ?? [], $inMeta);
    if (isset($inMeta['status']) && in_array($inMeta['status'], [CMS_STATUS_EDITING, CMS_STATUS_PREVIEW, CMS_STATUS_DEPLOYED], true)) {
        $meta['status'] = $inMeta['status'];
    }
    $ts = now_iso8601();
    $meta['dirty'] = false;
    $meta['section_dirty'] = [];
    if (!in_array($meta['status'] ?? '', [CMS_STATUS_EDITING, CMS_STATUS_PREVIEW, CMS_STATUS_DEPLOYED], true)) {
        $meta['status'] = CMS_STATUS_EDITING;
    }
    $content = [
        'images' => $images,
        'texts' => $texts,
        'created_at' => $existing['created_at'] ?? $ts,
        'updated_at' => $ts,
        'updated_by' => $ctx['audit_user'],
        'meta' => $meta,
    ];
    $content = normalize_content_json($content);
    $content['meta']['dirty'] = false;
    $content['meta']['section_dirty'] = [];
    write_json($ctx['content_path'], $content);
    mirror_cms_page_state_to_site_custom($ctx['site_key'], $content);
    append_audit(
        $ctx['audit_user'],
        'content_update',
        [
            'fields' => ['images', 'texts', 'meta'],
            'site_key' => $ctx['site_key'],
            'lp_token' => $ctx['lp_token'],
        ]
    );
    json_response([
        'ok' => true,
        'updated_at' => $content['updated_at'],
        'created_at' => $content['created_at'] ?? $ts,
        'meta' => $content['meta'] ?? [],
    ]);
}

json_response(['ok' => false, 'error' => 'method_not_allowed'], 405);
