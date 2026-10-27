<?php
/**
 * Chargement hors Magento (scripts, tests). Dans Magento 1, lib/ est déjà dans
 * l'include_path et l'autoloader Varien trouve Aicache_Policy_Lru dans lib/Aicache/Policy/Lru.php.
 */
spl_autoload_register(function ($class) {
    if (strpos($class, 'Aicache_') === 0) {
        $f = dirname(__DIR__) . '/' . str_replace('_', '/', $class) . '.php';
        if (is_file($f)) {
            require $f;
        }
    }
});
