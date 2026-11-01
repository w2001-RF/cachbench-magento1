<?php
/** Crée une politique par son nom, comme cachebench.policies.get_policy. */
class Aicache_Factory
{
    public static $classes = array(
        'lru' => 'Aicache_Policy_Lru',
        'fifo' => 'Aicache_Policy_Fifo',
        'lfu' => 'Aicache_Policy_Lfu',
        'drl' => 'Aicache_Policy_Drl',
        'semantic' => 'Aicache_Policy_Semantic',
        'cacheus_pp' => 'Aicache_Policy_CacheusPP',
        'cacheus_pp2' => 'Aicache_Policy_CacheusPP2',
    );

    /** Code officiel de sylab/cacheus : compte des objets (tailles unitaires). */
    public static $official = array('lecar', 'cacheus', 'arc', 'lirs');

    /** @return Aicache_Policy_Interface */
    public static function create($name, $capacity, array $params = array())
    {
        if (in_array($name, self::$official, true)) {
            return new Aicache_Policy_Official($name, $capacity, $params);
        }
        if (!isset(self::$classes[$name])) {
            throw new InvalidArgumentException("politique inconnue : $name (" . implode(', ', self::available()) . ')');
        }
        $cls = self::$classes[$name];
        return new $cls($capacity, $params);
    }

    public static function available()
    {
        return array_merge(array_keys(self::$classes), self::$official);
    }
}
