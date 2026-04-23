<?php
declare(strict_types=1);

/**
 * オリジナル（アップロード品の固定）: {site_key}/_lp_original/
 * 本番用生成先: {site_key}/_lp_publish/
 */
require_once __DIR__ . '/../api/bootstrap.php';

function lp_site_key_valid(string $siteKey): bool
{
    return $siteKey !== ''
        && !preg_match('/[\x00-\x1f]/', $siteKey)
        && !str_contains($siteKey, '..')
        && !str_contains($siteKey, '/')
        && strlen($siteKey) < 500;
}

function lp_site_root(string $siteKey): string
{
    return get_document_root() . '/' . $siteKey;
}

function lp_original_path(string $siteKey): string
{
    return lp_site_root($siteKey) . '/' . LP_DIR_ORIGINAL;
}

function lp_publish_path(string $siteKey): string
{
    return lp_site_root($siteKey) . '/' . LP_DIR_PUBLISH;
}

function lp_is_excluded_basename(string $name): bool
{
    return $name === LP_DIR_ORIGINAL || $name === LP_DIR_PUBLISH;
}

function lp_delete_tree(string $path): void
{
    if (!is_dir($path)) {
        if (is_file($path)) {
            @unlink($path);
        }
        return;
    }
    $it = new RecursiveIteratorIterator(
        new RecursiveDirectoryIterator($path, FilesystemIterator::SKIP_DOTS),
        RecursiveIteratorIterator::CHILD_FIRST
    );
    foreach ($it as $f) {
        if ($f->isDir()) {
            @rmdir($f->getPathname());
        } else {
            @unlink($f->getPathname());
        }
    }
    @rmdir($path);
}

/**
 * コピー: $fromDir 直下の子を $toDir へ（$toDir は空である前提）
 */
function lp_copy_tree_children(string $fromDir, string $toDir): void
{
    if (!is_dir($fromDir)) {
        return;
    }
    if (!is_dir($toDir) && !@mkdir($toDir, 0755, true) && !is_dir($toDir)) {
        throw new RuntimeException('mkdir_failed: ' . $toDir);
    }
    $items = new DirectoryIterator($fromDir);
    foreach ($items as $item) {
        if ($item->isDot()) {
            continue;
        }
        $base = $item->getBasename();
        if (lp_is_excluded_basename($base)) {
            continue;
        }
        $from = $item->getPathname();
        $to = $toDir . '/' . $base;
        if ($item->isDir()) {
            lp_recurse_copy($from, $to);
        } else {
            if (!@copy($from, $to)) {
                throw new RuntimeException('copy_failed: ' . $from);
            }
        }
    }
}

function lp_recurse_copy(string $from, string $to): void
{
    if (!is_dir($to) && !@mkdir($to, 0755, true) && !is_dir($to)) {
        throw new RuntimeException('mkdir_failed: ' . $to);
    }
    $it = new RecursiveIteratorIterator(
        new RecursiveDirectoryIterator($from, FilesystemIterator::SKIP_DOTS),
        RecursiveIteratorIterator::SELF_FIRST
    );
    foreach ($it as $f) {
        $rel = substr($f->getPathname(), strlen($from) + 1);
        $dest = $to . '/' . $rel;
        if ($f->isDir()) {
            if (!is_dir($dest) && !@mkdir($dest, 0755, true) && !is_dir($dest)) {
                throw new RuntimeException('mkdir_failed: ' . $dest);
            }
        } else {
            if (!@copy($f->getPathname(), $dest)) {
                throw new RuntimeException('copy_failed: ' . $f->getPathname());
            }
        }
    }
}

function lp_merge_custom(string $fromCustom, string $toCustom): void
{
    if (!is_dir($fromCustom)) {
        return;
    }
    if (!is_dir($toCustom) && !@mkdir($toCustom, 0755, true) && !is_dir($toCustom)) {
        return;
    }
    $it = new DirectoryIterator($fromCustom);
    foreach ($it as $item) {
        if ($item->isDot() || !$item->isFile()) {
            continue;
        }
        $base = $item->getBasename();
        $src = $item->getPathname();
        $dst = $toCustom . '/' . $base;
        @copy($src, $dst);
    }
}

function lp_inject_overlay_script(string $indexPath): void
{
    if (!is_file($indexPath) || !is_readable($indexPath)) {
        return;
    }
    $html = (string) file_get_contents($indexPath);
    if (str_contains($html, 'overlay-apply.js')) {
        return;
    }
    $tag = '  <script src="/cms/overlay-apply.js" defer></script>' . "\n";
    if (preg_match('/<\/body>/i', $html)) {
        $html = preg_replace('/<\/body>/i', $tag . '</body>', $html, 1);
    } else {
        $html .= $tag;
    }
    file_put_contents($indexPath, $html);
}

function lp_dir_empty_or_missing(string $path): bool
{
    if (!is_dir($path)) {
        return true;
    }
    $i = new FilesystemIterator($path, FilesystemIterator::SKIP_DOTS);
    return !$i->valid();
}

/**
 * 現在の site 直下（_lp_* 除く）を _lp_original に写す
 * @return array{ok: bool, error?: string, message?: string}
 */
function lp_snapshot_original(string $siteKey, bool $force): array
{
    if (!lp_site_key_valid($siteKey)) {
        return ['ok' => false, 'error' => 'invalid_site_key'];
    }
    $root = lp_site_root($siteKey);
    if (!is_dir($root)) {
        return ['ok' => false, 'error' => 'lp_dir_not_found'];
    }
    $dest = lp_original_path($siteKey);
    if (!lp_dir_empty_or_missing($dest) && !$force) {
        return ['ok' => false, 'error' => 'original_exists'];
    }
    if ($force && is_dir($dest)) {
        lp_delete_tree($dest);
    }
    if (!@mkdir($dest, 0755, true) && !is_dir($dest)) {
        return ['ok' => false, 'error' => 'mkdir_failed'];
    }
    try {
        lp_copy_tree_children($root, $dest);
    } catch (Throwable $e) {
        return ['ok' => false, 'error' => 'copy_failed', 'message' => $e->getMessage()];
    }
    return ['ok' => true, 'message' => '_lp_original にアップロード品を固定しました。'];
}

/**
 * オリジナル＋作業中 custom＋ cms content.json から本番用 _lp_publish を作る
 * @return array{ok: bool, error?: string, message?: string}
 */
function lp_build_publish_from_original(string $siteKey, string $lpToken): array
{
    if (!lp_site_key_valid($siteKey)) {
        return ['ok' => false, 'error' => 'invalid_site_key'];
    }
    $root = lp_site_root($siteKey);
    $orig = lp_original_path($siteKey);
    $pub = lp_publish_path($siteKey);
    if (lp_dir_empty_or_missing($orig)) {
        $snap = lp_snapshot_original($siteKey, true);
        if (!$snap['ok']) {
            return $snap;
        }
    }
    if (is_dir($pub)) {
        lp_delete_tree($pub);
    }
    if (!@mkdir($pub, 0755, true) && !is_dir($pub)) {
        return ['ok' => false, 'error' => 'mkdir_failed'];
    }
    try {
        lp_recurse_copy($orig, $pub);
    } catch (Throwable $e) {
        return ['ok' => false, 'error' => 'copy_failed', 'message' => $e->getMessage()];
    }
    $customWorking = $root . '/custom';
    $customPub = $pub . '/custom';
    lp_merge_custom($customWorking, $customPub);
    $contentPath = content_path_for_lp_token($lpToken);
    $content = read_json($contentPath, []);
    mirror_cms_page_state_to_custom_dir($customPub, $content);
    $indexPub = $pub . '/index.html';
    if (is_file($indexPub)) {
        lp_inject_overlay_script($indexPub);
    }
    return [
        'ok' => true,
        'message' => '_lp_publish を生成しました。本番URLは /' . $siteKey . '/_lp_publish/ または .htaccess で振り分けてください（SERVER_SETUP 参照）。',
    ];
}
