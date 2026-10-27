<?php
class Aicache_Policy_Lru extends Aicache_Policy_Abstract
{
    /** clé => true, du moins récent au plus récent */
    protected $order = array();

    protected function onHit($key, Aicache_Request $req)
    {
        unset($this->order[$key]);
        $this->order[$key] = true;
    }

    protected function onInsert($key, Aicache_Request $req)
    {
        $this->order[$key] = true;
    }

    protected function onRemove($key)
    {
        unset($this->order[$key]);
    }

    protected function victim()
    {
        foreach ($this->order as $k => $_) {
            return (string) $k;
        }
        throw new LogicException('cache vide');
    }
}
