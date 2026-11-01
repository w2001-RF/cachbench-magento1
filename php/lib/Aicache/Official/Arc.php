<?php
/**
 * Portage PHP d'ARC (sylab/cacheus, code/algs/arc.py), décision par décision :
 * mêmes listes T1, T2, B1, B2 et même cible p. Les journaux de visualisation et de
 * pollution du code officiel ne changent aucune décision et ne sont pas portés.
 */
class Aicache_Official_Arc
{
    public $cacheSize;
    public $time = 0;
    public $p = 0;
    protected $T1;
    protected $T2;
    protected $B1;
    protected $B2;

    public function __construct($cacheSize, array $kwargs = array())
    {
        $this->cacheSize = (int) $cacheSize;
        $this->T1 = new Aicache_Official_DequeDict();
        $this->T2 = new Aicache_Official_DequeDict();
        $this->B1 = new Aicache_Official_DequeDict();
        $this->B2 = new Aicache_Official_DequeDict();
    }

    public function contains($oblock)
    {
        return $this->T1->has($oblock) || $this->T2->has($oblock);
    }

    protected function cacheFull()
    {
        return count($this->T1) + count($this->T2) === $this->cacheSize;
    }

    protected function hit($oblock, $list)
    {
        $x = $list->get($oblock);
        $list->del($oblock);
        $this->T2->set($oblock, $x);
    }

    protected function evict()
    {
        $lenL1 = count($this->T1) + count($this->B1);
        $lenL2 = count($this->T2) + count($this->B2);
        $evicted = null;
        if ($lenL1 >= $this->cacheSize) {
            if (count($this->T1) < $this->cacheSize) {
                $this->B1->popFirst();
                $evicted = $this->replace();
            } else {
                $evicted = $this->T1->popFirst();
            }
        } elseif ($lenL1 + $lenL2 >= $this->cacheSize) {
            if ($lenL1 + $lenL2 === 2 * $this->cacheSize) {
                $this->B2->popFirst();
            }
            $evicted = $this->replace();
        }
        return $evicted;
    }

    protected function replace($xInB2 = false)
    {
        $t1 = count($this->T1);
        if ($t1 > 0 && (($xInB2 && $t1 === $this->p) || $t1 > $this->p)) {
            $evicted = $this->T1->popFirst();
            $this->B1->set($evicted, $evicted);
        } else {
            $evicted = $this->T2->popFirst();
            $this->B2->set($evicted, $evicted);
        }
        return $evicted;
    }

    protected function missInHistory($oblock, $history)
    {
        $xInB2 = $this->B2->has($oblock);
        $history->del($oblock);
        $evicted = $this->replace($xInB2);
        $this->T2->set($oblock, (string) $oblock);
        return $evicted;
    }

    protected function miss($oblock)
    {
        if ($this->B1->has($oblock)) {
            $this->p = min($this->p + max(1, intdiv(count($this->B2), count($this->B1))), $this->cacheSize);
            return $this->missInHistory($oblock, $this->B1);
        }
        if ($this->B2->has($oblock)) {
            $this->p = max($this->p - max(1, intdiv(count($this->B1), count($this->B2))), 0);
            return $this->missInHistory($oblock, $this->B2);
        }
        $evicted = null;
        if ($this->cacheFull()) {
            $evicted = $this->evict();
        }
        $this->T1->set($oblock, (string) $oblock);
        return $evicted;
    }

    /** @return array(bool hit, string|null clé évincée) */
    public function request($oblock)
    {
        $this->time++;
        if ($this->T1->has($oblock)) {
            $this->hit($oblock, $this->T1);
            return array(true, null);
        }
        if ($this->T2->has($oblock)) {
            $this->hit($oblock, $this->T2);
            return array(true, null);
        }
        return array(false, $this->miss($oblock));
    }
}
