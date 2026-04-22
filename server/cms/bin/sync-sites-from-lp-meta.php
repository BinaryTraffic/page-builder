#!/usr/bin/env php
<?php
/**
 * ドキュメントルート配下の各 <site_key>/custom/lp_meta.json を走査し、
 * cms/data/sites.json（台帳）へマージする。WEB 非公開。CLI 専用。
 *
 * 使い方:
 *   sudo -u www-data php /home/lp-tool/cms/bin/sync-sites-from-lp-meta.php /home/lp-tool
 *
 * 既存の sites.json 行は site_key 単位で上書きマージ。台帳にあって meta が無い LP 行は残る。
 */
declare(strict_types=1);

$docRoot = $argv[1] ?? (dirname(__DIR__, 2));
$docRoot = rtrim($docRoot, '/');

require_once dirname(__DIR__) . '/api/bootstrap.php';

$merged = [];
foreach (load_sites_registry() as $row) {
    if (is_array($row) && isset($row['site_key'])) {
        $sk = (string) $row['site_key'];
        if ($sk !== '') {
            $merged[$sk] = [
                'lp_token' => (string) ($row['lp_token'] ?? $sk),
                'site_key' => $sk,
            ];
        }
    }
}

$skip = ['cms', 'custom', '.', '..'];
$dh = opendir($docRoot);
if ($dh === false) {
    fwrite(STDERR, "Cannot open: {$docRoot}\n");
    exit(1);
}
while (false !== ($e = readdir($dh))) {
    if (in_array($e, $skip, true) || $e[0] === '.') {
        continue;
    }
    $full = $docRoot . '/' . $e;
    if (!is_dir($full)) {
        continue;
    }
    $metaPath = $full . '/custom/lp_meta.json';
    if (!is_file($metaPath)) {
        continue;
    }
    $raw = @file_get_contents($metaPath);
    if ($raw === false) {
        continue;
    }
    $j = json_decode($raw, true);
    if (!is_array($j)) {
        continue;
    }
    $siteKey = (string) ($j['site_key'] ?? $e);
    $lpToken = (string) ($j['lp_token'] ?? $siteKey);
    if ($siteKey === '' || $lpToken === '') {
        continue;
    }
    $merged[$siteKey] = [
        'lp_token' => $lpToken,
        'site_key' => $siteKey,
    ];
}
closedir($dh);

ksort($merged);
save_sites_registry(array_values($merged));

$count = count($merged);
echo "sync-sites-from-lp-meta: OK, sites={$count}, docroot={$docRoot}\n";
