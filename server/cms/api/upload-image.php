<?php
declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    json_response(['ok' => false, 'error' => 'method_not_allowed'], 405);
}

$userId = require_auth();
$ctx = require_active_site_for_editing($userId);
require_csrf();

$siteKey = $ctx['site_key'];

if (!isset($_FILES['image']) || !is_array($_FILES['image'])) {
    json_response(['ok' => false, 'error' => 'missing_file'], 400);
}

$file = $_FILES['image'];
if (($file['error'] ?? UPLOAD_ERR_OK) !== UPLOAD_ERR_OK) {
    json_response(['ok' => false, 'error' => 'upload_failed'], 400);
}

$tmp = (string) $file['tmp_name'];
$original = (string) ($file['name'] ?? 'upload.jpg');
$ext = strtolower(pathinfo($original, PATHINFO_EXTENSION));
$allowed = ['jpg', 'jpeg', 'png', 'webp'];
if (!in_array($ext, $allowed, true)) {
    json_response(['ok' => false, 'error' => 'unsupported_type'], 400);
}

$safeName = preg_replace('/[^a-zA-Z0-9_-]/', '_', pathinfo($original, PATHINFO_FILENAME));
$finalName = sprintf('%s_%s.%s', $safeName, date('YmdHis'), $ext);
$dr = get_document_root();
$destDir = $dr . '/' . $siteKey . '/custom';
if (!is_dir($destDir)) {
    mkdir($destDir, 0755, true);
}
$destPath = $destDir . '/' . $finalName;

if (!move_uploaded_file($tmp, $destPath)) {
    json_response(['ok' => false, 'error' => 'save_failed'], 500);
}

append_audit(
    $userId,
    'image_upload',
    [
        'file' => $finalName,
        'site_key' => $siteKey,
        'lp_token' => $ctx['lp_token'],
    ]
);
json_response(['ok' => true, 'file' => $finalName]);
