<?php
require dirname(__DIR__, 2) . '/php/lib/Aicache/Autoload.php';
$xs = json_decode(stream_get_contents(STDIN), true);
$o = array();
foreach ($xs as $x) { $o[] = array(Aicache_Official_Float32::pyRound3($x), Aicache_Official_Float32::npRound3($x)); }
echo json_encode($o), "\n";
