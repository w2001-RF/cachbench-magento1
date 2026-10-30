<?php
// Pour chaque graine : SeedSequence (8 mots), 4 sorties brutes en hexadécimal, 4 random(),
// puis 20 choice() (comparés à numpy.random.default_rng).
require dirname(__DIR__, 2) . '/php/lib/Aicache/Autoload.php';
$o = array();
foreach (array(0, 1, 7, 123, 4294967297) as $seed) {
    $g = new Aicache_CacheusPP_Pcg64($seed);
    $raw = array();
    for ($i = 0; $i < 4; $i++) {
        list($hi, $lo) = $g->next64();
        $raw[] = sprintf('%08x%08x', $hi, $lo);
    }
    $rnd = array();
    for ($i = 0; $i < 4; $i++) {
        $rnd[] = sprintf('%.17g', $g->random());
    }
    $ch = array();
    for ($i = 0; $i < 20; $i++) {
        $ch[] = $g->choice(array(0.2, 0.5, 0.3));
    }
    $o[] = array('seed' => $seed, 'words' => Aicache_CacheusPP_Pcg64::seedSequence($seed, 8),
                 'raw' => $raw, 'random' => $rnd, 'choice' => $ch);
}
echo json_encode($o), "\n";
