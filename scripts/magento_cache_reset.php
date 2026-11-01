<?php
/**
 * Pour scripts/magento_live_eval.py : prépare ou relève une passe sur la boutique.
 *
 *   php scripts/magento_cache_reset.php C:/wamp64/www/magento reset   vide le cache Magento, efface
 *       l'état de la politique (fichier de state_dir) et le journal du cache ; affiche la configuration
 *   php scripts/magento_cache_reset.php C:/wamp64/www/magento state   état final de la politique (JSON)
 *
 * L'état doit être dans un fichier (state_dir, sans APCu dans Apache) : la ligne de commande ne voit
 * pas l'APCu d'Apache.
 */
list(, $root, $mode) = $argv + array(null, 'C:/wamp64/www/magento', 'reset');
chdir($root);
require 'app/Mage.php';
Mage::app('admin');
$b = Mage::app()->getCacheInstance()->getFrontend()->getBackend();
$o = new ReflectionProperty($b, '_options');
$o->setAccessible(true);
$opt = $o->getValue($b);
$stateFile = rtrim($opt['state_dir'], '/\\') . '/aicache_' . preg_replace('/[^a-z0-9_]/i', '_', $opt['state_name']) . '.state';

if ($mode === 'state') {
    $p = unserialize(file_get_contents($stateFile));
    $out = array('class' => get_class($p), 'capacity' => $p->getCapacity(), 'used_bytes' => $p->usedBytes(),
        'evictions' => $p->getEvictions());
    if (method_exists($p, 'stats')) {
        $out['stats'] = $p->stats();
    }
    if ($p instanceof Aicache_Policy_Official) {
        // ces politiques comptent des objets : le script Python retrouve leurs octets dans le journal
        $get = function ($name) use ($p) {
            $r = new ReflectionProperty($p, $name);
            $r->setAccessible(true);
            return $r->getValue($p);
        };
        $out['resident_keys'] = array_map('strval', array_keys(array_diff_key($get('resident'), $get('stale'))));
    }
    echo json_encode($out), "\n";
    exit;
}
@unlink($stateFile);
Mage::app()->getCacheInstance()->flush();
@unlink($stateFile);   // flush() a pu réécrire un état vide : on repart sans fichier
if (!empty($opt['trace_file'])) {
    file_put_contents($opt['trace_file'], '');
}
// réglage en base : celui que la prochaine requête lira, le cache des options venant d'être vidé
$options = Mage::getResourceSingleton('core/cache')->getAllOptions();
$fpc = !empty($options['fpc']);
echo json_encode(array('backend' => get_class($b), 'policy' => $opt['policy'], 'capacity' => (int) $opt['capacity'],
    'params' => $opt['params'], 'fpc' => $fpc ? 'on' : 'off',
    'apcu' => Aicache_StateStore::apcuAvailable())), "\n";
