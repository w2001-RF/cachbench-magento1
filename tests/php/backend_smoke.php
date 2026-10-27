<?php
// Backend Magento hors Magento : bouchons Zend_Cache, capacité de 3 pages de 1000 octets.
require __DIR__ . '/zend_stub.php';
$root = dirname(__DIR__, 2);
require $root . '/php/lib/Aicache/Autoload.php';
require $root . '/php/app/code/local/Aicache/Benchmark/Model/Backend.php';
foreach (array('lru' => 3000, 'cacheus' => 3) as $policy => $cap) {
    $name = 'test_' . $policy . '_' . getmypid();
    $b = new Aicache_Benchmark_Model_Backend(array('inner_backend' => 'Stub_Array_Backend',
        'policy' => $policy, 'capacity' => $cap, 'state_name' => $name));
    for ($i = 0; $i < 6; $i++) {
        $b->load("k$i");
        $b->save(str_repeat('x', 1000), "k$i", array('catalog_product_' . $i));
        $b->flush();
    }
    $b->load('k4');
    $b->clean(Zend_Cache::CLEANING_MODE_MATCHING_TAG, array('catalog_product_5'));
    $b->load('k1');
    $b->save('y', 'k1');
    $b->save(str_repeat('z', 1000), 'k6');
    $b->flush();
    echo implode(',', $b->getIds()), "\n";
    (new Aicache_StateStore($name))->clear();
}
