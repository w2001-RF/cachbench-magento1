<?php
// Affiche 5 tirages rand() puis 5 choice2() d'un MT19937 de graine 123 (comparé à numpy).
require dirname(__DIR__, 2) . '/php/lib/Aicache/Autoload.php';
$a = new Aicache_Official_Mt19937(123);
$o = array();
for ($i = 0; $i < 5; $i++) { $o[] = sprintf('%.17g', $a->rand()); }
for ($i = 0; $i < 5; $i++) { $o[] = $a->choice2(); }
echo json_encode($o), "\n";
