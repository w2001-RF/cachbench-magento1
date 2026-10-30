<?php
// Lit [[ligne de theta, state], ...] en JSON et renvoie dotState pour chacune (comparé à theta @ state).
require dirname(__DIR__, 2) . '/php/lib/Aicache/Autoload.php';
$out = array();
foreach (json_decode(stream_get_contents(STDIN), true) as $pair) {
    $out[] = sprintf('%.17g', Aicache_CacheusPP_Algorithm::dotState($pair[0], $pair[1]));
}
echo json_encode($out), "\n";
