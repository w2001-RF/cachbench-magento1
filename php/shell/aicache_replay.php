<?php
/**
 * Rejoue une trace CSV dans une politique PHP et affiche les mesures en JSON.
 * Fonctionne à la racine de Magento 1 (shell/ et lib/ côte à côte) ou dans le dossier php/ du dépôt.
 *
 *   php shell/aicache_replay.php --trace traces/m1.csv --policy lru --capacity 10%
 *   php shell/aicache_replay.php --trace t.csv --policy drl --param model=models/drl-bytes.json
 *   php shell/aicache_replay.php --trace t.csv --policy cacheus --sizes unit --invalidation lazy
 *
 * Options : --capacity (N%, 64MB ou octets), --sizes bytes|unit, --invalidation eager|lazy,
 *           --warmup 0.1, --param clé=valeur (répétable), --hits (ajoute la suite des hits).
 */
require dirname(__DIR__) . '/lib/Aicache/Autoload.php';

if (PHP_SAPI !== 'cli') {
    exit(1);
}

$opts = getopt('', array('trace:', 'policy:', 'capacity:', 'sizes:', 'invalidation:', 'warmup:', 'param:', 'hits'));
if (!isset($opts['trace'], $opts['policy'])) {
    fwrite(STDERR, "usage : php shell/aicache_replay.php --trace FICHIER.csv --policy NOM [--capacity 10%] ...\n"
        . 'politiques : ' . implode(', ', Aicache_Factory::available()) . "\n");
    exit(2);
}

$replay = new Aicache_Replay();
foreach (array('sizes', 'invalidation') as $o) {
    if (isset($opts[$o])) {
        $replay->$o = $opts[$o];
    }
}
if (isset($opts['warmup'])) {
    $replay->warmup = (float) $opts['warmup'];
}
$params = array();
foreach ((array) (isset($opts['param']) ? $opts['param'] : array()) as $p) {
    list($k, $v) = explode('=', $p, 2);
    $params[$k] = is_numeric($v) ? $v + 0 : $v;
}

$trace = Aicache_Trace::read($opts['trace']);

// Capacité : même règle que cachebench.engine.resolve_capacity
$spec = isset($opts['capacity']) ? $opts['capacity'] : '10%';
if (preg_match('/^\s*([0-9.]+)\s*%\s*$/', $spec, $m)) {
    $sizes = array();
    foreach ($trace as $r) {
        if ($r->op === Aicache_Request::GET && $r->cacheable) {
            $s = $replay->sizes === 'unit' ? 1 : $r->size;
            $sizes[$r->key] = isset($sizes[$r->key]) ? max($s, $sizes[$r->key]) : $s;
        }
    }
    $capacity = max(1, (int) (array_sum($sizes) * (float) $m[1] / 100));
} elseif (preg_match('/^\s*([0-9.]+)\s*(b|kb|mb|gb)\s*$/i', $spec, $m)) {
    $units = array('b' => 1, 'kb' => 1024, 'mb' => 1048576, 'gb' => 1073741824);
    $capacity = max(1, (int) ((float) $m[1] * $units[strtolower($m[2])]));
} else {
    $capacity = max(1, (int) $spec);
}

$policy = Aicache_Factory::create($opts['policy'], $capacity, $params);
$res = $replay->run($policy, $trace, $hits);
$res = array('policy' => $opts['policy'], 'capacity' => $capacity) + $res;
if (isset($opts['hits'])) {
    $res['hits'] = implode('', $hits);
}
echo json_encode($res), "\n";
