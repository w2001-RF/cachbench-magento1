<?php
/**
 * État d'une politique partagé entre les requêtes PHP (qui ne partagent rien).
 * APCu si disponible, sinon un fichier. update() tient un verrou le temps d'appliquer
 * les opérations d'une requête à l'état le plus récent.
 */
class Aicache_StateStore
{
    protected $name;
    protected $dir;

    public function __construct($name, $dir = null)
    {
        $this->name = 'aicache_' . preg_replace('/[^a-z0-9_]/i', '_', $name);
        $this->dir = $dir ? $dir : sys_get_temp_dir();
    }

    public static function apcuAvailable()
    {
        return function_exists('apcu_fetch') && ini_get('apc.enabled') && (PHP_SAPI !== 'cli' || ini_get('apc.enable_cli'));
    }

    /**
     * @param callable $fn reçoit l'état (ou null) et renvoie le nouvel état
     */
    public function update($fn)
    {
        if (self::apcuAvailable()) {
            $lock = $this->name . '_lock';
            $t = microtime(true);
            while (!apcu_add($lock, 1, 5)) {   // le verrou expire seul après 5 s si un processus meurt
                if (microtime(true) - $t > 2) {
                    return false;          // on saute cette mise à jour plutôt que bloquer la page
                }
                usleep(200);
            }
            try {
                $state = apcu_fetch($this->name, $ok);
                $state = call_user_func($fn, $ok ? $state : null);
                apcu_store($this->name, $state);
            } catch (Exception $e) {
                apcu_delete($lock);
                throw $e;
            }
            apcu_delete($lock);
            return true;
        }
        $f = fopen($this->dir . DIRECTORY_SEPARATOR . $this->name . '.state', 'c+');
        if (!$f || !flock($f, LOCK_EX)) {
            return false;
        }
        $raw = stream_get_contents($f);
        $state = $raw ? unserialize($raw) : null;
        $state = call_user_func($fn, $state === false ? null : $state);
        ftruncate($f, 0);
        rewind($f);
        fwrite($f, serialize($state));
        flock($f, LOCK_UN);
        fclose($f);
        return true;
    }

    public function clear()
    {
        if (self::apcuAvailable()) {
            apcu_delete($this->name);
        }
        @unlink($this->dir . DIRECTORY_SEPARATOR . $this->name . '.state');
    }
}
