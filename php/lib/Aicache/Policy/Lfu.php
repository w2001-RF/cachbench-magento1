<?php
/** LFU, égalités départagées par ancienneté (LRU au sein d'une fréquence). */
class Aicache_Policy_Lfu extends Aicache_Policy_Abstract
{
    protected $freq = array();
    /** fréquence => (clé => true) dans l'ordre d'arrivée */
    protected $buckets = array();
    protected $min = 1;

    private function bump($key, $f)
    {
        $this->freq[$key] = $f;
        $this->buckets[$f][$key] = true;
    }

    private function unlink($key)
    {
        $f = $this->freq[$key];
        unset($this->freq[$key], $this->buckets[$f][$key]);
        if (empty($this->buckets[$f])) {
            unset($this->buckets[$f]);
        }
        return $f;
    }

    protected function onHit($key, Aicache_Request $req)
    {
        $this->bump($key, $this->unlink($key) + 1);
    }

    protected function onInsert($key, Aicache_Request $req)
    {
        $this->bump($key, 1);
        $this->min = 1;
    }

    protected function onRemove($key)
    {
        $this->unlink($key);
    }

    protected function victim()
    {
        $f = $this->min;
        while (!isset($this->buckets[$f])) {
            $f++;
        }
        $this->min = $f;
        foreach ($this->buckets[$f] as $k => $_) {
            return (string) $k;
        }
        throw new LogicException('cache vide');
    }
}
